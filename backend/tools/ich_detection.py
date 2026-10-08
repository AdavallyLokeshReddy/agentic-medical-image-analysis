from typing import Any, Dict, Optional

import numpy as np
import torch

from .base import MedicalAITool


class ICHDetectionTool(MedicalAITool):
    """
    Registered intracranial hemorrhage detection tool.

    This tool wraps the official research model inference pipeline.

    Input:
        CT volume in Hounsfield Units.

        Shape:
            (slices, rows, columns)

    Output:
        Series-level probabilities for:

            epidural
            intraparenchymal
            intraventricular
            subarachnoid
            subdural
            any

    Important:
        This is a research/demo component.
        It is NOT a clinical diagnostic system.
    """

    name = "ich_detection"

    description = (
        "Detects suspected intracranial hemorrhage from a "
        "validated non-contrast head CT series."
    )

    LABELS = [
        "epidural",
        "intraparenchymal",
        "intraventricular",
        "subarachnoid",
        "subdural",
        "any",
    ]

    MODEL_REPO = (
        "ianpan/ct-head-hemorrhage-detection"
    )

    MODEL_VERSION = "research-model"

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: Optional[str] = None,
    ):
        """
        Initialize the research ICH model.

        Parameters
        ----------
        model_path:
            Reserved for future local model loading.

        device:
            "cuda", "cpu", or None for automatic selection.
        """

        self.model_path = model_path

        self.device = torch.device(
            device
            if device
            else (
                "cuda"
                if torch.cuda.is_available()
                else "cpu"
            )
        )

        self.model = None

        self._load_model()

    def _load_model(self):
        """
        Load the project's official research
        inference implementation.
        """

        try:
            from model_runtime.inference import (
                HemorrhageSliceModel
            )

        except ImportError as error:

            raise ImportError(
                "Could not import the research model "
                "inference implementation.\n\n"
                "Expected file:\n"
                "backend/model_runtime/inference.py"
            ) from error

        print(
            f"Loading ICH model on device: "
            f"{self.device}"
        )

        self.model = HemorrhageSliceModel()

        print(
            "ICH detection model loaded successfully."
        )

    def _validate_input(
        self,
        input_data: Dict[str, Any]
    ) -> np.ndarray:
        """
        Validate the CT volume supplied to the tool.

        The volume must:
        - Be supplied as a dictionary value named 'volume'
        - Be a NumPy array
        - Be three-dimensional
        - Contain at least one slice
        - Contain only finite values
        - Be represented in Hounsfield Units
        """

        if not isinstance(input_data, dict):
            raise ValueError(
                "Tool input must be a dictionary."
            )

        if "volume" not in input_data:
            raise ValueError(
                "Tool input must contain 'volume'."
            )

        volume = input_data["volume"]

        if not isinstance(volume, np.ndarray):
            raise ValueError(
                "CT volume must be a NumPy array."
            )

        if volume.ndim != 3:
            raise ValueError(
                "CT volume must have shape "
                "(slices, rows, columns)."
            )

        if volume.size == 0:
            raise ValueError(
                "CT volume cannot be empty."
            )

        if not np.isfinite(volume).all():
            raise ValueError(
                "CT volume contains non-finite values."
            )

        if volume.shape[0] < 1:
            raise ValueError(
                "CT volume must contain at least "
                "one slice."
            )

        return np.ascontiguousarray(
            volume,
            dtype=np.float32
        )

    def _run_model(
        self,
        volume: np.ndarray,
        batch_size: int = 4,
    ) -> Dict[str, Any]:
        """
        Run the official model's HU-volume inference.

        The official implementation performs its own
        model-specific preprocessing.

        Therefore the input must remain in
        Hounsfield Units.
        """

        if self.model is None:
            raise RuntimeError(
                "ICH detection model is not loaded."
            )

        output = self.model.predict_hu_volume(
            volume,
            batch_size=batch_size,
            return_segmentation=False,
        )

        if not isinstance(output, dict):
            raise ValueError(
                "Research model returned an unexpected "
                "output format."
            )

        return output

    @staticmethod
    def _convert_probabilities(
        values,
        labels,
    ) -> Dict[str, float]:
        """
        Convert model probabilities into normal
        Python floats so that they are JSON serializable.
        """

        values = np.asarray(
            values,
            dtype=np.float32
        )

        if values.ndim != 1:
            raise ValueError(
                "Expected a one-dimensional "
                "probability vector."
            )

        if len(values) != len(labels):
            raise ValueError(
                "Model output class count does not "
                "match expected ICH classes."
            )

        result = {}

        for index, label in enumerate(labels):

            probability = float(
                values[index]
            )

            if not np.isfinite(probability):
                raise ValueError(
                    f"Non-finite probability for "
                    f"{label}."
                )

            if not 0.0 <= probability <= 1.0:
                raise ValueError(
                    f"Invalid probability for "
                    f"{label}: {probability}"
                )

            result[label] = probability

        return result

    @staticmethod
    def _find_supporting_slices(
        slice_output,
        labels,
        top_k: int = 5,
    ) -> Dict[str, list]:
        """
        Find the slices with the highest predicted
        probability for each hemorrhage subtype.

        These values are model evidence/provenance.

        They are NOT independent clinical diagnoses.
        """

        if slice_output is None:
            return {}

        slice_array = np.asarray(
            slice_output,
            dtype=np.float32
        )

        if slice_array.ndim != 2:
            return {}

        if slice_array.shape[1] != len(labels):
            return {}

        evidence = {}

        for class_index, label in enumerate(labels):

            if label == "any":
                continue

            scores = slice_array[
                :,
                class_index
            ]

            if len(scores) == 0:
                evidence[label] = []
                continue

            valid_scores = np.isfinite(
                scores
            )

            valid_indices = np.where(
                valid_scores
            )[0]

            if len(valid_indices) == 0:
                evidence[label] = []
                continue

            count = min(
                top_k,
                len(valid_indices)
            )

            sorted_indices = valid_indices[
                np.argsort(
                    scores[valid_indices]
                )[-count:][::-1]
            ]

            evidence[label] = [
                {
                    "slice_index": int(index),
                    "probability": float(
                        scores[index]
                    ),
                }
                for index in sorted_indices
            ]

        return evidence

    @staticmethod
    def _get_prediction_label(
        any_probability: float
    ) -> str:
        """
        Convert the model's 'any hemorrhage'
        probability into a simple research/demo
        prediction label.

        The threshold is intentionally kept simple
        for the prototype. A future verification layer
        should apply validated thresholds and policies.
        """

        if any_probability >= 0.5:
            return "hemorrhage_detected"

        return "no_hemorrhage_detected"

    def run(
        self,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the ICH detection tool.
        """

        volume = self._validate_input(
            input_data
        )

        model_output = self._run_model(
            volume
        )

        if "series_classification" not in model_output:
            raise ValueError(
                "Research model did not return "
                "'series_classification'."
            )

        series_output = model_output[
            "series_classification"
        ]

        series_probabilities = (
            self._convert_probabilities(
                series_output,
                self.LABELS,
            )
        )

        subtype_probabilities = {
            label: series_probabilities[label]
            for label in self.LABELS
            if label != "any"
        }

        highest_subtype = max(
            subtype_probabilities,
            key=subtype_probabilities.get,
        )

        highest_probability = (
            subtype_probabilities[
                highest_subtype
            ]
        )

        any_probability = (
            series_probabilities["any"]
        )

        prediction_label = (
            self._get_prediction_label(
                any_probability
            )
        )

        hemorrhage_detected = (
            prediction_label
            == "hemorrhage_detected"
        )

        slice_output = model_output.get(
            "slice_classification"
        )

        supporting_slices = (
            self._find_supporting_slices(
                slice_output,
                self.LABELS,
            )
        )

        slice_prediction_count = None

        if slice_output is not None:

            slice_array = np.asarray(
                slice_output
            )

            if slice_array.ndim >= 1:
                slice_prediction_count = int(
                    slice_array.shape[0]
                )

        return {
            "tool": self.name,

            "status": "completed",

            "prediction": {
                "label":
                    prediction_label,

                "hemorrhage_detected":
                    hemorrhage_detected,

                "any_probability":
                    any_probability,

                "highest_probability_subtype":
                    highest_subtype,

                "highest_probability":
                    highest_probability,

                "subtypes":
                    subtype_probabilities,
            },

            "series": {
                "slice_count":
                    int(volume.shape[0]),

                "aggregation":
                    "research_model_contextual_series_prediction",

                "slice_prediction_count":
                    slice_prediction_count,

                "supporting_slices":
                    supporting_slices,
            },

            "input": {
                "volume_shape":
                    list(volume.shape),

                "data_type":
                    str(volume.dtype),

                "units":
                    "Hounsfield Units",
            },

            "evidence": {
                "model":
                    self.MODEL_REPO,

                "model_version":
                    self.MODEL_VERSION,

                "device":
                    str(self.device),

                "classes":
                    self.LABELS,
            },

            "verification_required":
                True,

            "clinical_use":
                "research_demo_only",

            "warnings": [
                "Research model output only.",
                "This result is not a clinical diagnosis.",
                "Human verification is required.",
            ],
        }