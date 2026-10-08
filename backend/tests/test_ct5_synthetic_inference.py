from pathlib import Path

import numpy as np
import torch
from monai.networks.nets import SegResNet


PROJECT_ROOT = Path(__file__).resolve().parents[1]

MODEL_PATH = (
    PROJECT_ROOT
    / "models"
    / "monai"
    / "wholeBody_ct_segmentation"
    / "wholeBody_ct_segmentation"
    / "models"
    / "model.pt"
)


def build_ct5_network():
    network = SegResNet(
        spatial_dims=3,
        in_channels=1,
        out_channels=105,
        init_filters=32,
        blocks_down=(1, 2, 2, 4),
        blocks_up=(1, 1, 1),
        dropout_prob=0.2,
    )

    checkpoint = torch.load(
        MODEL_PATH,
        map_location="cpu",
        weights_only=False,
    )

    network.load_state_dict(checkpoint, strict=True)
    network.eval()

    return network


def test_ct5_synthetic_forward():
    network = build_ct5_network()

    # Small synthetic CT-like volume.
    # This test validates the network itself, not the official
    # whole-body preprocessing or sliding-window pipeline.
    input_tensor = torch.zeros(
        (1, 1, 96, 96, 96),
        dtype=torch.float32,
    )

    with torch.no_grad():
        output = network(input_tensor)

    print("\nInput shape:", tuple(input_tensor.shape))
    print("Output shape:", tuple(output.shape))
    print("Output dtype:", output.dtype)

    assert output.ndim == 5
    assert output.shape[0] == 1
    assert output.shape[1] == 105
    assert output.shape[2:] == (96, 96, 96)

    assert torch.isfinite(output).all()

    print("CT-5 SYNTHETIC FORWARD: PASS")