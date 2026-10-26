"""
Verify that this environment can actually run the ICH research model.

    python scripts/check_runtime.py --imports-only        # fast: are all packages present?
    python scripts/check_runtime.py --smoke               # also load the model and run it once
    python scripts/check_runtime.py --smoke --out run.json

--smoke feeds a SYNTHETIC phantom volume (an ellipse of soft tissue inside a bone ring). Its only
purpose is to prove the runtime executes end to end and to record timings and memory. The output
probability on a phantom has no meaning and is never presented as a finding.

Exit code 0 = everything requested worked. Non-zero = something is missing; the reason is printed.
"""
from __future__ import annotations

import argparse
import importlib
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

REQUIRED_MODULES = [
    "numpy", "torch", "monai", "timm", "skp", "cv2", "pydicom", "nibabel",
    "safetensors", "huggingface_hub", "fastapi", "uvicorn", "sqlalchemy", "psycopg",
]


def peak_memory_mb() -> float | None:
    try:
        import resource

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux reports kilobytes, macOS bytes.
        return round(peak / 1024 if sys.platform.startswith("linux") else peak / 1024 / 1024, 1)
    except Exception:
        return None


def check_imports() -> tuple[dict, list[str]]:
    versions, missing = {}, []
    for name in REQUIRED_MODULES:
        try:
            module = importlib.import_module(name)
            versions[name] = getattr(module, "__version__", "present")
        except Exception as error:  # ImportError, or a broken native library
            missing.append(f"{name}: {type(error).__name__}: {error}")
    return versions, missing


def phantom_volume(slices: int = 24, size: int = 512):
    import numpy as np

    yy, xx = np.mgrid[:size, :size]
    cy = cx = size / 2
    radius = ((yy - cy) / (size * 0.38)) ** 2 + ((xx - cx) / (size * 0.31)) ** 2
    volume = np.full((slices, size, size), -1000.0, dtype=np.float32)
    volume[:, radius <= 1.0] = 1000.0                 # bone ring
    volume[:, radius <= 0.88] = 40.0                  # soft tissue
    rng = np.random.default_rng(0)
    volume += rng.normal(0.0, 4.0, volume.shape).astype(np.float32) * (volume > -900)
    return volume


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--imports-only", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--out", default=None, help="write the result as JSON")
    args = parser.parse_args()
    if not (args.imports_only or args.smoke):
        parser.error("choose --imports-only or --smoke")

    record = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "synthetic_input": True,
        "note": "Smoke test on a synthetic phantom. Not a finding; no accuracy claim.",
    }
    versions, missing = check_imports()
    record["versions"] = versions
    record["missing"] = missing
    for name, version in versions.items():
        print(f"  ok       {name} {version}")
    for line in missing:
        print(f"  MISSING  {line}")
    if missing:
        print("\nRuntime is NOT complete. Fix the missing packages above.")
        if args.out:
            Path(args.out).write_text(json.dumps(record, indent=2))
        return 1

    if args.smoke:
        import torch

        record["torch_threads"] = torch.get_num_threads()
        from tools.ich_detection import ICHDetectionTool

        started = time.perf_counter()
        tool = ICHDetectionTool()
        record["model_load_seconds"] = round(time.perf_counter() - started, 2)
        print(f"  model loaded in {record['model_load_seconds']} s on {tool.device}")

        volume = phantom_volume()
        started = time.perf_counter()
        result = tool.run({"volume": volume})
        record["inference_seconds"] = round(time.perf_counter() - started, 2)
        record["result_status"] = result.get("status")
        record["volume_shape"] = list(volume.shape)
        print(f"  inference: status={result.get('status')} in {record['inference_seconds']} s "
              f"(synthetic phantom; output is not a finding)")

    record["peak_memory_mb"] = peak_memory_mb()
    print(f"  peak memory: {record['peak_memory_mb']} MB")
    if args.out:
        Path(args.out).write_text(json.dumps(record, indent=2))
        print(f"  written: {args.out}")
    print("\nRuntime check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
