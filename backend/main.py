import io
import os
import re
import shutil
from pathlib import Path
from typing import Optional

import numpy as np
import pydicom
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from preprocessing.ct_preprocessing import preprocess_ct_series


# ============================================================
# APP CONFIGURATION
# ============================================================

app = FastAPI(
    title="Agentic Medical AI Backend",
    description="Backend foundation for Agentic AI Medical Image Analysis",
    version="0.5.0",
)


# ============================================================
# CORS (environment-driven)
#
# CORS_ORIGINS is a comma-separated list of allowed browser
# origins, e.g.
#     CORS_ORIGINS=https://my-frontend.example.com,http://localhost:3000
#
# Defaults to the local Next.js dev server only. Never "*" by
# default. The /preview response carries its slice metadata in
# custom headers, so they must be exposed to the browser.
# ============================================================

_cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=[
        "X-Case-ID",
        "X-Series-Instance-UID",
        "X-Slice-Index",
        "X-Slice-Count",
    ],
)


# ============================================================
# DIRECTORIES
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# IN-MEMORY CASE REGISTRY
# ============================================================

cases = {}


# ============================================================
# PYDANTIC MODELS
# ============================================================

class CaseCreateResponse(BaseModel):
    case_id: str
    status: str


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def validate_case_id(case_id: str):
    """
    Prevent unsafe path values.

    Expected examples:
        CASE-0001
        CASE-0002
        CASE-0003
    """

    if not re.fullmatch(r"[A-Za-z0-9_-]+", case_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid case_id. Use only letters, numbers, '-' and '_'."
        )


def get_case_dir(case_id: str) -> Path:
    """
    Return the directory belonging to a case.
    """

    validate_case_id(case_id)

    case_dir = UPLOAD_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    return case_dir


def get_series_root(case_id: str) -> Path:
    """
    Return:
        uploads/CASE-XXXX/series/
    """

    case_dir = get_case_dir(case_id)

    series_root = case_dir / "series"
    series_root.mkdir(parents=True, exist_ok=True)

    return series_root


def get_series_dir(case_id: str, series_uid: str) -> Path:
    """
    Return the directory for one DICOM series.

    Example:
        uploads/
            CASE-0003/
                series/
                    1.2.840....../
                        image_0.dcm
                        image_1.dcm
    """

    series_root = get_series_root(case_id)

    # DICOM UIDs contain dots and numbers.
    # We still prevent path traversal characters.
    if not re.fullmatch(r"[0-9.]+", series_uid):
        raise HTTPException(
            status_code=400,
            detail="Invalid SeriesInstanceUID."
        )

    series_dir = series_root / series_uid
    series_dir.mkdir(parents=True, exist_ok=True)

    return series_dir


def get_dicom_files(series_dir: Path):
    """
    Return all DICOM files in a series directory.
    """

    if not series_dir.exists():
        return []

    return sorted(
        [
            path
            for path in series_dir.iterdir()
            if path.is_file() and path.suffix.lower() == ".dcm"
        ],
        key=lambda path: path.name
    )


def read_dicom_metadata(file_path: Path):
    """
    Read only the DICOM metadata required for validation.
    """

    try:
        ds = pydicom.dcmread(
            str(file_path),
            stop_before_pixels=True
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not read DICOM file: {file_path.name}"
        ) from exc

    modality = str(getattr(ds, "Modality", "")).upper()

    study_uid = str(
        getattr(ds, "StudyInstanceUID", "")
    )

    series_uid = str(
        getattr(ds, "SeriesInstanceUID", "")
    )

    return {
        "dataset": ds,
        "modality": modality,
        "study_instance_uid": study_uid,
        "series_instance_uid": series_uid,
    }


