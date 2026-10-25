"""
Generate a SYNTHETIC head-CT-like DICOM series for testing the upload/preview pipeline.

This is a geometric phantom (ellipsoidal "skull" ring around soft-tissue-like interior).
It contains NO patient data and NO pathology, and must never be used for any
clinical or model-performance claim. Its only purpose is to exercise the pipeline
(validation -> preprocessing -> preview) when no real DICOM data is at hand.

Usage:
    python scripts/make_synthetic_ct.py OUTPUT_DIR [--slices 24] [--size 128]
"""

import argparse
import datetime
from pathlib import Path

import numpy as np
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

CT_IMAGE_STORAGE = "1.2.840.10008.5.1.4.1.1.2"


def build_slice_hu(z_index: int, n_slices: int, size: int, rng: np.random.Generator) -> np.ndarray:
    """Return one slice in Hounsfield Units."""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    cy = cx = (size - 1) / 2

    # The ellipsoid shrinks toward the top and bottom of the stack.
    t = (z_index + 0.5) / n_slices * 2 - 1  # -1..1
    scale = np.sqrt(max(0.05, 1 - t * t))
    ry_outer, rx_outer = size * 0.42 * scale, size * 0.34 * scale
    ry_inner, rx_inner = ry_outer - size * 0.045, rx_outer - size * 0.045

    outer = ((yy - cy) / ry_outer) ** 2 + ((xx - cx) / rx_outer) ** 2 <= 1
    inner = ((yy - cy) / ry_inner) ** 2 + ((xx - cx) / rx_inner) ** 2 <= 1

    hu = np.full((size, size), -1000.0, dtype=np.float32)  # air
    hu[outer] = 1000.0  # bone-like ring
    hu[inner] = 35.0 + rng.normal(0, 4, size=inner.sum())  # soft-tissue-like interior
    return hu


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output_dir")
    parser.add_argument("--slices", type=int, default=24)
    parser.add_argument("--size", type=int, default=128)
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(7)
    study_uid, series_uid, frame_uid = generate_uid(), generate_uid(), generate_uid()
    slice_thickness = 5.0
    pixel_spacing = [1.5, 1.5]
    now = datetime.datetime.now()

    for i in range(args.slices):
        hu = build_slice_hu(i, args.slices, args.size, rng)
        stored = np.clip(hu + 1024, 0, 4095).astype(np.uint16)  # intercept -1024, slope 1

        sop_uid = generate_uid()
        meta = FileMetaDataset()
        meta.MediaStorageSOPClassUID = CT_IMAGE_STORAGE
        meta.MediaStorageSOPInstanceUID = sop_uid
        meta.TransferSyntaxUID = ExplicitVRLittleEndian

        ds = FileDataset(str(out / f"slice_{i:03d}.dcm"), {}, file_meta=meta, preamble=b"\0" * 128)
        ds.SOPClassUID = CT_IMAGE_STORAGE
        ds.SOPInstanceUID = sop_uid
        ds.StudyInstanceUID = study_uid
        ds.SeriesInstanceUID = series_uid
        ds.FrameOfReferenceUID = frame_uid
        ds.Modality = "CT"
        ds.PatientName = "SYNTHETIC^PHANTOM"
        ds.PatientID = "SYNTHETIC-0001"
        ds.StudyDescription = "SYNTHETIC PHANTOM - NOT PATIENT DATA"
        ds.SeriesDescription = "Synthetic head phantom (pipeline test only)"
        ds.BodyPartExamined = "HEAD"
        ds.StudyDate = ds.SeriesDate = ds.ContentDate = now.strftime("%Y%m%d")
        ds.StudyTime = ds.SeriesTime = ds.ContentTime = now.strftime("%H%M%S")
        ds.InstanceNumber = i + 1
        ds.SliceThickness = slice_thickness
        ds.SpacingBetweenSlices = slice_thickness
        ds.PixelSpacing = pixel_spacing
        ds.ImagePositionPatient = [0.0, 0.0, float(i * slice_thickness)]
        ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        ds.RescaleIntercept = -1024
        ds.RescaleSlope = 1
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.Rows = ds.Columns = args.size
        ds.BitsAllocated = 16
        ds.BitsStored = 12
        ds.HighBit = 11
        ds.PixelRepresentation = 0
        ds.PixelData = stored.tobytes()
        ds.save_as(str(out / f"slice_{i:03d}.dcm"), enforce_file_format=True)

    print(f"Wrote {args.slices} synthetic CT slices ({args.size}x{args.size}) to {out}")


if __name__ == "__main__":
    main()
