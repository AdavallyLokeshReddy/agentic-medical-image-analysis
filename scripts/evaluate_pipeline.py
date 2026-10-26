"""
Reproducible evaluation of what THIS prototype can honestly measure today.

Measures, against a running API (default http://localhost:8000), using SYNTHETIC phantoms only:
  1. Workflow turnaround time  (upload -> validation -> preprocessing -> preview -> plan)
  2. Input-validation gate     (valid vs malformed series; sensitivity/specificity OF THE GATE)
  3. Determinism               (identical input -> identical governance plan)
  4. Security probes           (hostile case IDs, CORS origin policy)

It does NOT measure diagnostic accuracy, localization, calibration or reporting quality: those need
model weights and labelled data that are not in this repository. See docs/RESEARCH_BASIS.md.

Usage: python scripts/evaluate_pipeline.py OUT.json [--api URL] [--runs 10]
"""
import argparse, hashlib, json, statistics, subprocess, sys, tempfile, time
from pathlib import Path

import httpx
import pydicom

HERE = Path(__file__).resolve().parent


def make_series(dest: Path, slices: int, size: int):
    subprocess.run([sys.executable, str(HERE / "make_synthetic_ct.py"), str(dest), "--slices", str(slices), "--size", str(size)],
                   check=True, capture_output=True)
    return sorted(dest.glob("*.dcm"))


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, round(q * (len(xs) - 1)))]


def timed(client, method, url, **kw):
    t = time.perf_counter()
    r = client.request(method, url, **kw)
    return r, (time.perf_counter() - t) * 1000


def upload(client, case, files):
    return client.post(f"/cases/{case}/upload", files=[("files", (f.name, f.read_bytes(), "application/dicom")) for f in files])


# ---------------------------------------------------------------- 1. turnaround
def turnaround(client, files, runs):
    stages = ["upload", "series", "series_info", "ct_data", "preview", "plan"]
    acc = {s: [] for s in stages}; total = []
    for _ in range(runs):
        case = client.post("/cases").json()["case_id"]
        t0 = time.perf_counter()
        _, d = timed(client, "POST", f"/cases/{case}/upload", files=[("files", (f.name, f.read_bytes(), "application/dicom")) for f in files]); acc["upload"].append(d)
        for name, path in [("series", "series"), ("series_info", "series-info"), ("ct_data", "ct-data"), ("preview", "preview")]:
            r, d = timed(client, "GET", f"/cases/{case}/{path}"); assert r.status_code == 200, (path, r.text[:200]); acc[name].append(d)
        r, d = timed(client, "GET", f"/governance/cases/{case}/plan", params={"body_region": "head"}); assert r.status_code == 200, r.text[:200]; acc["plan"].append(d)
        total.append((time.perf_counter() - t0) * 1000)
    summ = lambda xs: {"median_ms": round(statistics.median(xs), 1), "p95_ms": round(pct(xs, .95), 1), "min_ms": round(min(xs), 1), "max_ms": round(max(xs), 1)}
    return {"runs": runs, "stages": {k: summ(v) for k, v in acc.items()}, "total": summ(total)}


