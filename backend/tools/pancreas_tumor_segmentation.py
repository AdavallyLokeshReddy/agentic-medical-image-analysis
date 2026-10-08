from __future__ import annotations

import os
import glob
from typing import Any, Dict

import numpy as np
import torch
import torch.nn.functional as F
from monai.networks.nets import DiNTS, TopologyInstance

from tools.base import MedicalAITool
from preprocessing.ct_preprocessing import preprocess_ct_series


class PancreasTumorSegmentationError(RuntimeError):
    """Raised when pancreas/tumor segmentation cannot be completed."""


class PancreasTumorSegmentationTool(MedicalAITool):
    """
    Research/demo pancreas and pancreatic-tumor segmentation tool.

    Uses the official MONAI Model Zoo Pancreas and Tumor DiNTS bundle.

    This tool is NOT clinically validated and must not be used as
    a standalone diagnostic system.
    """

    name = "pancreas_tumor_segmentation"

    description = (
        "Research/demo pancreas and pancreatic tumor segmentation "
        "of abdominal CT using the MONAI DiNTS model."
    )

    TOOL_VERSION = "research-demo-1.0"
    MODEL_NAME = "MONAI Pancreas and Tumor DiNTS Segmentation"
    MODEL_VERSION = "MONAI-bundle-0.5.2"

    SUPPORTED_MODALITIES = ["CT"]
    SUPPORTED_BODY_REGIONS = ["PANCREAS", "ABDOMEN"]

    MODEL_ROOT = os.path.join(
        "models",
        "monai",
        "pancreas_ct_dints_segmentation",
    )

    ARCH_PATH = os.path.join(
        MODEL_ROOT,
        "models",
        "search_code_18590.pt",
    )

    MODEL_PATH = os.path.join(
        MODEL_ROOT,
        "models",
        "model.pt",
    )

    LABELS = {
        0: "background",
        1: "pancreas",
        2: "pancreatic_tumor",
    }

    def __init__(self) -> None:
        self._network = None

    # ---------------------------------------------------------
    # Model loading
    # ---------------------------------------------------------

    def _load_model(self) -> None:
        if self._network is not None:
            return

        if not os.path.exists(self.ARCH_PATH):
            raise PancreasTumorSegmentationError(
                f"Architecture checkpoint not found: {self.ARCH_PATH}"
            )

        if not os.path.exists(self.MODEL_PATH):
            raise PancreasTumorSegmentationError(
                f"Model checkpoint not found: {self.MODEL_PATH}"
            )

        arch = torch.load(
            self.ARCH_PATH,
            map_location="cpu",
            weights_only=False,
        )

        dints_space = TopologyInstance(
            arch_code=[
                arch["arch_code_a"],
                arch["arch_code_c"],
            ],
            channel_mul=1,
            num_blocks=12,
            num_depths=4,
            use_downsample=True,
            device="cpu",
        )

        network = DiNTS(
            dints_space=dints_space,
            in_channels=1,
            num_classes=3,
            use_downsample=True,
            node_a=torch.from_numpy(arch["node_a"]),
        )

        checkpoint = torch.load(
            self.MODEL_PATH,
            map_location="cpu",
            weights_only=False,
        )

        network.load_state_dict(
            checkpoint,
            strict=True,
        )

        network.eval()

        self._network = network

    # ---------------------------------------------------------
    # CT preprocessing
    # ---------------------------------------------------------

    @staticmethod
    def _resample_to_1mm(
        volume: np.ndarray,
        spacing: tuple[float, float, float],
    ) -> torch.Tensor:
        """
        Resample raw HU volume to 1 mm isotropic spacing.

        Existing CT preprocessing returns volume as:
            (Z, Y, X)

        and spacing as:
            (Z, Y, X)
        """

        z, y, x = volume.shape

        sz, sy, sx = spacing

        new_z = max(1, round(z * sz))
        new_y = max(1, round(y * sy))
        new_x = max(1, round(x * sx))

        tensor = torch.from_numpy(
            volume.astype(np.float32)
        )[None, None]

        tensor = F.interpolate(
            tensor,
            size=(new_z, new_y, new_x),
            mode="trilinear",
            align_corners=False,
        )

        return tensor

    @staticmethod
    def _normalize_intensity(
        volume: torch.Tensor,
    ) -> torch.Tensor:
        """
        Official bundle intensity scaling:

        [-87, 199] -> [0, 1]
        """

        volume = torch.clamp(
            volume,
            min=-87.0,
            max=199.0,
        )

        return (volume + 87.0) / 286.0

    @staticmethod
    def _center_crop_96(
        volume: torch.Tensor,
    ) -> torch.Tensor:
        """
        Controlled 96^3 crop used for safe CPU smoke testing.
        """

        _, _, z, y, x = volume.shape

        if z < 96 or y < 96 or x < 96:
            raise PancreasTumorSegmentationError(
                "Preprocessed CT volume is smaller than the "
                "required 96x96x96 model input."
            )

        cz = z // 2
        cy = y // 2
        cx = x // 2

        z0 = cz - 48
        y0 = cy - 48
        x0 = cx - 48

        return volume[
            :,
            :,
            z0:z0 + 96,
            y0:y0 + 96,
            x0:x0 + 96,
        ]

    # ---------------------------------------------------------
    # Inference
    # ---------------------------------------------------------

    def predict_hu_volume(
        self,
        volume: np.ndarray,
        spacing: tuple[float, float, float],
        mode: str = "controlled_crop",
    ) -> Dict[str, Any]:

        # -----------------------------------------------------
        # Validate CT volume
        # -----------------------------------------------------

        if not isinstance(volume, np.ndarray):
            raise PancreasTumorSegmentationError(
                "CT volume must be a NumPy array."
            )

        if volume.ndim != 3:
            raise PancreasTumorSegmentationError(
                f"Expected 3D CT volume, got shape {volume.shape}"
            )

        if volume.size == 0:
            raise PancreasTumorSegmentationError(
                "CT volume is empty."
            )

        # Reject NaN and infinite values before resampling
        # or intensity normalization.
        if not np.all(np.isfinite(volume)):
            raise PancreasTumorSegmentationError(
                "CT volume contains NaN or infinite values."
            )

        # -----------------------------------------------------
        # Validate voxel spacing
        # -----------------------------------------------------

        if not isinstance(spacing, (tuple, list)):
            raise PancreasTumorSegmentationError(
                "Voxel spacing must be a tuple or list "
                "containing three values."
            )

        if len(spacing) != 3:
            raise PancreasTumorSegmentationError(
                "Voxel spacing must contain exactly three values "
                "(Z, Y, X)."
            )

        spacing = tuple(float(x) for x in spacing)

        if not all(np.isfinite(x) for x in spacing):
            raise PancreasTumorSegmentationError(
                "Voxel spacing contains NaN or infinite values."
            )

        if not all(x > 0 for x in spacing):
            raise PancreasTumorSegmentationError(
                "Voxel spacing must contain positive values."
            )

        # -----------------------------------------------------
        # Validate inference mode
        # -----------------------------------------------------

        if mode not in {"controlled_crop"}:
            raise PancreasTumorSegmentationError(
                "Only controlled_crop mode is enabled in this "
                "research prototype. Full-volume inference will "
                "be added after CT integration testing."
            )

        # -----------------------------------------------------
        # Model loading
        # -----------------------------------------------------

        self._load_model()

        # -----------------------------------------------------
        # Resampling
        # -----------------------------------------------------

        resampled = self._resample_to_1mm(
            volume,
            spacing,
        )

        # -----------------------------------------------------
        # Intensity normalization
        # -----------------------------------------------------

        normalized = self._normalize_intensity(
            resampled
        )

        # -----------------------------------------------------
        # Controlled 96x96x96 crop
        # -----------------------------------------------------

        model_input = self._center_crop_96(
            normalized
        )

        # -----------------------------------------------------
        # Model inference
        # -----------------------------------------------------

        with torch.inference_mode():
            logits = self._network(model_input)

        prediction = torch.argmax(
            logits,
            dim=1,
        )

        # -----------------------------------------------------
        # Label summary
        # -----------------------------------------------------

        unique, counts = torch.unique(
            prediction,
            return_counts=True,
        )

        label_summary = {}

        for label, count in zip(
            unique.tolist(),
            counts.tolist(),
        ):
            label_summary[self.LABELS[label]] = int(count)

        # -----------------------------------------------------
        # Return structured prediction result
        # -----------------------------------------------------

        return {
            "prediction": prediction.squeeze(0).numpy(),
            "prediction_shape": list(
                prediction.squeeze(0).shape
            ),
            "label_summary": label_summary,
            "input_shape": list(model_input.shape),
            "resampled_shape": list(resampled.shape),
            "input_range": [
                float(model_input.min()),
                float(model_input.max()),
            ],
        }

    # ---------------------------------------------------------
    # Public tool interface
    # ---------------------------------------------------------

    def run(
        self,
        input_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        # -----------------------------------------------------
        # Validate input structure
        # -----------------------------------------------------

        if not isinstance(input_data, dict):
            raise PancreasTumorSegmentationError(
                "input_data must be a dictionary."
            )

        # -----------------------------------------------------
        # Validate modality
        # -----------------------------------------------------

        modality = str(
            input_data.get("modality", "CT")
        ).upper()

        if modality != "CT":
            raise PancreasTumorSegmentationError(
                "PancreasTumorSegmentationTool requires CT input."
            )

        # -----------------------------------------------------
        # Locate DICOM files
        # -----------------------------------------------------

        series_dir = input_data.get("series_dir")

        if series_dir:
            file_paths = sorted(
                glob.glob(
                    os.path.join(
                        series_dir,
                        "*.dcm",
                    )
                )
            )
        else:
            file_paths = input_data.get(
                "file_paths",
                [],
            )

        if not file_paths:
            raise PancreasTumorSegmentationError(
                "No DICOM files supplied."
            )

        # -----------------------------------------------------
        # CT preprocessing
        # -----------------------------------------------------

        result = preprocess_ct_series(
            file_paths
        )

        volume = result["volume"]

        spacing = tuple(
            float(x)
            for x in result["voxel_spacing"]
        )

        # -----------------------------------------------------
        # Model prediction
        # -----------------------------------------------------

        prediction_result = self.predict_hu_volume(
            volume=volume,
            spacing=spacing,
            mode=input_data.get(
                "mode",
                "controlled_crop",
            ),
        )

        # -----------------------------------------------------
        # Structured tool result
        # -----------------------------------------------------

        return {
            "tool_name": self.name,
            "tool_version": self.TOOL_VERSION,

            "model_name": self.MODEL_NAME,
            "model_version": self.MODEL_VERSION,

            "supported_modality": "CT",

            "body_region": input_data.get(
                "body_region",
                "PANCREAS",
            ),

            "intended_use": (
                "Research/demo pancreas and "
                "pancreatic tumor segmentation."
            ),

            "prediction": prediction_result[
                "prediction"
            ],

            "prediction_shape": prediction_result[
                "prediction_shape"
            ],

            "label_summary": prediction_result[
                "label_summary"
            ],

            "input_shape": prediction_result[
                "input_shape"
            ],

            "resampled_shape": prediction_result[
                "resampled_shape"
            ],

            "voxel_spacing": spacing,

            "input_range": prediction_result[
                "input_range"
            ],

            "verification_required": True,

            "clinical_use": "research_demo_only",

            "warnings": [
                "This model is not clinically validated.",
                "Output is not a diagnosis.",
                "Human clinical verification is required.",
                "Current prototype uses a controlled 96x96x96 crop.",
                "Full-volume inference is intentionally disabled "
                "until CT integration testing is complete.",
            ],

            "provenance": {
                "tool_name": self.name,
                "tool_version": self.TOOL_VERSION,
                "model_name": self.MODEL_NAME,
                "model_version": self.MODEL_VERSION,
                "runtime": "PyTorch CPU",
            },
        }