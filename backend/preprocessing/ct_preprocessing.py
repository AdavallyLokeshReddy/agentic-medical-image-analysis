import os

import numpy as np
import pydicom


def load_ct_dicom(file_path: str):
    """
    Load and validate a single CT DICOM file.

    Returns:
        pydicom.Dataset
    """

    if not os.path.isfile(file_path):
        raise FileNotFoundError(
            f"DICOM file not found: {file_path}"
        )

    try:
        dicom_data = pydicom.dcmread(file_path)
    except Exception as e:
        raise ValueError(
            f"Could not read DICOM file: "
            f"{os.path.basename(file_path)}"
        ) from e

    modality = str(
        getattr(dicom_data, "Modality", "")
    ).upper()

    if modality != "CT":
        raise ValueError(
            f"Expected CT image, but received {modality}"
        )

    if not hasattr(dicom_data, "PixelData"):
        raise ValueError(
            "DICOM file does not contain pixel data"
        )

    return dicom_data


def validate_ct_series(file_paths: list[str]):
    """
    Validate a collection of DICOM files as one CT series.

    Checks:
    - Files exist
    - Files can be read
    - All files are CT
    - All files belong to the same Study
    - All files belong to the same Series
    - Image dimensions are consistent
    """

    if not file_paths:
        raise ValueError(
            "No DICOM files were provided"
        )

    datasets = []

    for file_path in file_paths:

        if not os.path.isfile(file_path):
            raise FileNotFoundError(
                f"DICOM file not found: {file_path}"
            )

        try:
            ds = pydicom.dcmread(file_path)
        except Exception as e:
            raise ValueError(
                f"Could not read DICOM file: "
                f"{os.path.basename(file_path)}"
            ) from e

        modality = str(
            getattr(ds, "Modality", "")
        ).upper()

        if modality != "CT":
            raise ValueError(
                f"All files must be CT. "
                f"Found {modality} in "
                f"{os.path.basename(file_path)}"
            )

        if not hasattr(ds, "PixelData"):
            raise ValueError(
                f"No pixel data found in "
                f"{os.path.basename(file_path)}"
            )

        datasets.append(ds)

    # --------------------------------------------------
    # Check StudyInstanceUID
    # --------------------------------------------------

    study_uids = {
        str(
            getattr(
                ds,
                "StudyInstanceUID",
                ""
            )
        )
        for ds in datasets
    }

    if len(study_uids) != 1:
        raise ValueError(
            "DICOM files belong to different studies"
        )

    # --------------------------------------------------
    # Check SeriesInstanceUID
    # --------------------------------------------------

    series_uids = {
        str(
            getattr(
                ds,
                "SeriesInstanceUID",
                ""
            )
        )
        for ds in datasets
    }

    if len(series_uids) != 1:
        raise ValueError(
            "DICOM files belong to different series"
        )

    # --------------------------------------------------
    # Check image dimensions
    # --------------------------------------------------

    dimensions = {
        (
            int(getattr(ds, "Rows", 0)),
            int(getattr(ds, "Columns", 0))
        )
        for ds in datasets
    }

    if len(dimensions) != 1:
        raise ValueError(
            "CT slices have inconsistent "
            "image dimensions"
        )

    # --------------------------------------------------
    # Check PixelSpacing
    # --------------------------------------------------

    for ds in datasets:

        if not hasattr(ds, "PixelSpacing"):
            raise ValueError(
                f"PixelSpacing missing in "
                f"{getattr(ds, 'SOPInstanceUID', 'unknown')}"
            )

        if len(ds.PixelSpacing) < 2:
            raise ValueError(
                "PixelSpacing must contain "
                "row and column spacing"
            )

    return datasets


def sort_ct_slices(datasets: list):
    """
    Sort CT slices into anatomical order.

    ImagePositionPatient is preferred.
    InstanceNumber is used as fallback.

    Returns:
        List[pydicom.Dataset]
    """

    if not datasets:
        raise ValueError(
            "No CT slices available for sorting"
        )

    # --------------------------------------------------
    # Preferred method:
    # ImagePositionPatient Z coordinate
    # --------------------------------------------------

    if all(
        hasattr(ds, "ImagePositionPatient")
        and len(ds.ImagePositionPatient) >= 3
        for ds in datasets
    ):
        return sorted(
            datasets,
            key=lambda ds: float(
                ds.ImagePositionPatient[2]
            )
        )

    # --------------------------------------------------
    # Fallback:
    # InstanceNumber
    # --------------------------------------------------

    if all(
        hasattr(ds, "InstanceNumber")
        for ds in datasets
    ):
        return sorted(
            datasets,
            key=lambda ds: int(
                ds.InstanceNumber
            )
        )

    raise ValueError(
        "Unable to determine CT slice order. "
        "ImagePositionPatient and InstanceNumber "
        "are unavailable."
    )