def validate_dicom_file(file_path: Path):
    """
    Validate one DICOM file for CT processing.
    """

    try:
        ds = pydicom.dcmread(str(file_path))
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not read DICOM file: {file_path.name}"
        ) from exc

    modality = str(getattr(ds, "Modality", "")).upper()

    if modality != "CT":
        raise HTTPException(
            status_code=400,
            detail=(
                f"{file_path.name} is not a CT image. "
                f"Found modality: {modality}"
            )
        )

    if not hasattr(ds, "PixelData"):
        raise HTTPException(
            status_code=400,
            detail=f"{file_path.name} does not contain pixel data."
        )

    study_uid = str(
        getattr(ds, "StudyInstanceUID", "")
    )

    series_uid = str(
        getattr(ds, "SeriesInstanceUID", "")
    )

    if not study_uid:
        raise HTTPException(
            status_code=400,
            detail=f"{file_path.name} is missing StudyInstanceUID."
        )

    if not series_uid:
        raise HTTPException(
            status_code=400,
            detail=f"{file_path.name} is missing SeriesInstanceUID."
        )

    return ds


def select_series(
    case_id: str,
    series_uid: Optional[str] = None
):
    """
    Select a series for processing.

    If series_uid is provided:
        use that exact series.

    Otherwise:
        use the case's selected_series_uid.

    If neither exists:
        select the most recently modified series directory.
    """

    series_root = get_series_root(case_id)

    if series_uid:
        series_dir = get_series_dir(case_id, series_uid)

        if not series_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Series not found: {series_uid}"
            )

        if not get_dicom_files(series_dir):
            raise HTTPException(
                status_code=404,
                detail=f"No DICOM files found in series: {series_uid}"
            )

        return series_uid, series_dir

    case_info = cases.get(case_id, {})

    selected_series_uid = case_info.get(
        "selected_series_uid"
    )

    if selected_series_uid:
        selected_dir = series_root / selected_series_uid

        if selected_dir.exists() and get_dicom_files(selected_dir):
            return selected_series_uid, selected_dir

    series_dirs = [
        path
        for path in series_root.iterdir()
        if path.is_dir() and get_dicom_files(path)
    ]

    if not series_dirs:
        raise HTTPException(
            status_code=404,
            detail="No DICOM series found for this case."
        )

    latest_series = max(
        series_dirs,
        key=lambda path: path.stat().st_mtime
    )

    return latest_series.name, latest_series


def get_next_case_id():
    """
    Generate the next case ID.

    Example:
        CASE-0001
        CASE-0002
        CASE-0003
    """

    existing_numbers = []

    for case_dir in UPLOAD_DIR.iterdir():

        if not case_dir.is_dir():
            continue

        match = re.fullmatch(
            r"CASE-(\d+)",
            case_dir.name
        )

        if match:
            existing_numbers.append(
                int(match.group(1))
            )

    if not existing_numbers:
        next_number = 1
    else:
        next_number = max(existing_numbers) + 1

    return f"CASE-{next_number:04d}"


def get_case_metadata(case_id: str):
    """
    Return metadata stored for a case.
    """

    if case_id in cases:
        return cases[case_id]

    case_dir = UPLOAD_DIR / case_id

    if not case_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Case not found: {case_id}"
        )

    return {
        "case_id": case_id,
        "status": "existing"
    }


# ============================================================
# READ-ONLY EXTENSIONS (case list + governance introspection)
#
# See governance_api.py. These routes never execute a model and
# never write; they expose what the governance libraries can
# truthfully report.
# ============================================================

from governance_api import ApiContext, build_routers  # noqa: E402

# ============================================================
# ANALYSIS JOBS (governed, asynchronous model execution)
#
# See jobs/. POST /cases/{id}/analysis creates a job; the worker
# runs the existing orchestrator -> tool -> verifier -> evidence ->
# report -> human-review chain. Planning and execution stay
# separate, and GET routes never start or advance a job.
# JOBS_MAX_PENDING bounds the queue (default 3).
# ============================================================

from jobs.execution import LocalToolAdapter  # noqa: E402
from jobs.persistence import store_from_environment  # noqa: E402
from jobs.routes import build_job_router, series_locator_from_context  # noqa: E402
from jobs.service import AnalysisJobService  # noqa: E402

