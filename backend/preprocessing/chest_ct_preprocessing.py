from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pydicom


def _get_required(dataset: pydicom.Dataset, name: str) -> Any:
    """Return a required DICOM attribute or raise a clear error."""
    value = getattr(dataset, name, None)

    if value is None:
        raise ValueError(f"Required DICOM attribute is missing: {name}")

    return value


def _get_z_position(dataset: pydicom.Dataset) -> float:
    """Get the physical Z position of a CT slice."""
    position = getattr(dataset, "ImagePositionPatient", None)

    if position is None or len(position) < 3:
        raise ValueError(
            "ImagePositionPatient with a valid Z coordinate is required."
        )

    return float(position[2])


def _convert_to_hu(
    pixel_array: np.ndarray,
    dataset: pydicom.Dataset,
) -> np.ndarray:
    """Convert stored CT pixel values to Hounsfield Units."""
    slope = float(getattr(dataset, "RescaleSlope", 1.0))
    intercept = float(getattr(dataset, "RescaleIntercept", 0.0))

    hu = pixel_array.astype(np.float32) * slope + intercept

    return hu


def preprocess_chest_ct_series(
    series_directory: str | Path,
) -> dict[str, Any]:
    """
    Load and preprocess a chest CT DICOM series.

    The returned volume is in:
        (slices, rows, columns)

    Pixel values are converted to Hounsfield Units.

    This function performs technical preprocessing only.
    It does not perform lung segmentation, windowing, diagnosis,
    or model inference.
    """
    series_directory = Path(series_directory)

    if not series_directory.exists():
        raise FileNotFoundError(
            f"CT series directory does not exist: {series_directory}"
        )

    if not series_directory.is_dir():
        raise NotADirectoryError(
            f"Expected a directory: {series_directory}"
        )

    dicom_files = sorted(series_directory.glob("*.dcm"))

    if not dicom_files:
        raise ValueError(
            f"No DICOM files found in: {series_directory}"
        )

    datasets: list[tuple[Path, pydicom.Dataset]] = []

    for file_path in dicom_files:
        try:
            dataset = pydicom.dcmread(file_path)
        except Exception as exc:
            raise ValueError(
                f"Unable to read DICOM file: {file_path}"
            ) from exc

        datasets.append((file_path, dataset))

    # ------------------------------------------------------------------
    # Basic series validation
    # ------------------------------------------------------------------

    modalities = {
        str(getattr(dataset, "Modality", "")).upper()
        for _, dataset in datasets
    }

    if modalities != {"CT"}:
        raise ValueError(
            f"Expected CT DICOM files, found modalities: {modalities}"
        )

    body_regions = {
        str(getattr(dataset, "BodyPartExamined", "")).upper()
        for _, dataset in datasets
        if getattr(dataset, "BodyPartExamined", None) is not None
    }

    if body_regions and not any(
        region in {"CHEST", "LUNG", "THORAX"}
        for region in body_regions
    ):
        raise ValueError(
            f"Expected chest/lung CT data, found body regions: {body_regions}"
        )

    series_uids = {
        str(_get_required(dataset, "SeriesInstanceUID"))
        for _, dataset in datasets
    }

    if len(series_uids) != 1:
        raise ValueError(
            "DICOM directory contains multiple SeriesInstanceUID values."
        )

    series_uid = next(iter(series_uids))

    # ------------------------------------------------------------------
    # Geometry validation
    # ------------------------------------------------------------------

    rows = {
        int(_get_required(dataset, "Rows"))
        for _, dataset in datasets
    }

    columns = {
        int(_get_required(dataset, "Columns"))
        for _, dataset in datasets
    }

    if len(rows) != 1 or len(columns) != 1:
        raise ValueError(
            "CT slices do not have consistent image dimensions."
        )

    rows_value = next(iter(rows))
    columns_value = next(iter(columns))

    pixel_spacings = {
        tuple(float(value) for value in _get_required(dataset, "PixelSpacing"))
        for _, dataset in datasets
    }

    if len(pixel_spacings) != 1:
        raise ValueError(
            "CT slices do not have consistent PixelSpacing."
        )

    pixel_spacing = next(iter(pixel_spacings))

    orientations = {
        tuple(float(value) for value in _get_required(
            dataset,
            "ImageOrientationPatient",
        ))
        for _, dataset in datasets
    }

    if len(orientations) != 1:
        raise ValueError(
            "CT slices do not have consistent ImageOrientationPatient."
        )

    orientation = next(iter(orientations))

    # ------------------------------------------------------------------
    # Physical slice ordering
    # ------------------------------------------------------------------

    slices: list[tuple[float, Path, pydicom.Dataset]] = []

    for file_path, dataset in datasets:
        z_position = _get_z_position(dataset)
        slices.append((z_position, file_path, dataset))

    slices.sort(key=lambda item: item[0])

    z_positions = np.asarray(
        [item[0] for item in slices],
        dtype=np.float64,
    )

    if len(z_positions) > 1:
        z_differences = np.diff(z_positions)

        if np.any(z_differences <= 0):
            raise ValueError(
                "CT slices do not have strictly increasing Z positions."
            )

        slice_spacing = float(np.median(z_differences))

        if not np.allclose(
            z_differences,
            slice_spacing,
            rtol=1e-3,
            atol=1e-3,
        ):
            raise ValueError(
                "CT slice spacing is inconsistent."
            )
    else:
        slice_spacing = float(
            getattr(slices[0][2], "SliceThickness", 0.0)
        )

        if slice_spacing <= 0:
            raise ValueError(
                "Unable to determine slice spacing."
            )

    # ------------------------------------------------------------------
    # Pixel data → Hounsfield Units
    # ------------------------------------------------------------------

    hu_slices: list[np.ndarray] = []

    for _, file_path, dataset in slices:
        if "PixelData" not in dataset:
            raise ValueError(
                f"PixelData is missing from DICOM file: {file_path}"
            )

        pixel_array = dataset.pixel_array

        if pixel_array.shape != (rows_value, columns_value):
            raise ValueError(
                f"Unexpected pixel shape in {file_path}: "
                f"{pixel_array.shape}"
            )

        hu_slice = _convert_to_hu(pixel_array, dataset)

        hu_slices.append(hu_slice)

    volume = np.stack(hu_slices, axis=0).astype(np.float32)

    # ------------------------------------------------------------------
    # Final metadata
    # ------------------------------------------------------------------

    first_dataset = slices[0][2]

    voxel_spacing = (
        float(pixel_spacing[0]),
        float(pixel_spacing[1]),
        slice_spacing,
    )

    metadata = {
        "modality": "CT",
        "body_region": "CHEST",
        "series_instance_uid": series_uid,
        "number_of_slices": int(volume.shape[0]),
        "rows": int(volume.shape[1]),
        "columns": int(volume.shape[2]),
        "pixel_spacing": pixel_spacing,
        "slice_spacing": slice_spacing,
        "voxel_spacing": voxel_spacing,
        "image_orientation_patient": orientation,
        "z_position_min": float(z_positions.min()),
        "z_position_max": float(z_positions.max()),
        "rescale_slope": float(
            getattr(first_dataset, "RescaleSlope", 1.0)
        ),
        "rescale_intercept": float(
            getattr(first_dataset, "RescaleIntercept", 0.0)
        ),
        "source_directory": str(series_directory),
    }

    return {
        "datasets": [dataset for _, _, dataset in slices],
        "volume": volume,
        "voxel_spacing": voxel_spacing,
        "metadata": metadata,
    }