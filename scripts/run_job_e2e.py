"""
End-to-end check of the governed analysis job against a RUNNING backend, using only the standard library.

  terminal 1 (repo root):   cd backend && uvicorn main:app --port 8000
  terminal 2 (repo root):   python scripts/run_job_e2e.py PATH_TO_DICOM_FOLDER
                            python scripts/run_job_e2e.py PATH_TO_DICOM_FOLDER --review accept --reviewer reviewer-1

What it does, in order, through the real HTTP routes:
  create case -> upload DICOM -> POST /cases/{id}/analysis -> poll GET /jobs/{id} (status only)
  -> GET /jobs/{id}/result -> optionally POST /jobs/{id}/review.

It reports what the server returned. It never invents a value: if the model runtime is missing the
job is refused or fails, and that reason is printed. Use only data you are permitted to use. The full
result is written to --out (default ./out_e2e, git-ignored) and never uploaded anywhere.

Research & Engineering Prototype - Not for clinical diagnosis or treatment.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from urllib import error, request

FINAL = {"requires_review", "completed", "failed", "blocked", "abstained"}


def call(method, url, payload=None, data=None, headers=None, timeout=120):
    headers = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, method=method, headers=headers)
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return response.status, json.loads(response.read() or b"{}")
    except error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        try:
            body = json.loads(body)
        except ValueError:
            pass
        return exc.code, body


def multipart(files):
    boundary = uuid.uuid4().hex
    parts = []
    for path in files:
        parts.append(
            (f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"{path.name}\"\r\n"
             "Content-Type: application/dicom\r\n\r\n").encode() + path.read_bytes() + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), {"Content-Type": f"multipart/form-data; boundary={boundary}"}


def heading(text):
    print("\n" + "=" * 74 + f"\n{text}\n" + "=" * 74, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dicom_dir")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--body-region", default="head")
    parser.add_argument("--batch", type=int, default=20, help="files per upload request")
    parser.add_argument("--timeout", type=int, default=900, help="seconds to wait for the job")
    parser.add_argument("--review", choices=["accept", "modify", "reject"], help="record a human review decision")
    parser.add_argument("--reviewer", default="reviewer-1")
    parser.add_argument("--reason", default=None)
    parser.add_argument("--out", default="out_e2e")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    folder = Path(args.dicom_dir)
    files = sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() == ".dcm") if folder.is_dir() else []
    if not files:
        sys.exit(f"No .dcm files found in: {folder}")

    heading("1. BACKEND AND RUNTIME")
    code, health = call("GET", f"{base}/health")
    print(f"  /health            : {code} {health}")
    if code != 200:
        sys.exit("Backend is not reachable. Start it with: cd backend && uvicorn main:app --port 8000")
    code, status = call("GET", f"{base}/governance/status")
    runtime = status.get("job_execution", {}) if isinstance(status, dict) else {}
    print(f"  job_execution      : {runtime}")
    if not runtime.get("available"):
        sys.exit(f"Model runtime is not available on this backend: {runtime.get('reason')}")

    heading("2. CASE AND UPLOAD")
    code, created = call("POST", f"{base}/cases")
    case_id = created["case_id"]
    print(f"  case               : {case_id} (HTTP {code})")
    for start in range(0, len(files), args.batch):
        batch = files[start:start + args.batch]
        body, headers = multipart(batch)
        code, uploaded = call("POST", f"{base}/cases/{case_id}/upload", data=body, headers=headers, timeout=600)
        print(f"  uploaded {start + len(batch):>4}/{len(files)}   : HTTP {code}")
        if code >= 300:
            sys.exit(f"Upload failed: {uploaded}")

    heading("3. ANALYSIS JOB (governed)")
    code, job = call("POST", f"{base}/cases/{case_id}/analysis", payload={"body_region": args.body_region})
    print(f"  POST analysis      : HTTP {code} {job if code >= 300 else {k: job[k] for k in ('job_id', 'status')}}")
    if code != 202:
        sys.exit("Job was refused (this is the governance/runtime reason above, not a crash).")
    job_id = job["job_id"]
    seen, started, last = set(), time.time(), {}
    while time.time() - started < args.timeout:
        code, last = call("GET", f"{base}/jobs/{job_id}")
        if last["status"] not in seen:
            seen.add(last["status"])
            print(f"  [{time.time() - started:6.1f}s] status = {last['status']}", flush=True)
        if last["status"] in FINAL:
            break
        time.sleep(1)
    else:
        sys.exit("Timed out waiting for the job.")
    print(f"  stage seconds      : {last['timings_seconds']}")
    if last.get("error"):
        print(f"  ERROR              : {last['error']}")
    if last.get("note"):
        print(f"  note               : {last['note']}")

    heading("4. RESULT (verification, evidence, report, review)")
    code, result = call("GET", f"{base}/jobs/{job_id}/result")
    if code != 200:
        sys.exit(f"Result not available: {result}")
    verification = result.get("verification") or {}
    for name, check in (verification.get("verification", {}).get("checks") or {}).items():
        print(f"    {check['status']:<8} {name}")
    decision = verification.get("decision") or {}
    print(f"  decision           : {decision.get('status')} -> {decision.get('action')}")
    for evidence in result.get("evidence", []):
        print(f"  evidence           : {evidence['evidence_id']} status={evidence['status']}")
        print(f"    claim            : {evidence['claim']}")
        print(f"    supporting slices: {evidence['supporting_slices']}")
        print(f"    provenance       : tool={evidence['provenance']['tool_name']} runtime={evidence['provenance']['runtime']}")
    report = result.get("report") or {}
    print(f"  report             : status={report.get('status')} observations={len(report.get('observations', []))}")
    print(f"  human review       : {result.get('human_review', {}).get('status')}")
    print(f"  case status        : {result.get('case', {}).get('status')}")

    if args.review:
        heading("5. HUMAN REVIEW")
        payload = {"reviewer_id": args.reviewer, "decision": args.review, "reason": args.reason}
        code, review = call("POST", f"{base}/jobs/{job_id}/review", payload=payload)
        print(f"  POST review        : HTTP {code} {review}")
        code, after = call("GET", f"{base}/jobs/{job_id}")
        print(f"  job status         : {after.get('status')}")
        code, result = call("GET", f"{base}/jobs/{job_id}/result")
    else:
        print("\n  Human review is still PENDING. Re-run with --review accept|modify|reject (reject/modify need --reason).")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{case_id}_{job_id}_result.json"
    out_file.write_text(json.dumps(result, indent=2))
    print(f"\n  full result written: {out_file}")
    print("  Research & Engineering Prototype - Not for clinical diagnosis or treatment.")


if __name__ == "__main__":
    main()