job_service = AnalysisJobService(
    adapter=LocalToolAdapter(),
    series_locator=series_locator_from_context(
        UPLOAD_DIR, validate_case_id, select_series, get_dicom_files
    ),
    max_pending=int(os.getenv("JOBS_MAX_PENDING", "3")),
    store=store_from_environment(),  # PostgreSQL when DATABASE_URL is set, else in memory
)

for _router in build_routers(
    ApiContext(
        cases=cases,
        upload_dir=UPLOAD_DIR,
        validate_case_id=validate_case_id,
        select_series=select_series,
        get_dicom_files=get_dicom_files,
        job_status=job_service.runtime_status,
    )
):
    app.include_router(_router)

app.include_router(build_job_router(job_service, validate_case_id))


# ============================================================
# ROOT ENDPOINT
# ============================================================

@app.get("/")
def root():
    return {
        "application": "Agentic Medical AI Backend",
        "version": "0.5.0",
        "status": "running"
    }


# ============================================================
# CREATE CASE
# ============================================================

@app.post(
    "/cases",
    response_model=CaseCreateResponse
)
def create_case():

    case_id = get_next_case_id()

    case_dir = get_case_dir(case_id)
    series_root = case_dir / "series"

    series_root.mkdir(
        parents=True,
        exist_ok=True
    )

    cases[case_id] = {
        "case_id": case_id,
        "status": "created",
        "selected_series_uid": None,
        "files_uploaded": 0
    }

    return {
        "case_id": case_id,
        "status": "created"
    }


# ============================================================
# GET CASE
# ============================================================

@app.get("/cases/{case_id}")
def get_case(case_id: str):

    validate_case_id(case_id)

    return get_case_metadata(case_id)


# ============================================================
# MULTI-FILE DICOM UPLOAD
# ============================================================

