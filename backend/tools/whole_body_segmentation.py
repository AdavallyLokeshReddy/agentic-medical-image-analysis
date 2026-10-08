from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import numpy as np
import torch
from monai.data import MetaTensor
from monai.networks.nets import SegResNet
from monai.inferers import SlidingWindowInferer
from monai.transforms import (
    Compose,
    EnsureType,
    Orientation,
    ScaleIntensity,
    Spacing,
)

from preprocessing.ct_volume_preprocessing import preprocess_ct_volume
from tools.base import MedicalAITool


class WholeBodySegmentationError(RuntimeError):
    """Raised when whole-body CT segmentation cannot be completed."""


class WholeBodySegmentationTool(MedicalAITool):
    """
    Governed research/demo whole-body CT segmentation tool.

    This tool wraps the official MONAI wholeBody_ct_segmentation
    SegResNet model.

    The model predicts 105 classes:
        0   = background
        1-104 = anatomical structures

    This is a research/demo capability only.
    It is not a diagnostic system and must not be used to make
    autonomous clinical decisions or treatment decisions.
    """

    name = "whole_body_segmentation"

    description = (
        "Research/demo whole-body anatomical segmentation from CT "
        "using the MONAI wholeBody_ct_segmentation SegResNet model."
    )

    TOOL_VERSION = "research-demo-1.0"

    MODEL_NAME = "MONAI wholeBody_ct_segmentation"
    MODEL_VERSION = "0.2.7"

    VERIFICATION_REQUIRED = True
    CLINICAL_USE = "research_demo_only"

    ROI_SIZE = (96, 96, 96)
    SW_BATCH_SIZE = 1
    SW_OVERLAP = 0.25

    # Official whole-body bundle label map.
    LABELS = {
        0: "background",
        1: "spleen",
        2: "kidney_right",
        3: "kidney_left",
        4: "gallbladder",
        5: "liver",
        6: "stomach",
        7: "aorta",
        8: "inferior_vena_cava",
        9: "portal_vein_and_splenic_vein",
        10: "pancreas",
        11: "adrenal_gland_right",
        12: "adrenal_gland_left",
        13: "lung_upper_lobe_left",
        14: "lung_lower_lobe_left",
        15: "lung_upper_lobe_right",
        16: "lung_middle_lobe_right",
        17: "lung_lower_lobe_right",
        18: "vertebrae_L5",
        19: "vertebrae_L4",
        20: "vertebrae_L3",
        21: "vertebrae_L2",
        22: "vertebrae_L1",
        23: "vertebrae_T12",
        24: "vertebrae_T11",
        25: "vertebrae_T10",
        26: "vertebrae_T9",
        27: "vertebrae_T8",
        28: "vertebrae_T7",
        29: "vertebrae_T6",
        30: "vertebrae_T5",
        31: "vertebrae_T4",
        32: "vertebrae_T3",
        33: "vertebrae_T2",
        34: "vertebrae_T1",
        35: "vertebrae_C7",
        36: "vertebrae_C6",
        37: "vertebrae_C5",
        38: "vertebrae_C4",
        39: "vertebrae_C3",
        40: "vertebrae_C2",
        41: "vertebrae_C1",
        42: "esophagus",
        43: "trachea",
        44: "heart_myocardium",
        45: "heart_atrium_left",
        46: "heart_ventricle_left",
        47: "heart_atrium_right",
        48: "heart_ventricle_right",
        49: "pulmonary_artery",
        50: "brain",
        51: "iliac_artery_left",
        52: "iliac_artery_right",
        53: "iliac_vena_left",
        54: "iliac_vena_right",
        55: "small_bowel",
        56: "duodenum",
        57: "colon",
        58: "rib_left_1",
        59: "rib_left_2",
        60: "rib_left_3",
        61: "rib_left_4",
        62: "rib_left_5",
        63: "rib_left_6",
        64: "rib_left_7",
        65: "rib_left_8",
        66: "rib_left_9",
        67: "rib_left_10",
        68: "rib_left_11",
        69: "rib_left_12",
        70: "rib_right_1",
        71: "rib_right_2",
        72: "rib_right_3",
        73: "rib_right_4",
        74: "rib_right_5",
        75: "rib_right_6",
        76: "rib_right_7",
        77: "rib_right_8",
        78: "rib_right_9",
        79: "rib_right_10",
        80: "rib_right_11",
        81: "rib_right_12",
        82: "humerus_left",
        83: "humerus_right",
        84: "scapula_left",
        85: "scapula_right",
        86: "clavicula_left",
        87: "clavicula_right",
        88: "femur_left",
        89: "femur_right",
        90: "hip_left",
        91: "hip_right",
        92: "sacrum",
        93: "face",
        94: "gluteus_maximus_left",
        95: "gluteus_maximus_right",
        96: "gluteus_medius_left",
        97: "gluteus_medius_right",
        98: "gluteus_minimus_left",
        99: "gluteus_minimus_right",
        100: "autochthon_left",
        101: "autochthon_right",
        102: "iliopsoas_left",
        103: "iliopsoas_right",
        104: "urinary_bladder",
    }

    def __init__(
        self,
        bundle_dir: str = "models/monai/wholeBody_ct_segmentation",
        device: Optional[str] = None,
    ) -> None:
        self.bundle_dir = Path(bundle_dir)

        if not self.bundle_dir.exists():
            raise WholeBodySegmentationError(
                f"Whole-body bundle directory does not exist: "
                f"{self.bundle_dir}"
            )

        self.model_path = self.bundle_dir / "models" / "model.pt"

        if not self.model_path.exists():
            raise WholeBodySegmentationError(
                f"Whole-body model weights not found: {self.model_path}"
            )

        if device is None:
            self.device = torch.device(
                "cuda" if torch.cuda.is_available() else "cpu"
            )
        else:
            self.device = torch.device(device)

        self.network = self._build_network()
        self.inferer = SlidingWindowInferer(
            roi_size=self.ROI_SIZE,
            sw_batch_size=self.SW_BATCH_SIZE,
            overlap=self.SW_OVERLAP,
            padding_mode="replicate",
            mode="gaussian",
        )

    def _build_network(self) -> SegResNet:
        network = SegResNet(
            spatial_dims=3,
            in_channels=1,
            out_channels=105,
            init_filters=32,
            blocks_down=[1, 2, 2, 4],
            blocks_up=[1, 1, 1],
            dropout_prob=0.2,
        ).to(self.device)

        checkpoint = torch.load(
            self.model_path,
            map_location=self.device,
            weights_only=False,
        )

        if not isinstance(checkpoint, dict):
            raise WholeBodySegmentationError(
                "Unexpected checkpoint format. Expected a state dictionary."
            )

        # The downloaded MONAI bundle currently contains the raw
        # SegResNet state dictionary.
        state_dict = checkpoint.get(
            "state_dict",
            checkpoint.get("model", checkpoint),
        )

        result = network.load_state_dict(
            state_dict,
            strict=True,
        )

        if result.missing_keys or result.unexpected_keys:
            raise WholeBodySegmentationError(
                "Whole-body model checkpoint did not load cleanly: "
                f"missing={result.missing_keys}, "
                f"unexpected={result.unexpected_keys}"
            )

        network.eval()

        return network

    @staticmethod
    def _validate_volume(
        volume: np.ndarray,
        voxel_spacing: Sequence[float],
    ) -> None:
        if not isinstance(volume, np.ndarray):
            raise WholeBodySegmentationError(
                "CT volume must be a numpy.ndarray."
            )

        if volume.ndim != 3:
            raise WholeBodySegmentationError(
                f"CT volume must be 3D, got shape {volume.shape}."
            )

        if volume.size == 0:
            raise WholeBodySegmentationError(
                "CT volume is empty."
            )

        if not np.isfinite(volume).all():
            raise WholeBodySegmentationError(
                "CT volume contains non-finite values."
            )

        if len(voxel_spacing) != 3:
            raise WholeBodySegmentationError(
                "voxel_spacing must contain exactly three values."
            )

        if not all(
            np.isfinite(float(value)) and float(value) > 0
            for value in voxel_spacing
        ):
            raise WholeBodySegmentationError(
                f"Invalid voxel spacing: {voxel_spacing}"
            )

    @staticmethod
    def _build_affine(
        voxel_spacing: Sequence[float],
        image_orientation_patient: Sequence[float],
        image_position_patient: Sequence[float],
    ) -> np.ndarray:
        if len(image_orientation_patient) != 6:
            raise WholeBodySegmentationError(
                "image_orientation_patient must contain six values."
            )

        if len(image_position_patient) != 3:
            raise WholeBodySegmentationError(
                "image_position_patient must contain three values."
            )

        spacing = np.asarray(
            voxel_spacing,
            dtype=np.float64,
        )

        iop = np.asarray(
            image_orientation_patient,
            dtype=np.float64,
        )

        ipp = np.asarray(
            image_position_patient,
            dtype=np.float64,
        )

        if not np.isfinite(iop).all():
            raise WholeBodySegmentationError(
                "image_orientation_patient contains non-finite values."
            )

        if not np.isfinite(ipp).all():
            raise WholeBodySegmentationError(
                "image_position_patient contains non-finite values."
            )

        row_spacing = float(spacing[0])
        column_spacing = float(spacing[1])
        slice_spacing = float(spacing[2])

        row_dir = iop[:3]
        col_dir = iop[3:]

        slice_dir = np.cross(row_dir, col_dir)

        if np.linalg.norm(row_dir) == 0:
            raise WholeBodySegmentationError(
                "Invalid row direction in image orientation."
            )

        if np.linalg.norm(col_dir) == 0:
            raise WholeBodySegmentationError(
                "Invalid column direction in image orientation."
            )

        if np.linalg.norm(slice_dir) == 0:
            raise WholeBodySegmentationError(
                "Invalid slice direction derived from image orientation."
            )

        affine = np.eye(4, dtype=np.float64)

        # Existing preprocessing produces volume axes as:
        #   axis 0 = slice
        #   axis 1 = row
        #   axis 2 = column
        affine[:3, 0] = slice_dir * slice_spacing
        affine[:3, 1] = row_dir * row_spacing
        affine[:3, 2] = col_dir * column_spacing
        affine[:3, 3] = ipp

        return affine

    def _preprocess(
        self,
        volume: np.ndarray,
        voxel_spacing: Sequence[float],
        image_orientation_patient: Sequence[float],
        image_position_patient: Sequence[float],
    ) -> MetaTensor:
        self._validate_volume(
            volume,
            voxel_spacing,
        )

        affine = self._build_affine(
            voxel_spacing,
            image_orientation_patient,
            image_position_patient,
        )

        image = MetaTensor(
            torch.from_numpy(
                volume.astype(np.float32, copy=False)
            )[None],
            affine=torch.from_numpy(affine).double(),
        )

        preprocessing = Compose(
            [
                Orientation(axcodes="RAS"),
                Spacing(
                    pixdim=(1.5, 1.5, 1.5),
                    mode="bilinear",
                ),
                ScaleIntensity(
                    minv=-1.0,
                    maxv=1.0,
                ),
                EnsureType(),
            ]
        )

        processed = preprocessing(image)

        if processed.ndim != 4:
            raise WholeBodySegmentationError(
                f"Preprocessed CT must be 4D (C,D,H,W), "
                f"got {tuple(processed.shape)}."
            )

        if processed.shape[0] != 1:
            raise WholeBodySegmentationError(
                f"Preprocessed CT must have one channel, "
                f"got {processed.shape[0]}."
            )

        if not torch.isfinite(processed).all():
            raise WholeBodySegmentationError(
                "Preprocessed CT contains non-finite values."
            )

        return processed

    def _summarize_segmentation(
        self,
        segmentation: torch.Tensor,
    ) -> Dict[str, Dict[str, Any]]:
        unique_labels, voxel_counts = torch.unique(
            segmentation,
            return_counts=True,
        )

        summary: Dict[str, Dict[str, Any]] = {}

        for label, count in zip(
            unique_labels.cpu().tolist(),
            voxel_counts.cpu().tolist(),
        ):
            label_id = int(label)

            if label_id not in self.LABELS:
                raise WholeBodySegmentationError(
                    f"Invalid predicted label: {label_id}"
                )

            summary[str(label_id)] = {
                "label_id": label_id,
                "name": self.LABELS[label_id],
                "voxel_count": int(count),
            }

        return summary

    def _run_inference(
        self,
        processed: MetaTensor,
    ) -> torch.Tensor:
        input_tensor = processed.unsqueeze(0).to(self.device)

        with torch.inference_mode():
            logits = self.inferer(
                input_tensor,
                self.network,
            )

        if logits.ndim != 5:
            raise WholeBodySegmentationError(
                f"Model output must be 5D, got {tuple(logits.shape)}."
            )

        if logits.shape[1] != 105:
            raise WholeBodySegmentationError(
                f"Model output must contain 105 classes, "
                f"got {logits.shape[1]}."
            )

        if not torch.isfinite(logits).all():
            raise WholeBodySegmentationError(
                "Model produced non-finite logits."
            )

        segmentation = torch.argmax(
            torch.softmax(logits, dim=1),
            dim=1,
        )

        if segmentation.ndim != 4:
            raise WholeBodySegmentationError(
                "Segmentation output must be 4D "
                "(batch, depth, height, width)."
            )

        if not torch.all(
            (segmentation >= 0) & (segmentation <= 104)
        ):
            raise WholeBodySegmentationError(
                "Segmentation contains labels outside 0-104."
            )

        return segmentation

    def predict(
        self,
        volume: np.ndarray,
        voxel_spacing: Sequence[float],
        image_orientation_patient: Sequence[float],
        image_position_patient: Sequence[float],
    ) -> Dict[str, Any]:
        processed = self._preprocess(
            volume=volume,
            voxel_spacing=voxel_spacing,
            image_orientation_patient=image_orientation_patient,
            image_position_patient=image_position_patient,
        )

        segmentation = self._run_inference(processed)

        segmentation_cpu = segmentation[0].detach().cpu().numpy().astype(
            np.uint8,
            copy=False,
        )

        label_summary = self._summarize_segmentation(
            segmentation[0]
        )

        return {
            "prediction": segmentation_cpu,
            "input_shape": tuple(int(x) for x in volume.shape),
            "processed_shape": tuple(
                int(x) for x in processed.shape
            ),
            "prediction_shape": tuple(
                int(x) for x in segmentation_cpu.shape
            ),
            "voxel_spacing": tuple(
                float(x) for x in voxel_spacing
            ),
            "model_input_spacing": (1.5, 1.5, 1.5),
            "label_summary": label_summary,
            "label_count": len(label_summary),
            "tool": self.name,
            "tool_version": self.TOOL_VERSION,
            "model_name": self.MODEL_NAME,
            "model_version": self.MODEL_VERSION,
            "runtime": str(self.device),
            "verification_required": self.VERIFICATION_REQUIRED,
            "clinical_use": self.CLINICAL_USE,
            "warnings": [
                "Research/demo segmentation only.",
                "This model is not a diagnostic system.",
                "Segmentation outputs require human clinical verification.",
                "Model outputs must not be used for autonomous "
                "treatment or irreversible clinical action.",
                "The official MONAI bundle is an example model and "
                "is not intended for diagnostic use.",
            ],
            "provenance": {
                "bundle": "wholeBody_ct_segmentation",
                "bundle_version": "0.2.7",
                "architecture": "SegResNet",
                "roi_size": self.ROI_SIZE,
                "sw_batch_size": self.SW_BATCH_SIZE,
                "sw_overlap": self.SW_OVERLAP,
                "resampling_spacing": (1.5, 1.5, 1.5),
                "orientation": "RAS",
                "output_classes": 105,
            },
        }

    def predict_from_dicom(
        self,
        series_dir: str,
    ) -> Dict[str, Any]:
        series_path = Path(series_dir)

        if not series_path.exists():
            raise WholeBodySegmentationError(
                f"CT series directory does not exist: {series_path}"
            )

        result = preprocess_ct_volume(str(series_path))

        metadata = result["metadata"]

        return self.predict(
            volume=result["volume"],
            voxel_spacing=result["voxel_spacing"],
            image_orientation_patient=metadata[
                "image_orientation_patient"
            ],
            image_position_patient=metadata[
                "image_position_patient"
            ],
        )

    def run(
        self,
        input_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not isinstance(input_data, dict):
            raise WholeBodySegmentationError(
                "input_data must be a dictionary."
            )

        volume = input_data.get("volume")
        voxel_spacing = input_data.get("voxel_spacing")
        image_orientation_patient = input_data.get(
            "image_orientation_patient"
        )
        image_position_patient = input_data.get(
            "image_position_patient"
        )

        if volume is None:
            raise WholeBodySegmentationError(
                "Missing required input: volume"
            )

        if voxel_spacing is None:
            raise WholeBodySegmentationError(
                "Missing required input: voxel_spacing"
            )

        if image_orientation_patient is None:
            raise WholeBodySegmentationError(
                "Missing required input: image_orientation_patient"
            )

        if image_position_patient is None:
            raise WholeBodySegmentationError(
                "Missing required input: image_position_patient"
            )

        return self.predict(
            volume=volume,
            voxel_spacing=voxel_spacing,
            image_orientation_patient=image_orientation_patient,
            image_position_patient=image_position_patient,
        )