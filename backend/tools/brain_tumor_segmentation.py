from __future__ import annotations

import os
from typing import Any, Dict

import nibabel as nib
import numpy as np
import torch
from monai.inferers import SlidingWindowInferer
from monai.networks.nets import SegResNet

from tools.base import MedicalAITool


class BrainTumorSegmentationError(RuntimeError):
    """Raised when MRI brain-tumor segmentation cannot be completed."""


class BrainTumorSegmentationTool(MedicalAITool):
    """
    MRI brain tumor / lesion segmentation using the MONAI
    BraTS MRI segmentation bundle.

    Research/demo use only.
    This tool does not provide a clinical diagnosis.
    """

    name = "brain_tumor_segmentation"

    description = (
        "Research/demo MRI brain tumor subregion segmentation "
        "using T1c, T1, T2 and FLAIR sequences."
    )

    MODEL_NAME = "MONAI BraTS MRI segmentation"
    MODEL_VERSION = "0.5.4"
    TOOL_VERSION = "research-demo-1.0"

    REQUIRED_SEQUENCES = ("T1c", "T1", "T2", "FLAIR")

    def __init__(
        self,
        bundle_dir: str = r"models\monai\brats_mri_segmentation",
        device: str | None = None,
    ) -> None:

        self.bundle_dir = bundle_dir

        if device is None:
            self.device = torch.device(
                "cuda" if torch.cuda.is_available() else "cpu"
            )
        else:
            self.device = torch.device(device)

        self.weights_path = os.path.join(
            self.bundle_dir,
            "models",
            "model.pt",
        )

        if not os.path.exists(self.weights_path):
            raise BrainTumorSegmentationError(
                f"MRI model weights not found: {self.weights_path}"
            )

        self.model = self._build_model()

    def _build_model(self) -> torch.nn.Module:
        """Build and load the exact SegResNet architecture from the bundle."""

        model = SegResNet(
            spatial_dims=3,
            init_filters=16,
            in_channels=4,
            out_channels=3,
            dropout_prob=0.2,
            blocks_down=(1, 2, 2, 4),
            blocks_up=(1, 1, 1),
        )

        state_dict = torch.load(
            self.weights_path,
            map_location="cpu",
            weights_only=True,
        )

        model.load_state_dict(
            state_dict,
            strict=True,
        )

        model.to(self.device)
        model.eval()

        return model

    @staticmethod
    def _load_nifti(path: str, sequence: str) -> np.ndarray:
        """Load one MRI sequence and validate its basic numerical state."""

        if not path:
            raise BrainTumorSegmentationError(
                f"Missing path for MRI sequence '{sequence}'."
            )

        if not os.path.exists(path):
            raise BrainTumorSegmentationError(
                f"MRI sequence file does not exist: {path}"
            )

        try:
            image = nib.load(path)
            volume = np.asarray(
                image.get_fdata(),
                dtype=np.float32,
            )
        except Exception as exc:
            raise BrainTumorSegmentationError(
                f"Unable to load MRI sequence '{sequence}': {exc}"
            ) from exc

        if volume.ndim != 3:
            raise BrainTumorSegmentationError(
                f"MRI sequence '{sequence}' must be 3D, "
                f"got shape {volume.shape}."
            )

        if not np.isfinite(volume).all():
            raise BrainTumorSegmentationError(
                f"MRI sequence '{sequence}' contains non-finite values."
            )

        return volume

    @staticmethod
    def _validate_geometry(
        volumes: Dict[str, np.ndarray],
        images: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Ensure all MRI sequences share the required geometry."""

        shapes = {
            sequence: tuple(volume.shape)
            for sequence, volume in volumes.items()
        }

        reference_shape = shapes["T1c"]

        for sequence, shape in shapes.items():
            if shape != reference_shape:
                raise BrainTumorSegmentationError(
                    "MRI sequence geometry mismatch: "
                    f"T1c={reference_shape}, "
                    f"{sequence}={shape}."
                )

        spacings = {}

        for sequence, image in images.items():
            spacing = tuple(
                float(value)
                for value in image.header.get_zooms()[:3]
            )

            spacings[sequence] = spacing

            if not np.allclose(
                spacing,
                (1.0, 1.0, 1.0),
                atol=1e-3,
            ):
                raise BrainTumorSegmentationError(
                    f"MRI sequence '{sequence}' does not satisfy "
                    f"the 1 mm isotropic input contract. "
                    f"Spacing={spacing}."
                )

        reference_affine = images["T1c"].affine

        for sequence, image in images.items():
            if not np.allclose(
                image.affine,
                reference_affine,
                atol=1e-3,
            ):
                raise BrainTumorSegmentationError(
                    f"MRI sequence affine mismatch: "
                    f"T1c vs {sequence}."
                )

        return {
            "shapes": shapes,
            "spacing": spacings,
            "reference_affine": reference_affine.tolist(),
        }

    @staticmethod
    def _normalize_channel(
        volume: np.ndarray,
    ) -> np.ndarray:
        """
        Match the bundle's NormalizeIntensityd behavior:
        nonzero=True, channel_wise=True.
        """

        result = np.zeros_like(
            volume,
            dtype=np.float32,
        )

        mask = volume != 0

        if not np.any(mask):
            return result

        values = volume[mask]

        mean = float(values.mean())
        std = float(values.std())

        if std > 0:
            result[mask] = (
                (values - mean) / std
            )
        else:
            result[mask] = values - mean

        return result

    @staticmethod
    def _dice(
        prediction: np.ndarray,
        target: np.ndarray,
    ) -> float:
        """
        Utility retained for research output diagnostics.
        Not used as a clinical decision criterion.
        """

        prediction = prediction.astype(bool)
        target = target.astype(bool)

        denominator = (
            prediction.sum()
            + target.sum()
        )

        if denominator == 0:
            return 1.0

        intersection = np.logical_and(
            prediction,
            target,
        ).sum()

        return float(
            (2.0 * intersection) / denominator
        )

    def run(
        self,
        input_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run MRI brain tumor segmentation.

        Expected input:

        {
            "T1c": "<path>",
            "T1": "<path>",
            "T2": "<path>",
            "FLAIR": "<path>"
        }

        Optional:

        {
            "case_id": "...",
            "image_ids": [...]
        }
        """

        if not isinstance(input_data, dict):
            raise BrainTumorSegmentationError(
                "input_data must be a dictionary."
            )

        missing = [
            sequence
            for sequence in self.REQUIRED_SEQUENCES
            if not input_data.get(sequence)
        ]

        if missing:
            raise BrainTumorSegmentationError(
                "Missing required MRI sequences: "
                + ", ".join(missing)
            )

        case_id = input_data.get("case_id")
        image_ids = input_data.get("image_ids", [])

        paths = {
            sequence: input_data[sequence]
            for sequence in self.REQUIRED_SEQUENCES
        }

        images = {}
        volumes = {}

        for sequence in self.REQUIRED_SEQUENCES:
            if not os.path.exists(paths[sequence]):
                raise BrainTumorSegmentationError(
                    f"MRI sequence file does not exist: "
                    f"{paths[sequence]}"
                )

            try:
                images[sequence] = nib.load(
                    paths[sequence]
                )

                volumes[sequence] = np.asarray(
                    images[sequence].get_fdata(),
                    dtype=np.float32,
                )
            except Exception as exc:
                raise BrainTumorSegmentationError(
                    f"Failed to load '{sequence}': {exc}"
                ) from exc

            if volumes[sequence].ndim != 3:
                raise BrainTumorSegmentationError(
                    f"{sequence} must be a 3D volume."
                )

            if not np.isfinite(
                volumes[sequence]
            ).all():
                raise BrainTumorSegmentationError(
                    f"{sequence} contains non-finite values."
                )

        geometry = self._validate_geometry(
            volumes,
            images,
        )

        # Fixed model channel order from the MONAI bundle.
        normalized = np.stack(
            [
                self._normalize_channel(
                    volumes["T1c"]
                ),
                self._normalize_channel(
                    volumes["T1"]
                ),
                self._normalize_channel(
                    volumes["T2"]
                ),
                self._normalize_channel(
                    volumes["FLAIR"]
                ),
            ],
            axis=0,
        ).astype(np.float32)

        if not np.isfinite(normalized).all():
            raise BrainTumorSegmentationError(
                "Normalized MRI input contains non-finite values."
            )

        input_tensor = torch.from_numpy(
            normalized
        ).unsqueeze(0).to(self.device)

        inferer = SlidingWindowInferer(
            roi_size=(240, 240, 160),
            sw_batch_size=1,
            overlap=0.5,
        )

        with torch.no_grad():
            logits = inferer(
                input_tensor,
                self.model,
            )

            probabilities = torch.sigmoid(
                logits
            )

        if not torch.isfinite(
            probabilities
        ).all():
            raise BrainTumorSegmentationError(
                "MRI model produced non-finite probabilities."
            )

        probability_array = (
            probabilities[0]
            .detach()
            .cpu()
            .numpy()
            .astype(np.float32)
        )

        # Channel semantics defined by the MONAI bundle.
        tumor_core_probability = probability_array[0]
        whole_tumor_probability = probability_array[1]
        enhancing_tumor_probability = probability_array[2]

        tumor_core_mask = (
            tumor_core_probability >= 0.5
        )

        whole_tumor_mask = (
            whole_tumor_probability >= 0.5
        )

        enhancing_tumor_mask = (
            enhancing_tumor_probability >= 0.5
        )

        prediction_shape = tuple(
            probability_array.shape[1:]
        )

        input_shape = tuple(
            normalized.shape[1:]
        )

        if prediction_shape != input_shape:
            raise BrainTumorSegmentationError(
                "Prediction spatial shape does not match "
                f"input shape: "
                f"{prediction_shape} vs {input_shape}."
            )

        output = {
            "case_id": case_id,

            "modality": "MRI",
            "body_region": "brain",

            "input_sequences": [
                "T1c",
                "T1",
                "T2",
                "FLAIR",
            ],

            "input_shape": input_shape,
            "prediction_shape": prediction_shape,

            "voxel_spacing": {
                sequence: geometry["spacing"][sequence]
                for sequence in self.REQUIRED_SEQUENCES
            },

            "model_input_spacing": (
                1.0,
                1.0,
                1.0,
            ),

            "probabilities": {
                "tumor_core": tumor_core_probability,
                "whole_tumor": whole_tumor_probability,
                "enhancing_tumor": (
                    enhancing_tumor_probability
                ),
            },

            "masks": {
                "tumor_core": tumor_core_mask,
                "whole_tumor": whole_tumor_mask,
                "enhancing_tumor": enhancing_tumor_mask,
            },

            "label_summary": {
                "tumor_core": {
                    "region": "Tumor Core",
                    "voxel_count": int(
                        tumor_core_mask.sum()
                    ),
                },
                "whole_tumor": {
                    "region": "Whole Tumor",
                    "voxel_count": int(
                        whole_tumor_mask.sum()
                    ),
                },
                "enhancing_tumor": {
                    "region": "Enhancing Tumor",
                    "voxel_count": int(
                        enhancing_tumor_mask.sum()
                    ),
                },
            },

            "tool": self.name,
            "tool_version": self.TOOL_VERSION,

            "model": self.MODEL_NAME,
            "model_version": self.MODEL_VERSION,

            "runtime": {
                "device": str(self.device),
                "framework": "PyTorch",
                "architecture": "SegResNet",
                "inferer": "SlidingWindowInferer",
                "roi_size": (
                    240,
                    240,
                    160,
                ),
                "sw_batch_size": 1,
                "overlap": 0.5,
            },

            "verification_required": True,

            "clinical_use": "research_demo_only",

            "warnings": [
                "This output is not a clinical diagnosis.",
                "This model is a research/demo implementation.",
                "Human verification is required before workflow use.",
                "The model was developed using the BraTS "
                "training distribution and may not generalize "
                "to all MRI acquisition protocols.",
                "All four required MRI sequences must be present "
                "and satisfy the input geometry contract.",
                "No autonomous treatment or irreversible action "
                "is permitted from this output.",
            ],

            "provenance": {
                "bundle": "brats_mri_segmentation",
                "bundle_version": self.MODEL_VERSION,
                "model_name": self.MODEL_NAME,
                "model_version": self.MODEL_VERSION,
                "tool_name": self.name,
                "tool_version": self.TOOL_VERSION,
                "architecture": "SegResNet",
                "input_sequences": [
                    "T1c",
                    "T1",
                    "T2",
                    "FLAIR",
                ],
                "channel_order": [
                    "T1c",
                    "T1",
                    "T2",
                    "FLAIR",
                ],
                "output_regions": [
                    "Tumor Core",
                    "Whole Tumor",
                    "Enhancing Tumor",
                ],
                "input_spacing": (
                    1.0,
                    1.0,
                    1.0,
                ),
                "normalization": (
                    "nonzero=True, "
                    "channel_wise=True"
                ),
                "roi_size": (
                    240,
                    240,
                    160,
                ),
                "sw_batch_size": 1,
                "overlap": 0.5,
                "image_ids": image_ids,
            },
        }

        return output