@app.post("/cases/{case_id}/upload")
async def upload_dicom(
    case_id: str,
    files: list[UploadFile] = File(...)
):
    """
    Upload one or multiple DICOM files.

    v0.5.0 supports:

        files: list[UploadFile]

    Therefore Swagger will allow multiple DICOM files
    to be selected in one request.
    """

    validate_case_id(case_id)

    if not files:
        raise HTTPException(
            status_code=400,
            detail="No files were provided."
        )

    case_dir = get_case_dir(case_id)
    series_root = get_series_root(case_id)

    uploaded_files = []

    # --------------------------------------------------------
    # STEP 1: Save uploaded files temporarily
    # --------------------------------------------------------

    temp_dir = case_dir / "_temp_upload"

    temp_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    try:

        for upload in files:

            if not upload.filename:
                raise HTTPException(
                    status_code=400,
                    detail="One uploaded file has no filename."
                )

            original_name = Path(
                upload.filename
            ).name

            if not original_name.lower().endswith(".dcm"):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"{original_name} is not a DICOM file. "
                        "Only .dcm files are accepted."
                    )
                )

            temp_path = temp_dir / original_name

            with temp_path.open("wb") as buffer:

                while True:

                    chunk = await upload.read(
                        1024 * 1024
                    )

                    if not chunk:
                        break

                    buffer.write(chunk)

            uploaded_files.append(temp_path)

    except Exception:
        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )
        raise

    # --------------------------------------------------------
    # STEP 2: Validate every DICOM file
    # --------------------------------------------------------

    datasets = []

    try:

        for temp_path in uploaded_files:

            ds = validate_dicom_file(
                temp_path
            )

            datasets.append(ds)

    except Exception:

        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )

        raise

    # --------------------------------------------------------
    # STEP 3: Make sure every file belongs to the same series
    # --------------------------------------------------------

    study_uids = {
        str(getattr(
            ds,
            "StudyInstanceUID",
            ""
        ))
        for ds in datasets
    }

    series_uids = {
        str(getattr(
            ds,
            "SeriesInstanceUID",
            ""
        ))
        for ds in datasets
    }

    modalities = {
        str(getattr(
            ds,
            "Modality",
            ""
        )).upper()
        for ds in datasets
    }

    if len(modalities) != 1 or "CT" not in modalities:

        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )

        raise HTTPException(
            status_code=400,
            detail="All uploaded files must be CT images."
        )

    if len(study_uids) != 1:

        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )

        raise HTTPException(
            status_code=400,
            detail=(
                "Uploaded files belong to different studies. "
                "Upload one CT series at a time."
            )
        )

    if len(series_uids) != 1:

        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )

        raise HTTPException(
            status_code=400,
            detail=(
                "Uploaded files belong to different series. "
                "Upload one CT series at a time."
            )
        )

    study_uid = next(iter(study_uids))
    series_uid = next(iter(series_uids))

    # --------------------------------------------------------
    # STEP 4: Check whether this series already exists
    # --------------------------------------------------------

    series_dir = get_series_dir(
        case_id,
        series_uid
    )

    existing_files = get_dicom_files(
        series_dir
    )

    # --------------------------------------------------------
    # STEP 5: Save files into the series directory
    # --------------------------------------------------------

    saved_files = []

    try:

        for temp_path in uploaded_files:

            destination = series_dir / temp_path.name

            # Avoid accidental overwrite by giving duplicate
            # filenames a unique suffix.
            if destination.exists():

                stem = destination.stem
                suffix = destination.suffix

                counter = 1

                while destination.exists():

                    destination = (
                        series_dir
                        / f"{stem}_{counter}{suffix}"
                    )

                    counter += 1

            shutil.move(
                str(temp_path),
                str(destination)
            )

            saved_files.append(
                destination.name
            )

    except Exception as exc:

        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to save uploaded DICOM files."
        ) from exc

    finally:

        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )

    # --------------------------------------------------------
    # STEP 6: Update case registry
    # --------------------------------------------------------

    if case_id not in cases:

        cases[case_id] = {
            "case_id": case_id,
            "status": "uploaded",
            "selected_series_uid": series_uid,
            "files_uploaded": 0
        }

    cases[case_id][
        "selected_series_uid"
    ] = series_uid

    cases[case_id][
        "status"
    ] = "uploaded"

    cases[case_id][
        "files_uploaded"
    ] = cases[case_id].get(
        "files_uploaded",
        0
    ) + len(saved_files)

    all_series_files = get_dicom_files(
        series_dir
    )

    return {
        "case_id": case_id,
        "status": "uploaded",
        "uploaded_count": len(saved_files),
        "series_file_count": len(all_series_files),
        "study_instance_uid": study_uid,
        "series_instance_uid": series_uid,
        "modality": "CT",
        "files": saved_files
    }


# ============================================================
# LIST SERIES
# ============================================================

@app.get("/cases/{case_id}/series")
def list_series(case_id: str):

    validate_case_id(case_id)

    series_root = get_series_root(case_id)

    series_list = []

    for series_dir in sorted(series_root.iterdir()):

        if not series_dir.is_dir():
            continue

        dicom_files = get_dicom_files(
            series_dir
        )

        if not dicom_files:
            continue

        first_file = dicom_files[0]

        try:

            ds = pydicom.dcmread(
                str(first_file),
                stop_before_pixels=True
            )

            modality = str(
                getattr(
                    ds,
                    "Modality",
                    ""
                )
            ).upper()

            study_uid = str(
                getattr(
                    ds,
                    "StudyInstanceUID",
                    ""
                )
            )

            series_uid = str(
                getattr(
                    ds,
                    "SeriesInstanceUID",
                    ""
                )
            )

            series_description = str(
                getattr(
                    ds,
                    "SeriesDescription",
                    ""
                )
            )

        except Exception:

            continue

        series_list.append(
            {
                "series_instance_uid": series_uid,
                "study_instance_uid": study_uid,
                "modality": modality,
                "series_description": series_description,
                "slice_count": len(dicom_files),
                "selected": (
                    cases.get(
                        case_id,
                        {}
                    ).get(
                        "selected_series_uid"
                    ) == series_uid
                )
            }
        )

    return {
        "case_id": case_id,
        "series_count": len(series_list),
        "series": series_list
    }


