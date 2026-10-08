from pathlib import Path
from typing import Any

import numpy as np
import pydicom


class CTPreprocessingError(ValueError):
    """Raised when a CT DICOM series cannot be safely preprocessed."""


def _get_required(ds: Any, attribute: str) -> Any:
    value = getattr(ds, attribute, None)

    if value is None:
        raise CTPreprocessingError(
            f"Required DICOM attribute is missing: {attribute}"
        )

    return value


def _get_slice_position(ds: Any) -> np.ndarray:
    position = _get_required(ds, "ImagePositionPatient")

    if len(position) != 3:
        raise CTPreprocessingError(
            "ImagePositionPatient must contain exactly 3 values."
        )

    return np.asarray([float(value) for value in position], dtype=np.float64)


def _get_orientation(ds: Any) -> np.ndarray:
    orientation = _get_required(ds, "ImageOrientationPatient")

    if len(orientation) != 6:
        raise CTPreprocessingError(
            "ImageOrientationPatient must contain exactly 6 values."
        )

    return np.asarray(
        [float(value) for value in orientation],
        dtype=np.float64,
    )


def _validate_series(datasets: list[Any]) -> None:
    if not datasets:
        raise CTPreprocessingError("No DICOM files were found.")

    modalities = {
        str(getattr(ds, "Modality", "")).upper()
        for ds in datasets
    }

    if modalities != {"CT"}:
        raise CTPreprocessingError(
            f"Expected CT DICOM files, found modalities: {sorted(modalities)}"
        )

    series_uids = {
        getattr(ds, "SeriesInstanceUID", None)
        for ds in datasets
    }

    if None in series_uids:
        raise CTPreprocessingError(
            "One or more DICOM files are missing SeriesInstanceUID."
        )

    if len(series_uids) != 1:
        raise CTPreprocessingError(
            "Multiple SeriesInstanceUID values were found. "
            "Provide exactly one CT series."
        )

    rows = {
        int(_get_required(ds, "Rows"))
        for ds in datasets
    }

    columns = {
        int(_get_required(ds, "Columns"))
        for ds in datasets
    }

    if len(rows) != 1 or len(columns) != 1:
        raise CTPreprocessingError(
            "CT slices do not have consistent image dimensions."
        )

    pixel_spacings = {
        tuple(float(value) for value in _get_required(ds, "PixelSpacing"))
        for ds in datasets
    }

    if len(pixel_spacings) != 1:
        raise CTPreprocessingError(
            "CT slices do not have consistent PixelSpacing."
        )

    for spacing in next(iter(pixel_spacings)):
        if spacing <= 0:
            raise CTPreprocessingError(
                "PixelSpacing values must be positive."
            )

    orientations = {
        tuple(float(value) for value in _get_orientation(ds))
        for ds in datasets
    }

    if len(orientations) != 1:
        raise CTPreprocessingError(
            "CT slices do not have consistent ImageOrientationPatient."
        )


def _sort_datasets(datasets: list[Any]) -> list[Any]:
    positions = [
        _get_slice_position(ds)
        for ds in datasets
    ]

    orientation = _get_orientation(datasets[0])

    row_direction = orientation[:3]
    column_direction = orientation[3:]

    slice_direction = np.cross(
        row_direction,
        column_direction,
    )

    norm = np.linalg.norm(slice_direction)

    if norm == 0:
        raise CTPreprocessingError(
            "Invalid ImageOrientationPatient: row and column "
            "directions produce a zero slice direction."
        )

    slice_direction = slice_direction / norm

    projected_positions = [
        float(np.dot(position, slice_direction))
        for position in positions
    ]

    ordered = sorted(
        zip(projected_positions, datasets),
        key=lambda item: item[0],
    )

    return [dataset for _, dataset in ordered]


