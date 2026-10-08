from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import torch
from monai.bundle import ConfigParser
from monai.data import MetaTensor
from monai.apps.detection.transforms.dictionary import (
    AffineBoxToWorldCoordinated,
    ClipBoxToImaged,
    ConvertBoxModed,
)
from monai.transforms import (
    Compose,
    EnsureChannelFirst,
    EnsureType,
    Orientation,
    ScaleIntensityRange,
    Spacing,
)

from tools.base import MedicalAITool


class LungNoduleDetectionTool(MedicalAITool):
    """
    Research/demo lung-nodule detection capability based on the
    official MONAI lung_nodule_ct_detection bundle.

    This tool is not clinically validated and must not be used
    for autonomous diagnosis or treatment.
    """

    # ---------------------------------------------------------
    # MedicalAITool interface
    # ---------------------------------------------------------

    name = "lung_nodule_detection"

    description = (
        "Research/demo lung nodule detection from chest CT "
        "using the MONAI RetinaNet LUNA16 model."
    )

    # ---------------------------------------------------------
    # Tool metadata
    # ---------------------------------------------------------

    TOOL_NAME = "lung_nodule_detection"

    TOOL_VERSION = "MONAI-lung_nodule_ct_detection"

    MODEL_NAME = "MONAI lung_nodule_ct_detection"

    MODEL_VERSION = TOOL_VERSION

    VERIFICATION_REQUIRED = True

    CLINICAL_USE = "research_demo_only"

    TARGET_SPACING = (
        0.703125,
        0.703125,
        1.25,
    )

    SCORE_THRESHOLD = 0.02

    NMS_THRESHOLD = 0.22

    MAX_DETECTIONS = 300

    INFER_PATCH_SIZE = (
        512,
        512,
        192,
    )

    OVERLAP = 0.25

    SW_BATCH_SIZE = 1

    # ---------------------------------------------------------
    # Constructor
    # ---------------------------------------------------------

    def __init__(
        self,
        bundle_dir: str | Path = (
            "models/monai/lung_nodule_ct_detection"
        ),
    ) -> None:

        self.bundle_dir = Path(
            bundle_dir
        ).resolve()

        # The official MONAI bundle references its own
        # local Python package:
        #
        #     scripts.detection_inferer.RetinaNetInferer
        #
        # Make the bundle root importable without modifying
        # the official MONAI bundle.

        if str(self.bundle_dir) not in sys.path:
            sys.path.insert(
                0,
                str(self.bundle_dir),
            )

        self.config_path = (
            self.bundle_dir
            / "configs"
            / "inference.json"
        )

        self.checkpoint_path = (
            self.bundle_dir
            / "models"
            / "model.pt"
        )

        if not self.config_path.exists():
            raise FileNotFoundError(
                "MONAI inference config not found: "
                f"{self.config_path}"
            )

        if not self.checkpoint_path.exists():
            raise FileNotFoundError(
                "MONAI checkpoint not found: "
                f"{self.checkpoint_path}"
            )

        self.device = torch.device(
            "cuda:0"
            if torch.cuda.is_available()
            else "cpu"
        )

        self.parser = ConfigParser()

        self.parser.read_config(
            str(self.config_path)
        )

        self.network = self._load_network()

        self.detector = self._configure_detector()

        self.inferer = self._configure_inferer()

        self.preprocessing = (
            self._configure_preprocessing()
        )

        self.postprocessing = (
            self._configure_postprocessing()
        )

    # ---------------------------------------------------------
    # Network
    # ---------------------------------------------------------

    def _load_network(
        self,
    ) -> torch.nn.Module:
        """
        Create the official RetinaNet architecture and load
        the official MONAI checkpoint.
        """

        network = self.parser.get_parsed_content(
            "network"
        )

        checkpoint = torch.load(
            self.checkpoint_path,
            map_location="cpu",
            weights_only=False,
        )

        network.load_state_dict(
            checkpoint
        )

        network.to(
            self.device
        )

        network.eval()

        return network

    # ---------------------------------------------------------
    # Detector configuration
    # ---------------------------------------------------------

    def _configure_detector(
        self,
    ) -> Any:
        """
        Configure the official MONAI RetinaNetDetector.
        """

        detector = self.parser.get_parsed_content(
            "detector"
        )

        detector.set_target_keys(
            box_key="box",
            label_key="label",
        )

        detector.set_box_selector_parameters(
            score_thresh=self.SCORE_THRESHOLD,
            topk_candidates_per_level=1000,
            nms_thresh=self.NMS_THRESHOLD,
            detections_per_img=self.MAX_DETECTIONS,
        )

        detector.set_sliding_window_inferer(
            roi_size=self.INFER_PATCH_SIZE,
            overlap=self.OVERLAP,
            sw_batch_size=self.SW_BATCH_SIZE,
            mode="constant",
            device="cpu",
        )

        return detector

    # ---------------------------------------------------------
    # Inferer
    # ---------------------------------------------------------

    def _configure_inferer(
        self,
    ) -> Any:
        """
        Build the official bundle-local RetinaNetInferer.
        """

        return self.parser.get_parsed_content(
            "inferer"
        )

    # ---------------------------------------------------------
    # Preprocessing
    # ---------------------------------------------------------

    def _configure_preprocessing(
        self,
    ) -> Compose:
        """
        Reproduce the official MONAI preprocessing sequence.

        Official bundle:

            EnsureChannelFirst
            Orientation -> RAS
            Spacing -> target spacing
            ScaleIntensityRange [-1024, 300] -> [0, 1]
            EnsureTyped
        """

        return Compose(
            [
                EnsureChannelFirst(
                    channel_dim="no_channel",
                ),
                Orientation(
                    axcodes="RAS",
                ),
                Spacing(
                    pixdim=self.TARGET_SPACING,
                    mode="bilinear",
                ),
                ScaleIntensityRange(
                    a_min=-1024.0,
                    a_max=300.0,
                    b_min=0.0,
                    b_max=1.0,
                    clip=True,
                ),
                EnsureType(),
            ]
        )

    # ---------------------------------------------------------
    # Postprocessing
    # ---------------------------------------------------------

    def _configure_postprocessing(
        self,
    ) -> Compose:
        """
        Reproduce the official MONAI lung-nodule
        postprocessing sequence.
        """

        return Compose(
            [
                ClipBoxToImaged(
                    box_keys="box",
                    label_keys="label",
                    box_ref_image_keys="image",
                ),
                AffineBoxToWorldCoordinated(
                    box_keys="box",
                    box_ref_image_keys="image",
                    affine_lps_to_ras=True,
                ),
                ConvertBoxModed(
                    box_keys="box",
                    src_mode="xyzxyz",
                    dst_mode="cccwhd",
                ),
            ]
        )

    # ---------------------------------------------------------
    # Input validation
    # ---------------------------------------------------------

    @staticmethod
    def validate_input(
        volume: np.ndarray,
        voxel_spacing: tuple[
            float,
            float,
            float,
        ],
        image_position_patient: tuple[
            float,
            float,
            float,
        ],
        image_orientation_patient: tuple[
            float,
            float,
            float,
            float,
            float,
            float,
        ],
    ) -> None:
        """
        Validate raw HU chest CT volume and DICOM geometry.
        """

        if not isinstance(
            volume,
            np.ndarray,
        ):
            raise TypeError(
                "volume must be a numpy.ndarray"
            )

        if volume.ndim != 3:
            raise ValueError(
                "Expected a 3D CT volume, "
                f"received {volume.ndim} dimensions."
            )

        if volume.size == 0:
            raise ValueError(
                "CT volume is empty."
            )

        if not np.isfinite(
            volume
        ).all():
            raise ValueError(
                "CT volume contains NaN or "
                "infinite values."
            )

        if len(voxel_spacing) != 3:
            raise ValueError(
                "voxel_spacing must contain "
                "exactly three values."
            )

        if any(
            float(value) <= 0
            for value in voxel_spacing
        ):
            raise ValueError(
                f"Invalid voxel spacing: "
                f"{voxel_spacing}"
            )

        if len(
            image_position_patient
        ) != 3:
            raise ValueError(
                "image_position_patient must contain "
                "exactly three values."
            )

        if not np.isfinite(
            np.asarray(
                image_position_patient,
                dtype=np.float64,
            )
        ).all():
            raise ValueError(
                "image_position_patient contains "
                "invalid values."
            )

        if len(
            image_orientation_patient
        ) != 6:
            raise ValueError(
                "image_orientation_patient must contain "
                "exactly six values."
            )

        if not np.isfinite(
            np.asarray(
                image_orientation_patient,
                dtype=np.float64,
            )
        ).all():
            raise ValueError(
                "image_orientation_patient contains "
                "invalid values."
            )

    # ---------------------------------------------------------
    # DICOM affine
    # ---------------------------------------------------------

    @staticmethod
    def _build_affine(
        voxel_spacing: tuple[
            float,
            float,
            float,
        ],
        image_position_patient: tuple[
            float,
            float,
            float,
        ],
        image_orientation_patient: tuple[
            float,
            float,
            float,
            float,
            float,
            float,
        ],
    ) -> np.ndarray:
        """
        Build a DICOM patient-coordinate affine for a volume
        stored as (D, H, W).

        DICOM ImageOrientationPatient contains:

            [row_x, row_y, row_z,
             col_x, col_y, col_z]

        Volume axes:

            D = slice axis
            H = image row
            W = image column

        The affine is initially expressed in DICOM
        LPS patient coordinates.
        """

        if len(
            image_position_patient
        ) != 3:
            raise ValueError(
                "image_position_patient must contain "
                "exactly three values."
            )

        if len(
            image_orientation_patient
        ) != 6:
            raise ValueError(
                "image_orientation_patient must contain "
                "exactly six values."
            )

        row_direction = np.asarray(
            image_orientation_patient[:3],
            dtype=np.float64,
        )

        column_direction = np.asarray(
            image_orientation_patient[3:],
            dtype=np.float64,
        )

        origin = np.asarray(
            image_position_patient,
            dtype=np.float64,
        )

        row_spacing = float(
            voxel_spacing[0]
        )

        column_spacing = float(
            voxel_spacing[1]
        )

        slice_spacing = float(
            voxel_spacing[2]
        )

        slice_direction = np.cross(
            row_direction,
            column_direction,
        )

        row_norm = np.linalg.norm(
            row_direction
        )

        column_norm = np.linalg.norm(
            column_direction
        )

        slice_norm = np.linalg.norm(
            slice_direction
        )

        if (
            row_norm == 0
            or column_norm == 0
            or slice_norm == 0
        ):
            raise ValueError(
                "Invalid DICOM orientation vectors."
            )

        row_direction = (
            row_direction / row_norm
        )

        column_direction = (
            column_direction / column_norm
        )

        slice_direction = (
            slice_direction / slice_norm
        )

        affine = np.eye(
            4,
            dtype=np.float64,
        )

        # Volume axis 0 = D
        affine[:3, 0] = (
            slice_direction
            * slice_spacing
        )

        # Volume axis 1 = H
        affine[:3, 1] = (
            row_direction
            * row_spacing
        )

        # Volume axis 2 = W
        affine[:3, 2] = (
            column_direction
            * column_spacing
        )

        # First slice origin
        affine[:3, 3] = origin

        return affine

    # ---------------------------------------------------------
    # Prepare model input
    # ---------------------------------------------------------

    def _prepare_input(
        self,
        volume: np.ndarray,
        voxel_spacing: tuple[
            float,
            float,
            float,
        ],
        image_position_patient: tuple[
            float,
            float,
            float,
        ],
        image_orientation_patient: tuple[
            float,
            float,
            float,
            float,
            float,
            float,
        ],
    ) -> MetaTensor:
        """
        Apply official MONAI preprocessing while preserving
        DICOM patient-space geometry.
        """

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
            volume.astype(
                np.float32,
                copy=False,
            ),
            affine=affine,
        )

        image = self.preprocessing(
            image
        )

        return image

    # ---------------------------------------------------------
    # Prediction extraction
    # ---------------------------------------------------------

    @staticmethod
    def _extract_prediction(
        prediction: Any,
    ) -> Any:
        """
        Convert tensor outputs to CPU NumPy arrays while
        preserving detector output structure.
        """

        if isinstance(
            prediction,
            list,
        ):
            return [
                LungNoduleDetectionTool._extract_prediction(
                    item
                )
                for item in prediction
            ]

        if not isinstance(
            prediction,
            dict,
        ):
            return prediction

        result: dict[str, Any] = {}

        for key, value in prediction.items():

            if torch.is_tensor(value):

                result[key] = (
                    value.detach()
                    .cpu()
                    .numpy()
                )

            elif isinstance(
                value,
                list,
            ):

                converted = []

                for item in value:

                    if torch.is_tensor(
                        item
                    ):
                        converted.append(
                            item.detach()
                            .cpu()
                            .numpy()
                        )
                    else:
                        converted.append(
                            item
                        )

                result[key] = converted

            else:
                result[key] = value

        return result

    # ---------------------------------------------------------
    # Main prediction method
    # ---------------------------------------------------------

    def predict(
        self,
        volume: np.ndarray,
        voxel_spacing: tuple[
            float,
            float,
            float,
        ],
        image_position_patient: tuple[
            float,
            float,
            float,
        ],
        image_orientation_patient: tuple[
            float,
            float,
            float,
            float,
            float,
            float,
        ],
    ) -> dict[str, Any]:
        """
        Run official MONAI lung-nodule detection.

        The result remains structured so the orchestrator
        can later convert it into an EvidenceItem with
        provenance and verification state.
        """

        self.validate_input(
            volume=volume,
            voxel_spacing=voxel_spacing,
            image_position_patient=(
                image_position_patient
            ),
            image_orientation_patient=(
                image_orientation_patient
            ),
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

        # MONAI preprocessing:
        #
        #     (C, D, H, W)
        #
        # RetinaNet expects:
        #
        #     (B, C, D, H, W)

        model_input = model_input.unsqueeze(
            0
        )

        model_input = model_input.to(
            self.device
        )

        with torch.no_grad():

            prediction = self.inferer(
                model_input,
                self.network,
            )

        # RetinaNetDetector returns:
        #
        #     List[Dict[str, Tensor]]

        postprocessed_predictions = []

        for detection in prediction:

            postprocess_data = {
                "image": model_input[0],
                **detection,
            }

            postprocess_data = (
                self.postprocessing(
                    postprocess_data
                )
            )

            postprocessed_predictions.append(
                {
                    key: value
                    for key, value
                    in postprocess_data.items()
                    if key != "image"
                }
            )

        prediction = (
            self._extract_prediction(
                postprocessed_predictions
            )
        )

        return {
            "tool_name": self.TOOL_NAME,
            "tool_version": self.TOOL_VERSION,
            "clinical_use": self.CLINICAL_USE,
            "model_name": self.MODEL_NAME,
            "model_version": self.MODEL_VERSION,
            "verification_required": self.VERIFICATION_REQUIRED,
            "device": str(
                self.device
            ),
            "input_shape": tuple(
                int(value)
                for value in volume.shape
            ),
            "input_spacing": tuple(
                float(value)
                for value in voxel_spacing
            ),
            "image_position_patient": tuple(
                float(value)
                for value
                in image_position_patient
            ),
            "image_orientation_patient": tuple(
                float(value)
                for value
                in image_orientation_patient
            ),
            "target_spacing": self.TARGET_SPACING,
            "score_threshold": self.SCORE_THRESHOLD,
            "nms_threshold": self.NMS_THRESHOLD,
            "max_detections": self.MAX_DETECTIONS,
            "prediction": prediction,
            "warnings": [
                "Research/demo output only.",
                (
                    "This model was trained and evaluated "
                    "in the LUNA16 research setting."
                ),
                (
                    "This system has not clinically "
                    "validated this model."
                ),
                "Detection output requires verification.",
                (
                    "Output must not be used for autonomous "
                    "diagnosis or treatment."
                ),
            ],
        }

    # ---------------------------------------------------------
    # MedicalAITool public interface
    # ---------------------------------------------------------

    def run(
        self,
        input_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute the registered lung-nodule detection tool.

        Expected input_data:

            {
                "volume": np.ndarray,
                "voxel_spacing": (...),
                "image_position_patient": (...),
                "image_orientation_patient": (...),
            }
        """

        if not isinstance(
            input_data,
            dict,
        ):
            raise TypeError(
                "input_data must be a dictionary."
            )

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
            raise ValueError(
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


        )