# ============================================================
# IMAGE INFO
# ============================================================

@app.get("/cases/{case_id}/image-info")
def image_info(
    case_id: str,
    series_uid: Optional[str] = None
):

    selected_uid, series_dir = select_series(
        case_id,
        series_uid
    )

    dicom_files = get_dicom_files(
        series_dir
    )

    if not dicom_files:

        raise HTTPException(
            status_code=404,
            detail="No DICOM files found."
        )

    try:

        ds = pydicom.dcmread(
            str(dicom_files[0])
        )

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail="Could not read DICOM image."
        ) from exc

    try:

        pixel_array = ds.pixel_array

        min_value = int(
            np.min(pixel_array)
        )

        max_value = int(
            np.max(pixel_array)
        )

        data_type = str(
            pixel_array.dtype
        )

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail="Could not read DICOM pixel data."
        ) from exc

    return {
        "case_id": case_id,
        "series_instance_uid": selected_uid,
        "modality": str(
            getattr(
                ds,
                "Modality",
                ""
            )
        ).upper(),
        "rows": int(
            getattr(
                ds,
                "Rows",
                0
            )
        ),
        "columns": int(
            getattr(
                ds,
                "Columns",
                0
            )
        ),
        "slice_count": len(
            dicom_files
        ),
        "pixel_data_available": (
            hasattr(ds, "PixelData")
        ),
        "min_pixel_value": min_value,
        "max_pixel_value": max_value,
        "data_type": data_type
    }


# ============================================================
# CT DATA
# ============================================================

@app.get("/cases/{case_id}/ct-data")
def ct_data(
    case_id: str,
    series_uid: Optional[str] = None
):

    selected_uid, series_dir = select_series(
        case_id,
        series_uid
    )

    dicom_files = get_dicom_files(
        series_dir
    )

    if not dicom_files:

        raise HTTPException(
            status_code=404,
            detail="No DICOM files found."
        )

    try:

        processed = preprocess_ct_series(
            [
                str(file_path)
                for file_path in dicom_files
            ]
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc)
        ) from exc

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail="Failed to preprocess CT series."
        ) from exc

    volume = processed["volume"]

    return {
        "case_id": case_id,
        "series_instance_uid": selected_uid,
        "modality": "CT",
        "volume_shape": list(
            volume.shape
        ),
        "hu_min": float(
            np.min(volume)
        ),
        "hu_max": float(
            np.max(volume)
        ),
        "hu_mean": float(
            np.mean(volume)
        )
    }


# ============================================================
# CT PREVIEW
# ============================================================

@app.get("/cases/{case_id}/preview")
def preview(
    case_id: str,
    series_uid: Optional[str] = None
):

    selected_uid, series_dir = select_series(
        case_id,
        series_uid
    )

    dicom_files = get_dicom_files(
        series_dir
    )

    if not dicom_files:

        raise HTTPException(
            status_code=404,
            detail="No DICOM files found."
        )

    try:

        processed = preprocess_ct_series(
            [
                str(file_path)
                for file_path in dicom_files
            ]
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc)
        ) from exc

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail="Failed to preprocess CT series."
        ) from exc

    volume = processed["volume"]

    if volume.ndim != 3:

        raise HTTPException(
            status_code=500,
            detail="Expected a 3D CT volume."
        )

    # --------------------------------------------------------
    # Select middle slice
    # --------------------------------------------------------

    middle_index = volume.shape[0] // 2

    middle_slice = volume[
        middle_index
    ]

    # --------------------------------------------------------
    # Brain-style window
    #
    # Center = 40 HU
    # Width  = 80 HU
    # --------------------------------------------------------

    window_center = 40
    window_width = 80

    lower = (
        window_center
        - window_width / 2
    )

    upper = (
        window_center
        + window_width / 2
    )

    windowed = np.clip(
        middle_slice,
        lower,
        upper
    )

    normalized = (
        (
            windowed - lower
        )
        /
        (
            upper - lower
        )
        *
        255
    ).astype(np.uint8)

    # --------------------------------------------------------
    # Convert NumPy image to PNG
    # --------------------------------------------------------

    try:

        from PIL import Image

        image = Image.fromarray(
            normalized
        )

        image_buffer = io.BytesIO()

        image.save(
            image_buffer,
            format="PNG"
        )

        image_buffer.seek(0)

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail="Failed to generate CT preview."
        ) from exc

    return StreamingResponse(
        image_buffer,
        media_type="image/png",
        headers={
            "X-Case-ID": case_id,
            "X-Series-Instance-UID": selected_uid,
            "X-Slice-Index": str(
                middle_index
            ),
            "X-Slice-Count": str(
                volume.shape[0]
            )
        }
    )


