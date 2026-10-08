from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import torch
from monai.data import MetaTensor
from monai.inferers import sliding_window_inference
from monai.networks.nets import SwinUNETR
from monai.transforms import (
    Compose,
    EnsureType,
    Orientation,
    ScaleIntensityRange,
    Spacing,
)

from preprocessing.ct_volume_preprocessing import preprocess_ct_volume
from .base import MedicalAITool


class MultiOrganSegmentationError(RuntimeError):
    """Raised when multi-organ CT segmentation cannot be completed."""


class MultiOrganSegmentationTool(MedicalAITool):
    """
    Governed research/demo tool for multi-organ segmentation of abdominal CT.

    This wraps the MONAI Swin UNETR BTCV model.

    Important:
        - Research/demo use only.
        - Not a diagnostic system.
        - Output requires verification before clinical interpretation.
        - No autonomous treatment or clinical decision-making.
    """

    name = "multi_organ_segmentation"

    description = (
        "Research/demo multi-organ segmentation of abdominal CT "
        "using the MONAI Swin UNETR BTCV model."
    )

    TOOL_VERSION = "research-demo-1.0"

    CLASSES = {
        0: "background",
        1: "spleen",
        2: "right_kidney",
        3: "left_kidney",
        4: "gallbladder",
        5: "esophagus",
        6: "liver",
        7: "stomach",
        8: "aorta",
        9: "ivc",
        10: "portal_splenic_veins",
        11: "pancreas",
        12: "right_adrenal",
        13: "left_adrenal",
    }

    def __init__(
        self,
        bundle_dir: str | Path = (
            "models/monai/swin_unetr_btcv_segmentation"
        ),
        device: str | None = None,
    ) -> None:
        self.bundle_dir = Path(bundle_dir)

        if not self.bundle_dir.exists():
            raise MultiOrganSegmentationError(
                f"MONAI bundle directory does not exist: "
                f"{self.bundle_dir}"
            )

        if device is None:
            device = (
                "cuda"
                if torch.cuda.is_available()
                else "cpu"
            )

        self.device = torch.device(device)

        self.model = SwinUNETR(
            spatial_dims=3,
            in_channels=1,
            out_channels=14,
            feature_size=48,
            use_checkpoint=False,
        )

        checkpoint_path = (
            self.bundle_dir
            / "models"
            / "model.pt"
        )

        if not checkpoint_path.exists():
            raise MultiOrganSegmentationError(
                f"Model checkpoint does not exist: "
                f"{checkpoint_path}"
            )

        checkpoint = torch.load(
            checkpoint_path,
            map_location="cpu",
            weights_only=False,
        )

        try:
            self.model.load_state_dict(checkpoint)
        except Exception as exc:
            raise MultiOrganSegmentationError(
                "Unable to load Swin UNETR checkpoint."
            ) from exc

        self.model.to(self.device)
        self.model.eval()

        self.preprocessing = Compose(
            [
                Orientation(axcodes="RAS"),
                Spacing(
                    pixdim=(1.5, 1.5, 2.0),
                    mode="bilinear",
                ),
                ScaleIntensityRange(
                    a_min=-175,
                    a_max=250,
                    b_min=0.0,
                    b_max=1.0,
                    clip=True,
                ),
                EnsureType(),
            ]
        )

    def _build_affine(
        self,
        voxel_spacing: tuple[float, float, float],
        image_position_patient: tuple[
            float,
            float,
            float,
        ],
        image_orientation_patient: tuple[float, ...],
    ) -> np.ndarray:

        orientation = np.asarray(
            image_orientation_patient,
            dtype=np.float64,
        )

        if orientation.shape != (6,):
            raise MultiOrganSegmentationError(
                "ImageOrientationPatient must contain 6 values."
            )

        row = orientation[:3]
        column = orientation[3:]

        slice_direction = np.cross(
            row,
            column,
        )

        norm = np.linalg.norm(
            slice_direction
        )

        if norm == 0:
            raise MultiOrganSegmentationError(
                "Invalid ImageOrientationPatient."
            )

        slice_direction = (
            slice_direction / norm
        )

        spacing = tuple(
            float(value)
            for value in voxel_spacing
        )

        origin = np.asarray(
            image_position_patient,
            dtype=np.float64,
        )

        affine = np.eye(
            4,
            dtype=np.float64,
        )

        # Volume axis 0 = slice direction
        affine[:3, 0] = (
            slice_direction * spacing[2]
        )

        # Volume axis 1 = row direction
        affine[:3, 1] = (
            row * spacing[0]
        )

        # Volume axis 2 = column direction
        affine[:3, 2] = (
            column * spacing[1]
        )

        affine[:3, 3] = origin

        return affine

    def _prepare_input(
        self,
        volume: np.ndarray,
        voxel_spacing: tuple[float, float, float],
        image_position_patient: tuple[
            float,
            float,
            float,
        ],
        image_orientation_patient: tuple[float, ...],
    ) -> torch.Tensor:

        if volume.ndim != 3:
            raise MultiOrganSegmentationError(
                f"Expected 3D CT volume, "
                f"got shape {volume.shape}."
            )

        affine = self._build_affine(
            voxel_spacing=voxel_spacing,
            image_position_patient=(
                image_position_patient
            ),
            image_orientation_patient=(
                image_orientation_patient
            ),
        )

        image = MetaTensor(
            volume[None, ...],
            affine=torch.tensor(
                affine,
                dtype=torch.float64,
            ),
        )

        processed = self.preprocessing(
            image
        )

        if processed.ndim != 4:
            raise MultiOrganSegmentationError(
                "Preprocessed CT must have shape "
                "(channel, depth, height, width)."
            )

        return (
            processed
            .unsqueeze(0)
            .to(self.device)
        )

    def _segment(
        self,
        model_input: torch.Tensor,
        roi_size: tuple[int, int, int] = (
            96,
            96,
            96,
        ),
        sw_batch_size: int = 1,
        overlap: float = 0.0,
    ) -> tuple[
        torch.Tensor,
        torch.Tensor,
    ]:

        with torch.no_grad():

            logits = sliding_window_inference(
                inputs=model_input,
                roi_size=roi_size,
                sw_batch_size=sw_batch_size,
                predictor=self.model,
                overlap=overlap,
            )

            probabilities = torch.softmax(
                logits,
                dim=1,
            )

            segmentation = torch.argmax(
                probabilities,
                dim=1,
            )

        return (
            probabilities,
            segmentation,
        )

    def _summarize_segmentation(
        self,
        segmentation: torch.Tensor,
    ) -> dict[str, dict[str, Any]]:

        labels, counts = torch.unique(
            segmentation.detach().cpu(),
            return_counts=True,
        )

        summary: dict[
            str,
            dict[str, Any],
        ] = {}

        for label, count in zip(
            labels,
            counts,
        ):
            label_id = int(label)
            voxel_count = int(count)

            summary[str(label_id)] = {
                "label_id": label_id,
                "name": self.CLASSES[label_id],
                "voxel_count": voxel_count,
            }

        return summary

    def predict(
        self,
        volume: np.ndarray,
        voxel_spacing: tuple[float, float, float],
        image_position_patient: tuple[
            float,
            float,
            float,
        ],
        image_orientation_patient: tuple[float, ...],
        roi_size: tuple[int, int, int] = (
            96,
            96,
            96,
        ),
        sw_batch_size: int = 1,
        overlap: float = 0.0,
    ) -> dict[str, Any]:
        """
        Run segmentation on a CT volume.

        Returns a structured research/demo result.
        """

        if volume.dtype != np.float32:
            volume = volume.astype(
                np.float32,
                copy=False,
            )

        model_input = self._prepare_input(
            volume=volume,
            voxel_spacing=voxel_spacing,
            image_position_patient=(
                image_position_patient
            ),
            image_orientation_patient=(
                image_orientation_patient
            ),
        )

        probabilities, segmentation = (
            self._segment(
                model_input=model_input,
                roi_size=roi_size,
                sw_batch_size=sw_batch_size,
                overlap=overlap,
            )
        )

        prediction = (
            segmentation[0]
            .detach()
            .cpu()
            .numpy()
            .astype(np.uint8)
        )

        probabilities_cpu = (
            probabilities[0]
            .detach()
            .cpu()
        )

        return {
            "prediction": prediction,
            "probabilities": probabilities_cpu,
            "label_summary": (
                self._summarize_segmentation(
                    segmentation
                )
            ),
            "tool": self.name,
            "tool_version": self.TOOL_VERSION,
            "model_name": "SwinUNETR-BTCV",
            "model_version": "MONAI-BTCV-bundle",
            "runtime": str(self.device),
            "verification_required": True,
            "clinical_use": "research_demo_only",
            "warnings": [
                "Research/demo model output only.",
                "This segmentation is not a diagnosis.",
                "Human verification is required before "
                "clinical interpretation.",
                "This tool has not been clinically validated.",
            ],
        }

    def predict_from_dicom(
        self,
        series_dir: str | Path,
        roi_size: tuple[int, int, int] = (
            96,
            96,
            96,
        ),
        sw_batch_size: int = 1,
        overlap: float = 0.0,
    ) -> dict[str, Any]:
        """
        Load a CT DICOM series and run segmentation.
        """

        result = preprocess_ct_volume(
            series_dir
        )

        datasets = result["datasets"]
        volume = result["volume"]

        first = datasets[0]

        return self.predict(
            volume=volume,
            voxel_spacing=(
                result["voxel_spacing"]
            ),
            image_position_patient=tuple(
                float(value)
                for value in first.ImagePositionPatient
            ),
            image_orientation_patient=tuple(
                float(value)
                for value in first.ImageOrientationPatient
            ),
            roi_size=roi_size,
            sw_batch_size=sw_batch_size,
            overlap=overlap,
        )

    def run(
        self,
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        MedicalAITool interface.

        Expected input_data:

            {
                "volume": np.ndarray,
                "voxel_spacing": (...),
                "image_position_patient": (...),
                "image_orientation_patient": (...),
                "roi_size": (96, 96, 96),
                "sw_batch_size": 1,
                "overlap": 0.0,
            }
        """

        required_fields = [
            "volume",
            "voxel_spacing",
            "image_position_patient",
            "image_orientation_patient",
        ]

        missing = [
            field
            for field in required_fields
            if field not in input_data
        ]

        if missing:
            raise MultiOrganSegmentationError(
                "Missing required input fields: "
                + ", ".join(missing)
            )

        return self.predict(
            volume=input_data["volume"],
            voxel_spacing=tuple(
                input_data["voxel_spacing"]
            ),
            image_position_patient=tuple(
                input_data[
                    "image_position_patient"
                ]
            ),
            image_orientation_patient=tuple(
                input_data[
                    "image_orientation_patient"
                ]
            ),
            roi_size=tuple(
                input_data.get(
                    "roi_size",
                    (96, 96, 96),
                )
            ),
            sw_batch_size=int(
                input_data.get(
                    "sw_batch_size",
                    1,
                )
            ),
            overlap=float(
                input_data.get(
                    "overlap",
                    0.0,
                )
            ),
        )