def _derive_slice_spacing(
    datasets: list[Any],
) -> float:
    if len(datasets) == 1:
        thickness = getattr(datasets[0], "SliceThickness", None)

        if thickness is None:
            raise CTPreprocessingError(
                "Cannot determine slice spacing from a single slice."
            )

        spacing = float(thickness)

        if spacing <= 0:
            raise CTPreprocessingError(
                "SliceThickness must be positive."
            )

        return spacing

    orientation = _get_orientation(datasets[0])

    row_direction = orientation[:3]
    column_direction = orientation[3:]

    slice_direction = np.cross(
        row_direction,
        column_direction,
    )

    norm = np.linalg.norm(slice_direction)

    if norm == 0:
        raise CTPreprocessingError(
            "Invalid slice orientation."
        )

    slice_direction = slice_direction / norm

    positions = [
        _get_slice_position(ds)
        for ds in datasets
    ]

    projected_positions = np.asarray(
        [
            float(np.dot(position, slice_direction))
            for position in positions
        ],
        dtype=np.float64,
    )

    spacings = np.abs(
        np.diff(projected_positions)
    )

    if np.any(spacings <= 0):
        raise CTPreprocessingError(
            "CT slices contain duplicate or invalid positions."
        )

    median_spacing = float(np.median(spacings))

    tolerance = max(
        0.01,
        median_spacing * 0.02,
    )

    if np.any(
        np.abs(spacings - median_spacing) > tolerance
    ):
        raise CTPreprocessingError(
            "CT slice spacing is inconsistent."
        )

    return median_spacing


def _convert_to_hu(
    datasets: list[Any],
) -> np.ndarray:
    first = datasets[0]

    rows = int(_get_required(first, "Rows"))
    columns = int(_get_required(first, "Columns"))

    volume = np.empty(
        (len(datasets), rows, columns),
        dtype=np.float32,
    )

    for index, ds in enumerate(datasets):
        if not hasattr(ds, "PixelData"):
            raise CTPreprocessingError(
                f"Missing PixelData in slice {index}."
            )

        pixel_array = ds.pixel_array

        if pixel_array.shape != (rows, columns):
            raise CTPreprocessingError(
                f"Slice {index} has shape {pixel_array.shape}; "
                f"expected {(rows, columns)}."
            )

        slope = float(
            getattr(ds, "RescaleSlope", 1.0)
        )

        intercept = float(
            getattr(ds, "RescaleIntercept", 0.0)
        )

        volume[index] = (
            pixel_array.astype(np.float32) * slope
            + intercept
        )

    return volume


def preprocess_ct_volume(
    series_dir: str | Path,
) -> dict[str, Any]:
    """
    Load and validate a single CT DICOM series.

    Returns:
        {
            "datasets": sorted DICOM datasets,
            "volume": HU volume,
            "voxel_spacing": (row, column, slice),
            "metadata": {...},
        }
    """

    series_path = Path(series_dir)

    if not series_path.exists():
        raise CTPreprocessingError(
            f"CT series directory does not exist: {series_path}"
        )

    if not series_path.is_dir():
        raise CTPreprocessingError(
            f"CT series path is not a directory: {series_path}"
        )

    files = sorted(series_path.rglob("*.dcm"))

    if not files:
        raise CTPreprocessingError(
            f"No .dcm files found in: {series_path}"
        )

    datasets = []

    for file_path in files:
        try:
            dataset = pydicom.dcmread(file_path)
        except Exception as exc:
            raise CTPreprocessingError(
                f"Unable to read DICOM file: {file_path}"
            ) from exc

        datasets.append(dataset)

    _validate_series(datasets)

    sorted_datasets = _sort_datasets(datasets)

    first = sorted_datasets[0]

    pixel_spacing = _get_required(
        first,
        "PixelSpacing",
    )

    row_spacing = float(pixel_spacing[0])
    column_spacing = float(pixel_spacing[1])

    slice_spacing = _derive_slice_spacing(
        sorted_datasets
    )

    volume = _convert_to_hu(
        sorted_datasets
    )

    orientation = _get_orientation(first)
    origin = _get_slice_position(first)

    metadata = {
        "modality": str(first.Modality),
        "body_region": getattr(
            first,
            "BodyPartExamined",
            None,
        ),
        "series_instance_uid": str(
            first.SeriesInstanceUID
        ),
        "rows": int(first.Rows),
        "columns": int(first.Columns),
        "slice_count": len(sorted_datasets),
        "image_orientation_patient": tuple(
            float(value)
            for value in orientation
        ),
        "image_position_patient": tuple(
            float(value)
            for value in origin
        ),
    }

    return {
        "datasets": sorted_datasets,
        "volume": volume,
        "voxel_spacing": (
            row_spacing,
            column_spacing,
            slice_spacing,
        ),
        "metadata": metadata,
    }