# ============================================================
# SERIES INFORMATION
# ============================================================

@app.get("/cases/{case_id}/series-info")
def series_info(
    case_id: str,
    series_uid: Optional[str] = None
):

    selected_uid, series_dir = select_series(
        case_id,
        series_uid
    )

    dicom_files = get_dicom_files(
        series_dir
    )

    if not dicom_files:

        raise HTTPException(
            status_code=404,
            detail="No DICOM files found."
        )

    # --------------------------------------------------------
    # Read first DICOM for metadata
    # --------------------------------------------------------

    try:

        first_ds = pydicom.dcmread(
            str(dicom_files[0]),
            stop_before_pixels=True
        )

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail="Could not read series metadata."
        ) from exc

    modality = str(
        getattr(
            first_ds,
            "Modality",
            ""
        )
    ).upper()

    study_uid = str(
        getattr(
            first_ds,
            "StudyInstanceUID",
            ""
        )
    )

    actual_series_uid = str(
        getattr(
            first_ds,
            "SeriesInstanceUID",
            ""
        )
    )

    # --------------------------------------------------------
    # Only CT is currently supported by preprocessing
    # --------------------------------------------------------

    if modality != "CT":

        return {
            "case_id": case_id,
            "modality": modality,
            "study_instance_uid": study_uid,
            "series_instance_uid": actual_series_uid,
            "slice_count": len(dicom_files),
            "series_status": "unsupported_modality"
        }

    # --------------------------------------------------------
    # Validate and build CT volume
    # --------------------------------------------------------

    try:

        processed = preprocess_ct_series(
            [
                str(file_path)
                for file_path in dicom_files
            ]
        )

    except ValueError as exc:

        return {
            "case_id": case_id,
            "modality": modality,
            "study_instance_uid": study_uid,
            "series_instance_uid": actual_series_uid,
            "slice_count": len(dicom_files),
            "series_status": "invalid",
            "validation_error": str(exc)
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail="Failed to validate CT series."
        ) from exc

    volume = processed["volume"]

    spacing = processed[
        "voxel_spacing"
    ]

    # --------------------------------------------------------
    # Final response
    # --------------------------------------------------------

    return {
        "case_id": case_id,
        "modality": modality,
        "study_instance_uid": study_uid,
        "series_instance_uid": actual_series_uid,
        "slice_count": len(dicom_files),
        "rows": int(
            volume.shape[1]
        ),
        "columns": int(
            volume.shape[2]
        ),
        "volume_shape": list(
            volume.shape
        ),
        "voxel_spacing": {
            "slice_spacing_mm": float(
                spacing[0]
            ),
            "row_spacing_mm": float(
                spacing[1]
            ),
            "column_spacing_mm": float(
                spacing[2]
            )
        },
        "hu_min": float(
            np.min(volume)
        ),
        "hu_max": float(
            np.max(volume)
        ),
        "hu_mean": float(
            np.mean(volume)
        ),
        "series_status": "valid"
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "healthy",
        "version": "0.5.0"
    }