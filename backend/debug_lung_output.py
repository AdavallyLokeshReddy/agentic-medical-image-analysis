from pathlib import Path
import torch

from preprocessing.chest_ct_preprocessing import preprocess_chest_ct_series
from tools.lung_nodule_detection import LungNoduleDetectionTool

series_dir = Path("uploads/CASE-LUNG-0001/series")

result = preprocess_chest_ct_series(series_dir)
datasets = result["datasets"]

tool = LungNoduleDetectionTool()

image = tool._prepare_input(
    volume=result["volume"],
    voxel_spacing=result["voxel_spacing"],
    image_position_patient=tuple(
        float(v) for v in datasets[0].ImagePositionPatient
    ),
    image_orientation_patient=tuple(
        float(v) for v in datasets[0].ImageOrientationPatient
    ),
)

image = image.unsqueeze(0).to(tool.device)

print("RUNNING RAW INFERER...")

with torch.no_grad():
    output = tool.inferer(
        image,
        tool.network,
    )

print("RAW TYPE:", type(output).__name__)

if isinstance(output, list):
    print("RAW LENGTH:", len(output))

    for index, item in enumerate(output):
        print(
            f"ITEM {index}:",
            type(item).__name__,
        )

        if isinstance(item, dict):
            print(
                "  KEYS:",
                list(item.keys()),
            )

            for key, value in item.items():
                print(
                    f"  {key}:",
                    type(value).__name__,
                )
else:
    print("RAW OUTPUT TYPE:", type(output).__name__)
