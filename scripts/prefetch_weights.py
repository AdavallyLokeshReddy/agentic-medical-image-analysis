"""
Download the ICH research-model weights into the Hugging Face cache and write a manifest.

Used at container build time (so the running service never needs the network for weights) and
usable locally. The manifest records the exact repository commit and the SHA-256 of every file,
so evidence/provenance can name the weights that were actually used.

    python scripts/prefetch_weights.py [--manifest PATH]

Environment:
    HF_HOME   where the Hugging Face cache lives (default: ~/.cache/huggingface)
    ICH_MODEL_REPO  override the repository id (default: the one in backend/model_runtime/inference.py)

Licence: the weights repository declares the MIT licence on its model card. The model card also
states it is research software, not a medical device. Re-check the card before changing the repo id.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

# Must match the files requested by HemorrhageSliceModel._artifact(...) in
# backend/model_runtime/inference.py. If that file changes, change this list.
ARTIFACTS = [
    "classifier/model.safetensors",
    "sequence/model.safetensors",
    *[f"segmentation/fold{fold}.safetensors" for fold in range(5)],
]
DEFAULT_REPO = "ianpan/ct-head-hemorrhage-detection"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", default=None, help="where to write model_manifest.json")
    args = parser.parse_args()

    try:
        from huggingface_hub import HfApi, hf_hub_download
    except ImportError:
        print("huggingface_hub is not installed.", file=sys.stderr)
        return 2

    repo = os.environ.get("ICH_MODEL_REPO", DEFAULT_REPO)
    cache_root = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
    manifest_path = Path(args.manifest) if args.manifest else cache_root / "model_manifest.json"

    # NOTE: no revision is passed, deliberately. The runtime (HemorrhageSliceModel) also loads the
    # default revision, and offline loading resolves it through the cache's refs/main entry.
    # The resolved commit is recorded below so a build can be traced to the weights it contains.
    sha = HfApi().model_info(repo).sha

    files = []
    started = time.perf_counter()
    for name in ARTIFACTS:
        local = Path(hf_hub_download(repo_id=repo, filename=name))
        files.append({"file": name, "bytes": local.stat().st_size, "sha256": sha256_of(local)})
        print(f"  fetched {name} ({local.stat().st_size / 1e6:.1f} MB)", flush=True)

    manifest = {
        "repo_id": repo,
        "resolved_commit": sha,
        "licence_declared_on_model_card": "MIT",
        "status": "research software, not a medical device; clinical validation not established",
        "files": files,
        "download_seconds": round(time.perf_counter() - started, 1),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"manifest written: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
