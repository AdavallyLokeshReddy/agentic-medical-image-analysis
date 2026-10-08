from pathlib import Path

import numpy as np
import pytest

from preprocessing.chest_ct_preprocessing import preprocess_chest_ct_series
from tools.lung_nodule_detection import LungNoduleDetectionTool


CASE_DIR = Path("uploads/CASE-LUNG-0001/series")


@pytest.fixture(scope="module")
def chest_ct():
    """
    Load the engineering-test chest CT series once for this test module.
    """
    if not CASE_DIR.exists():
        pytest.skip(f"Test CT series not found: {CASE_DIR}")

    result = preprocess_chest_ct_series(CASE_DIR)

    return result


@pytest.fixture(scope="module")
def cropped_ct(chest_ct):
    """
    Use a controlled 80-slice crop to keep CPU inference practical.

    IMPORTANT:
    The ImagePositionPatient used for the crop must correspond to
    the first slice in the cropped volume.
    """
    datasets = chest_ct["datasets"]

    start = 80
    end = 160

    volume = chest_ct["volume"][start:end]

    image_position_patient = tuple(
        float(value) for value in datasets[start].ImagePositionPatient
    )

    image_orientation_patient = tuple(
        float(value) for value in datasets[start].ImageOrientationPatient
    )

    return {
        "volume": volume,
        "voxel_spacing": chest_ct["voxel_spacing"],
        "image_position_patient": image_position_patient,
        "image_orientation_patient": image_orientation_patient,
    }


@pytest.fixture(scope="module")
def tool():
    """
    Initialize the actual MONAI lung-nodule detection tool once.
    """
    return LungNoduleDetectionTool()


@pytest.fixture(scope="module")
def prediction(tool, cropped_ct):
    """
    Run one real CPU inference and reuse its result across tests.
    """
    return tool.predict(
        volume=cropped_ct["volume"],
        voxel_spacing=cropped_ct["voxel_spacing"],
        image_position_patient=cropped_ct["image_position_patient"],
        image_orientation_patient=cropped_ct["image_orientation_patient"],
    )


def test_tool_initializes(tool):
    """
    Regression test:
    The official MONAI bundle must load and the tool must initialize.
    """
    assert tool is not None
    assert tool.network is not None
    assert tool.postprocessing is not None


def test_tool_uses_expected_bundle(tool):
    """
    Regression test:
    Make sure we are using the intended official lung-nodule bundle.
    """
    bundle_path = Path(tool.bundle_dir)

    assert bundle_path.exists()
    assert (bundle_path / "configs" / "inference.json").exists()
    assert (bundle_path / "models" / "model.pt").exists()


def test_preprocessed_test_volume(cropped_ct):
    """
    Regression test:
    The CT preprocessing pipeline must produce a valid 3D HU volume.
    """
    volume = cropped_ct["volume"]

    assert isinstance(volume, np.ndarray)
    assert volume.ndim == 3
    assert volume.shape[0] == 80
    assert volume.shape[1:] == (512, 512)
    assert volume.dtype == np.float32

    assert np.isfinite(volume).all()


def test_voxel_spacing_is_valid(cropped_ct):
    """
    Regression test:
    The spacing passed to the model must contain valid positive values.
    """
    spacing = cropped_ct["voxel_spacing"]

    assert len(spacing) == 3
    assert all(float(value) > 0 for value in spacing)


def test_crop_origin_matches_crop_start(chest_ct, cropped_ct):
    """
    Regression test:
    World-coordinate origin must come from the first slice of the crop,
    not from the first slice of the original full series.
    """
    datasets = chest_ct["datasets"]

    expected_origin = tuple(
        float(value) for value in datasets[80].ImagePositionPatient
    )

    assert cropped_ct["image_position_patient"] == expected_origin


def test_prediction_is_returned(prediction):
    """
    Regression test:
    Real inference must return the expected prediction container.
    """
    assert "prediction" in prediction
    assert isinstance(prediction["prediction"], list)