def get_voxel_spacing(datasets: list):
    """
    Extract voxel spacing.

    Returns:
        tuple:
            (
                slice_spacing,
                row_spacing,
                column_spacing
            )
    """

    if not datasets:
        raise ValueError(
            "No CT slices provided"
        )

    sorted_datasets = sort_ct_slices(
        datasets
    )

    first = sorted_datasets[0]

    # --------------------------------------------------
    # In-plane spacing
    # --------------------------------------------------

    if not hasattr(first, "PixelSpacing"):
        raise ValueError(
            "PixelSpacing is missing from CT DICOM"
        )

    row_spacing = float(
        first.PixelSpacing[0]
    )

    column_spacing = float(
        first.PixelSpacing[1]
    )

    if row_spacing <= 0 or column_spacing <= 0:
        raise ValueError(
            "Invalid PixelSpacing values"
        )

    # --------------------------------------------------
    # Slice spacing
    # --------------------------------------------------

    if (
        len(sorted_datasets) > 1
        and all(
            hasattr(
                ds,
                "ImagePositionPatient"
            )
            and len(ds.ImagePositionPatient) >= 3
            for ds in sorted_datasets
        )
    ):

        positions = np.array(
            [
                float(
                    ds.ImagePositionPatient[2]
                )
                for ds in sorted_datasets
            ],
            dtype=np.float32
        )

        differences = np.diff(
            positions
        )

        non_zero_differences = np.abs(
            differences[
                np.abs(differences) > 1e-6
            ]
        )

        if len(non_zero_differences) > 0:

            slice_spacing = float(
                np.median(
                    non_zero_differences
                )
            )

        else:

            slice_spacing = float(
                getattr(
                    first,
                    "SliceThickness",
                    1.0
                )
            )

    else:

        slice_spacing = float(
            getattr(
                first,
                "SliceThickness",
                1.0
            )
        )

    if slice_spacing <= 0:
        raise ValueError(
            "Invalid slice spacing"
        )

    return (
        slice_spacing,
        row_spacing,
        column_spacing
    )


def convert_to_hounsfield_units(
    dicom_data
):
    """
    Convert a single CT DICOM image
    into Hounsfield Units.

    Formula:

        HU =
            pixel_value * RescaleSlope
            + RescaleIntercept
    """

    if not hasattr(
        dicom_data,
        "PixelData"
    ):
        raise ValueError(
            "DICOM file does not contain pixel data"
        )

    pixel_array = (
        dicom_data.pixel_array.astype(
            np.float32
        )
    )

    slope = float(
        getattr(
            dicom_data,
            "RescaleSlope",
            1.0
        )
    )

    intercept = float(
        getattr(
            dicom_data,
            "RescaleIntercept",
            0.0
        )
    )

    hu_array = (
        pixel_array * slope
        + intercept
    )

    return hu_array


def stack_ct_volume(datasets: list):
    """
    Convert CT slices into a 3D HU volume.

    Output shape:

        (slices, rows, columns)

    The returned volume remains in Hounsfield Units.
    """

    if not datasets:
        raise ValueError(
            "No CT slices provided"
        )

    sorted_datasets = sort_ct_slices(
        datasets
    )

    slices = []

    expected_shape = None

    for ds in sorted_datasets:

        hu_array = (
            convert_to_hounsfield_units(
                ds
            )
        )

        if expected_shape is None:
            expected_shape = hu_array.shape

        if hu_array.shape != expected_shape:
            raise ValueError(
                "CT slices have inconsistent "
                "pixel array dimensions"
            )

        slices.append(
            hu_array
        )

    volume = np.stack(
        slices,
        axis=0
    ).astype(
        np.float32
    )

    return volume


def apply_brain_window(
    hu_array,
    window_center=40,
    window_width=80
):
    """
    Apply a standard brain CT window.

    This function is intended for:
    - visualization
    - preview images
    - frontend display

    IMPORTANT:
    Do NOT use this output as the input to the
    hemorrhage model.

    The hemorrhage model receives the original
    HU volume and performs its own model-specific
    preprocessing.
    """

    if window_width <= 0:
        raise ValueError(
            "window_width must be greater than 0"
        )

    lower = (
        window_center
        - window_width / 2
    )

    upper = (
        window_center
        + window_width / 2
    )

    windowed = np.clip(
        hu_array,
        lower,
        upper
    )

    normalized = (
        (windowed - lower)
        / (upper - lower)
        * 255.0
    )

    return normalized.astype(
        np.uint8
    )


def preprocess_ct(file_path: str):
    """
    Complete single-slice CT preprocessing.

    Returns:
        {
            "dicom": DICOM dataset,
            "hu_array": original HU image,
            "brain_window": display image
        }
    """

    dicom_data = load_ct_dicom(
        file_path
    )

    hu_array = (
        convert_to_hounsfield_units(
            dicom_data
        )
    )

    brain_window = apply_brain_window(
        hu_array
    )

    return {
        "dicom": dicom_data,
        "hu_array": hu_array,
        "brain_window": brain_window
    }


def preprocess_ct_series(
    file_paths: list[str]
):
    """
    Complete CT series preprocessing.

    Pipeline:

        DICOM files
             ↓
        Validate series
             ↓
        Sort slices
             ↓
        Convert to HU
             ↓
        Stack volume
             ↓
        Extract voxel spacing

    Returns:

        {
            "datasets": sorted DICOM datasets,
            "volume": 3D HU volume,
            "voxel_spacing": (
                slice_spacing,
                row_spacing,
                column_spacing
            )
        }

    IMPORTANT:
    The returned "volume" is kept in HU.

    The hemorrhage model should receive this HU
    volume directly. Do not apply the brain window
    before model inference.
    """

    datasets = validate_ct_series(
        file_paths
    )

    sorted_datasets = sort_ct_slices(
        datasets
    )

    volume = stack_ct_volume(
        sorted_datasets
    )

    voxel_spacing = get_voxel_spacing(
        sorted_datasets
    )

    return {
        "datasets": sorted_datasets,
        "volume": volume,
        "voxel_spacing": voxel_spacing
    }