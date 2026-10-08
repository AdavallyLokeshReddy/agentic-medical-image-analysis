from pathlib import Path

import torch
from monai.networks.nets import SegResNet


PROJECT_ROOT = Path(__file__).resolve().parents[1]

BUNDLE_DIR = (
    PROJECT_ROOT
    / "models"
    / "monai"
    / "wholeBody_ct_segmentation"
    / "wholeBody_ct_segmentation"
)

MODEL_PATH = BUNDLE_DIR / "models" / "model.pt"


def build_ct5_network():
    device = torch.device("cpu")

    network = SegResNet(
        spatial_dims=3,
        in_channels=1,
        out_channels=105,
        init_filters=32,
        blocks_down=(1, 2, 2, 4),
        blocks_up=(1, 1, 1),
        dropout_prob=0.2,
    )

    return network.to(device)


def test_ct5_checkpoint_exists():
    assert BUNDLE_DIR.exists(), (
        f"CT-5 bundle directory not found: {BUNDLE_DIR}"
    )

    assert MODEL_PATH.exists(), (
        f"CT-5 checkpoint not found: {MODEL_PATH}"
    )

    assert MODEL_PATH.stat().st_size > 0

    print("\nCT-5 bundle:", BUNDLE_DIR)
    print("CT-5 checkpoint:", MODEL_PATH)
    print("Checkpoint size:", MODEL_PATH.stat().st_size, "bytes")


def test_ct5_checkpoint_loads():
    network = build_ct5_network()

    checkpoint = torch.load(
        MODEL_PATH,
        map_location="cpu",
        weights_only=False,
    )

    print("\nCheckpoint type:", type(checkpoint))

    if isinstance(checkpoint, dict):
        print("Checkpoint keys:", list(checkpoint.keys()))

    if isinstance(checkpoint, dict) and "model" in checkpoint:
        state_dict = checkpoint["model"]
    else:
        state_dict = checkpoint

    assert isinstance(state_dict, dict), (
        "CT-5 checkpoint does not contain a valid state_dict."
    )

    missing_keys, unexpected_keys = network.load_state_dict(
        state_dict,
        strict=False,
    )

    print("\nMissing keys:", len(missing_keys))
    print("Unexpected keys:", len(unexpected_keys))

    if missing_keys:
        print("Missing:", missing_keys)

    if unexpected_keys:
        print("Unexpected:", unexpected_keys)

    assert not missing_keys, (
        f"CT-5 checkpoint has missing keys: {missing_keys}"
    )

    assert not unexpected_keys, (
        f"CT-5 checkpoint has unexpected keys: {unexpected_keys}"
    )

    network.eval()

    print("\nCT-5 CHECKPOINT LOAD: PASS")