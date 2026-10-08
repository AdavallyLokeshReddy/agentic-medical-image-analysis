from .brain_tumor_segmentation import BrainTumorSegmentationTool
from .ich_detection import ICHDetectionTool
from .lung_nodule_detection import LungNoduleDetectionTool
from .multi_organ_segmentation import MultiOrganSegmentationTool
from .pancreas_tumor_segmentation import PancreasTumorSegmentationTool
from .whole_body_segmentation import WholeBodySegmentationTool
from .registry import ToolMetadata, tool_registry


def register_default_tools() -> None:
    """
    Register the approved medical AI tools used by the prototype.

    This function is intentionally explicit:
    only tools listed here become available to the agent.
    """

    # =========================================================
    # CT-1: Intracranial Hemorrhage Detection
    # =========================================================

    ich_tool = ICHDetectionTool()

    ich_metadata = ToolMetadata(
        supported_modalities=["CT"],
        supported_body_regions=[
            "head",
            "brain",
        ],
        intended_use=(
            "Research/demo detection of suspected intracranial "
            "hemorrhage from non-contrast head CT."
        ),
        expected_inputs=[
            "3D CT volume",
            "Hounsfield Units",
        ],
        output_schema={
            "prediction": {
                "label": "string",
                "hemorrhage_detected": "boolean",
                "any_probability": "float",
                "highest_probability_subtype": "string",
                "highest_probability": "float",
                "subtypes": "object",
            },
            "series": "object",
            "input": "object",
            "evidence": "object",
            "warnings": "list",
        },
        validation_population=(
            "Research/demo use only. "
            "Clinical validation is not established."
        ),
        exclusions=[
            "Not a clinical diagnosis.",
            "Not intended to authorize treatment.",
            "Not intended for autonomous clinical decision-making.",
        ],
        version=ICHDetectionTool.MODEL_VERSION,
        compute_requirements={
            "framework": "PyTorch",
            "device": "CPU or CUDA",
        },
    )

    tool_registry.register(
        ich_tool,
        metadata=ich_metadata,
    )

    # =========================================================
    # CT-2: Lung Nodule Detection
    # =========================================================

    lung_nodule_tool = LungNoduleDetectionTool()

    lung_nodule_metadata = ToolMetadata(
        supported_modalities=["CT"],
        supported_body_regions=[
            "chest",
            "lung",
            "lungs",
            "thorax",
        ],
        intended_use=(
            "Research/demo detection of pulmonary nodules "
            "from chest CT using the MONAI RetinaNet "
            "LUNA16 model."
        ),
        expected_inputs=[
            "3D CT volume",
            "Hounsfield Units",
            "ImagePositionPatient",
            "ImageOrientationPatient",
            "voxel spacing",
        ],
        output_schema={
            "prediction": (
                "list of detected pulmonary nodule "
                "bounding-box predictions"
            ),
            "input_shape": "list",
            "input_spacing": "list",
            "image_position_patient": "list",
            "image_orientation_patient": "list",
            "target_spacing": "list",
            "score_threshold": "float",
            "nms_threshold": "float",
            "max_detections": "integer",
            "tool_name": "string",
            "tool_version": "string",
            "clinical_use": "string",
            "device": "string",
            "warnings": "list",
        },
        validation_population=(
            "LUNA16 research population. "
            "Clinical validation is not established."
        ),
        exclusions=[
            "Not a clinical diagnosis.",
            "Not intended to authorize treatment.",
            "Not intended for autonomous clinical decision-making.",
            "Human verification is required before clinical interpretation.",
            "Model was developed for the LUNA16 research setting.",
            "Detection output requires verification.",
        ],
        version=LungNoduleDetectionTool.TOOL_VERSION,
        compute_requirements={
            "framework": "PyTorch",
            "device": "CPU or CUDA",
            "inference": "3D RetinaNet detection",
        },
    )

    tool_registry.register(
        lung_nodule_tool,
        metadata=lung_nodule_metadata,
    )

    # =========================================================
    # CT-3: Multi-Organ Segmentation
    # =========================================================

    multi_organ_tool = MultiOrganSegmentationTool()

    multi_organ_metadata = ToolMetadata(
        supported_modalities=["CT"],
        supported_body_regions=[
            "abdomen",
            "abdominal",
            "pancreas",
        ],
        intended_use=(
            "Research/demo multi-organ segmentation "
            "from abdominal CT."
        ),
        expected_inputs=[
            "3D CT volume",
            "Hounsfield Units",
            "ImagePositionPatient",
            "ImageOrientationPatient",
            "voxel spacing",
        ],
        output_schema={
            "prediction": "segmentation map",
            "probabilities": "14-channel probability volume",
            "label_summary": "object",
            "tool": "string",
            "tool_version": "string",
            "model_name": "string",
            "model_version": "string",
            "runtime": "string",
            "verification_required": "boolean",
            "clinical_use": "string",
            "warnings": "list",
        },
        validation_population=(
            "BTCV research dataset. "
            "Clinical validation is not established."
        ),
        exclusions=[
            "Not a clinical diagnosis.",
            "Not intended to authorize treatment.",
            "Not intended for autonomous clinical decision-making.",
            "Human verification is required before clinical interpretation.",
        ],
        version=MultiOrganSegmentationTool.TOOL_VERSION,
        compute_requirements={
            "framework": "PyTorch",
            "device": "CPU or CUDA",
            "inference": "3D sliding-window",
        },
    )

    tool_registry.register(
        multi_organ_tool,
        metadata=multi_organ_metadata,
    )

    # =========================================================
    # CT-4: Pancreas + Pancreatic Tumor Segmentation
    # =========================================================

    pancreas_tumor_tool = PancreasTumorSegmentationTool()

    pancreas_tumor_metadata = ToolMetadata(
        supported_modalities=["CT"],
        supported_body_regions=[
            "abdomen",
            "abdominal",
            "pancreas",
        ],
        intended_use=(
            "Research/demo segmentation of the pancreas "
            "and pancreatic tumor from abdominal CT."
        ),
        expected_inputs=[
            "3D CT volume",
            "Hounsfield Units",
            "ImagePositionPatient",
            "ImageOrientationPatient",
            "voxel spacing",
        ],
        output_schema={
            "prediction": "segmentation map",
            "prediction_shape": "list",
            "label_summary": {
                "background": "integer",
                "pancreas": "integer",
                "pancreatic_tumor": "integer",
            },
            "input_shape": "list",
            "resampled_shape": "list",
            "voxel_spacing": "list",
            "input_range": "list",
            "tool_name": "string",
            "tool_version": "string",
            "model_name": "string",
            "model_version": "string",
            "verification_required": "boolean",
            "clinical_use": "string",
            "warnings": "list",
            "provenance": "object",
        },
        validation_population=(
            "Medical Segmentation Decathlon Task07 Pancreas "
            "research population. Clinical validation is not established."
        ),
        exclusions=[
            "Not a clinical diagnosis.",
            "Not intended to authorize treatment.",
            "Not intended for autonomous clinical decision-making.",
            "Human verification is required before clinical interpretation.",
            "Current prototype performs controlled 96x96x96 crop inference.",
            "Full-volume inference is not yet enabled.",
        ],
        version=PancreasTumorSegmentationTool.TOOL_VERSION,
        compute_requirements={
            "framework": "PyTorch",
            "device": "CPU",
            "inference": "3D 96x96x96 controlled crop",
        },
    )

    tool_registry.register(
        pancreas_tumor_tool,
        metadata=pancreas_tumor_metadata,
    )

    # =========================================================
    # CT-5: Whole-Body CT Segmentation
    # =========================================================

    whole_body_tool = WholeBodySegmentationTool()

    whole_body_metadata = ToolMetadata(
        supported_modalities=["CT"],
        supported_body_regions=[
            "whole_body",
            "whole-body",
            "body",
        ],
        intended_use=(
            "Research/demo whole-body anatomical segmentation "
            "from CT using the MONAI wholeBody_ct_segmentation model."
        ),
        expected_inputs=[
            "3D CT volume",
            "Hounsfield Units",
            "ImagePositionPatient",
            "ImageOrientationPatient",
            "voxel spacing",
        ],
        output_schema={
            "prediction": "segmentation map",
            "prediction_shape": "list",
            "input_shape": "list",
            "voxel_spacing": "list",
            "model_input_spacing": "list",
            "label_summary": "object",
            "tool": "string",
            "tool_version": "string",
            "model_name": "string",
            "model_version": "string",
            "runtime": "string",
            "verification_required": "boolean",
            "clinical_use": "string",
            "warnings": "list",
            "provenance": "object",
        },
        validation_population=(
            "MONAI wholeBody_ct_segmentation research bundle "
            "trained using TotalSegmentator data. "
            "Clinical validation is not established."
        ),
        exclusions=[
            "Not a clinical diagnosis.",
            "Not intended to authorize treatment.",
            "Not intended for autonomous clinical decision-making.",
            "Human verification is required before clinical interpretation.",
            "Research/demo model output requires verification.",
            "The model has not been clinically validated for autonomous use.",
        ],
        version=WholeBodySegmentationTool.MODEL_VERSION,
        compute_requirements={
            "framework": "PyTorch",
            "device": "CPU or CUDA",
            "inference": "3D sliding-window SegResNet",
            "roi_size": "96x96x96",
            "resampling_spacing": "1.5x1.5x1.5 mm",
            "output_classes": 105,
        },
    )

    tool_registry.register(
        whole_body_tool,
        metadata=whole_body_metadata,
    )

    # =========================================================
    # MRI-1: Brain Tumor / Lesion Segmentation
    # =========================================================

    brain_tumor_tool = BrainTumorSegmentationTool()

    brain_tumor_metadata = ToolMetadata(
        supported_modalities=["MRI"],
        supported_body_regions=[
            "brain",
            "head",
            "neuro",
            "neurological",
        ],
        intended_use=(
            "Research/demo multimodal brain tumor subregion "
            "segmentation from T1c, T1, T2 and FLAIR MRI."
        ),
        expected_inputs=[
            "3D T1c MRI volume",
            "3D T1 MRI volume",
            "3D T2 MRI volume",
            "3D FLAIR MRI volume",
            "1 mm isotropic voxel spacing",
            "consistent MRI sequence geometry",
        ],
        output_schema={
            "probabilities": {
                "tumor_core": "3D probability volume",
                "whole_tumor": "3D probability volume",
                "enhancing_tumor": "3D probability volume",
            },
            "masks": {
                "tumor_core": "3D boolean mask",
                "whole_tumor": "3D boolean mask",
                "enhancing_tumor": "3D boolean mask",
            },
            "label_summary": "object",
            "input_shape": "list",
            "prediction_shape": "list",
            "voxel_spacing": "object",
            "tool": "string",
            "tool_version": "string",
            "model": "string",
            "model_version": "string",
            "runtime": "object",
            "verification_required": "boolean",
            "clinical_use": "string",
            "warnings": "list",
            "provenance": "object",
        },
        validation_population=(
            "BraTS research population. "
            "Clinical validation is not established."
        ),
        exclusions=[
            "Not a clinical diagnosis.",
            "Not intended to authorize treatment.",
            "Not intended for autonomous clinical decision-making.",
            "Human verification is required before clinical interpretation.",
            "Requires T1c, T1, T2 and FLAIR sequences.",
            "Input geometry must satisfy the 1 mm isotropic contract.",
            "Model output requires verification before workflow use.",
            "Research/demo implementation only.",
        ],
        version=BrainTumorSegmentationTool.MODEL_VERSION,
        compute_requirements={
            "framework": "PyTorch",
            "device": "CPU or CUDA",
            "architecture": "SegResNet",
            "inference": "3D sliding-window",
            "roi_size": "240x240x160",
            "sw_batch_size": 1,
            "overlap": 0.5,
            "input_channels": 4,
            "output_regions": 3,
        },
    )

    tool_registry.register(
        brain_tumor_tool,
        metadata=brain_tumor_metadata,
    )


# =============================================================
# Initialize the explicit approved-tool registry
# =============================================================

register_default_tools()