# ---------------------------------------------------------------- 2. validation gate
def malformed_sets(valid_files, work: Path):
    sets = {}
    def clone(name):
        d = work / name; d.mkdir(); return d
    def rewrite(name, mutate, count=None):
        d = clone(name)
        for i, f in enumerate(valid_files[:count] if count else valid_files):
            ds = pydicom.dcmread(f); mutate(ds, i); ds.save_as(d / f.name)
        sets[name] = sorted(d.glob("*.dcm"))
    rewrite("MR modality (unsupported)", lambda ds, i: setattr(ds, "Modality", "MR"))
    rewrite("Non-CT modality: US", lambda ds, i: setattr(ds, "Modality", "US"))
    def mixed(ds, i):
        if i % 2: ds.SeriesInstanceUID = "1.2.3.4.5.999"
    rewrite("Mixed series UIDs in one upload", mixed)
    def shape(ds, i):
        if i == 3:
            import numpy as np
            ds.Rows = ds.Columns = 64; ds.PixelData = (np.zeros((64, 64), dtype=ds.pixel_array.dtype)).tobytes()
    rewrite("Inconsistent matrix size across slices", shape)
    def nopos(ds, i):
        if "ImagePositionPatient" in ds: del ds["ImagePositionPatient"]
    rewrite("Missing ImagePositionPatient", nopos)
    def study(ds, i):
        if i % 2: ds.StudyInstanceUID = "1.2.3.4.5.777"
    rewrite("Mixed study UIDs", study)
    rewrite("Single slice only", lambda ds, i: None, count=1)
    d = clone("Non-DICOM bytes"); (d / "a.dcm").write_bytes(b"this is not a dicom file" * 50); sets["Non-DICOM bytes named .dcm"] = [d / "a.dcm"]
    d = clone("Empty file"); (d / "a.dcm").write_bytes(b""); sets["Zero-length file"] = [d / "a.dcm"]
    d = clone("Truncated"); b = valid_files[0].read_bytes(); (d / "a.dcm").write_bytes(b[: len(b) // 3]); sets["Truncated DICOM"] = [d / "a.dcm"]
    return sets


def classify(client, files):
    """Return (flagged_as_bad: bool, detail)."""
    case = client.post("/cases").json()["case_id"]
    r = upload(client, case, files)
    if r.status_code >= 400:
        return True, f"upload rejected: HTTP {r.status_code}"
    r = client.get(f"/cases/{case}/series-info")
    if r.status_code >= 400:
        return True, f"series-info rejected: HTTP {r.status_code}"
    j = r.json()
    ok = j.get("series_status") == "valid"
    return (not ok), f"series_status={j.get('series_status')}" + (f" ({j.get('validation_error')})" if j.get("validation_error") else "")


def validation_gate(client, valid_files, work: Path):
    bad = {}
    for name, files in malformed_sets(valid_files, work).items():
        flagged, detail = classify(client, files); bad[name] = {"flagged": flagged, "detail": detail}
    good = {}
    for i in range(3):
        flagged, detail = classify(client, valid_files); good[f"valid phantom #{i + 1}"] = {"flagged": flagged, "detail": detail}
    tp = sum(v["flagged"] for v in bad.values()); fn = len(bad) - tp
    fp = sum(v["flagged"] for v in good.values()); tn = len(good) - fp
    return {"malformed_total": len(bad), "malformed_flagged": tp, "missed": fn, "valid_total": len(good), "valid_wrongly_flagged": fp,
            "gate_sensitivity": tp / len(bad), "gate_specificity": tn / len(good), "malformed": bad, "valid": good}


# ---------------------------------------------------------------- 3. determinism
def determinism(client, files, runs=10):
    digests = set()
    for _ in range(runs):
        case = client.post("/cases").json()["case_id"]; upload(client, case, files)
        j = client.get(f"/governance/cases/{case}/plan", params={"body_region": "head", "clinical_question": "ICH?"}).json()
        s = json.dumps(j, sort_keys=True).replace(case, "<CASE>")
        digests.add(hashlib.sha256(s.encode()).hexdigest())
    return {"runs": runs, "distinct_plans": len(digests), "identical": len(digests) == 1}


# ---------------------------------------------------------------- 4. security probes
def security(client, api):
    probes = ["../etc/passwd", "..%2f..%2fetc%2fpasswd", "CASE-1;rm -rf", "CASE 0001", "a" * 300 + "/x", "%00", "CASE-0001/../../x", "<script>alert(1)</script>"]
    results = {}
    for p in probes:
        codes = []
        for path in (f"/cases/{p}", f"/cases/{p}/series", f"/governance/cases/{p}/audit", f"/governance/cases/{p}/plan"):
            try: codes.append(client.get(path).status_code)
            except Exception as e: codes.append(type(e).__name__)
        results[p[:40]] = {"statuses": codes, "safe": all(isinstance(c, int) and c in (400, 404, 405, 422) for c in codes)}
    cors = {}
    for origin in ("http://localhost:3000", "https://evil.example.com"):
        r = client.options("/cases", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
        cors[origin] = r.headers.get("access-control-allow-origin")
    return {"path_probes_total": len(results), "path_probes_safe": sum(v["safe"] for v in results.values()), "probes": results,
            "cors_allowed_origin_header": cors, "cors_rejects_unlisted_origin": cors["https://evil.example.com"] is None}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("--api", default="http://localhost:8000"); ap.add_argument("--runs", type=int, default=10)
    a = ap.parse_args()
    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "api": a.api, "data": "synthetic phantoms only (no patient data, no pathology)"}
    with tempfile.TemporaryDirectory() as tmp, httpx.Client(base_url=a.api, timeout=300) as c:
        tmp = Path(tmp)
        out["health"] = c.get("/health").json()
        small = make_series(tmp / "small", 24, 128); big = make_series(tmp / "big", 40, 512)
        out["turnaround"] = {"24 slices x 128x128": turnaround(c, small, a.runs), "40 slices x 512x512": turnaround(c, big, a.runs)}
        work = tmp / "bad"; work.mkdir()
        out["validation_gate"] = validation_gate(c, small, work)
        out["determinism"] = determinism(c, small)
        out["security"] = security(c, a.api)
    Path(a.out).write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k in ("turnaround", "determinism")}, indent=1)[:1800])
    g = out["validation_gate"]; print("GATE", g["malformed_flagged"], "/", g["malformed_total"], "malformed flagged;", g["valid_wrongly_flagged"], "/", g["valid_total"], "valid wrongly flagged")
    for k, v in g["malformed"].items(): print("  ", "FLAGGED" if v["flagged"] else "MISSED ", k, "->", v["detail"][:90])
    s = out["security"]; print("SECURITY", s["path_probes_safe"], "/", s["path_probes_total"], "safe; cors:", s["cors_allowed_origin_header"])


main()