def test_prediction_contains_detection_dictionary(prediction):
    """
    Regression test:
    RetinaNet evaluation returns a list containing detection dictionaries.
    """
    detections = prediction["prediction"]

    assert len(detections) >= 1
    assert isinstance(detections[0], dict)


def test_prediction_contains_expected_keys(prediction):
    """
    Regression test:
    Postprocessing must preserve the detection information required
    by the governed medical-imaging platform.
    """
    detection = prediction["prediction"][0]

    assert "box" in detection
    assert "label" in detection
    assert "label_scores" in detection


def test_prediction_arrays_are_numpy(prediction):
    """
    Regression test:
    Predictions should be converted to NumPy arrays before being
    exposed by the tool.
    """
    detection = prediction["prediction"][0]

    assert isinstance(detection["box"], np.ndarray)
    assert isinstance(detection["label"], np.ndarray)
    assert isinstance(detection["label_scores"], np.ndarray)


def test_prediction_boxes_have_cccwhd_shape(prediction):
    """
    Regression test:
    Bounding boxes must be represented as:
        center_x, center_y, center_z,
        width, height, depth

    This protects the ConvertBoxMode postprocessing step.
    """
    detection = prediction["prediction"][0]

    boxes = detection["box"]

    assert boxes.ndim == 2
    assert boxes.shape[1] == 6


def test_prediction_lengths_match(prediction):
    """
    Regression test:
    Every predicted box must have exactly one label and one score.
    """
    detection = prediction["prediction"][0]

    boxes = detection["box"]
    labels = detection["label"]
    scores = detection["label_scores"]

    assert len(boxes) == len(labels)
    assert len(boxes) == len(scores)


def test_prediction_scores_are_valid(prediction):
    """
    Regression test:
    Detection confidence scores must remain within [0, 1].
    """
    scores = prediction["prediction"][0]["label_scores"]

    assert np.isfinite(scores).all()
    assert np.all(scores >= 0.0)
    assert np.all(scores <= 1.0)


def test_prediction_labels_are_valid(prediction):
    """
    Regression test:
    The official lung-nodule model currently uses class label 0.
    """
    labels = prediction["prediction"][0]["label"]

    assert np.isfinite(labels).all()
    assert np.all(labels >= 0)


def test_prediction_boxes_are_finite(prediction):
    """
    Regression test:
    Postprocessed world-coordinate boxes must contain finite values.
    """
    boxes = prediction["prediction"][0]["box"]

    assert np.isfinite(boxes).all()


def test_prediction_box_dimensions_are_positive(prediction):
    """
    Regression test:
    Width, height and depth must be positive after box conversion.
    """
    boxes = prediction["prediction"][0]["box"]

    if len(boxes) == 0:
        pytest.skip("No detections were produced by this test inference.")

    dimensions = boxes[:, 3:6]

    assert np.all(dimensions > 0)


def test_real_inference_produces_expected_known_output_shape(prediction):
    """
    Regression test for the exact integration path that previously broke.

    This specifically protects against:
    - treating the prediction list as a dictionary
    - passing the full batched model input to 3D box postprocessing
    - losing the postprocessed box representation
    """
    detection = prediction["prediction"][0]

    assert detection["box"].shape[1] == 6
    assert detection["label"].ndim == 1
    assert detection["label_scores"].ndim == 1


def test_tool_metadata_in_prediction(prediction):
    """
    Regression test:
    The structured tool output must identify this capability as
    research/demo functionality.
    """
    assert prediction["tool_name"] == "lung_nodule_detection"

    assert prediction["tool_version"] == (
        "MONAI-lung_nodule_ct_detection"
    )

    assert prediction["clinical_use"] == "research_demo_only"


def test_prediction_contains_safety_warnings(prediction):
    """
    Regression test:
    The structured tool output must retain safety warnings stating
    that the result requires verification and is not for autonomous
    diagnosis or treatment.
    """
    warnings = prediction["warnings"]

    assert isinstance(warnings, list)
    assert len(warnings) > 0

    warning_text = " ".join(
        str(warning)
        for warning in warnings
    ).lower()

    assert "research/demo" in warning_text
    assert "verification" in warning_text
    assert "autonomous" in warning_text

