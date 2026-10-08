\# Agentic AI for Autonomous Medical Image Analysis \& Clinical Workflow Automation



> An AI-assisted medical imaging system designed to automate parts of the medical image analysis workflow while maintaining verification, uncertainty handling, auditability, and human oversight.



\*\*Status:\*\* Active Development

\*\*Primary Focus:\*\* Non-Contrast Head CT Analysis

\*\*Domain:\*\* Medical Imaging · Agentic AI · Computer Vision · Clinical Workflow Automation



\---



\## Overview



This project explores how \*\*agentic AI systems can be used to coordinate medical image analysis and downstream clinical workflows\*\* rather than treating an ML model as an isolated prediction service.



The current system is being developed around \*\*non-contrast head CT analysis\*\*, with an emphasis on separating:



\* medical image preprocessing

\* AI model inference

\* evidence generation

\* verification and validation

\* clinical-context retrieval

\* structured reporting

\* workflow orchestration

\* human review

\* auditability and case persistence



The goal is not to replace clinical decision-making. The system is designed around a \*\*human-in-the-loop workflow\*\*, where AI outputs can be verified, reviewed, and governed before downstream actions.



\---



\## System Architecture



```text

&#x20;                ┌──────────────────────┐

&#x20;                │      CT / DICOM      │

&#x20;                │       Input          │

&#x20;                └──────────┬───────────┘

&#x20;                           │

&#x20;                           ▼

&#x20;                ┌──────────────────────┐

&#x20;                │ Image Preprocessing  │

&#x20;                │ \& Volume Processing  │

&#x20;                └──────────┬───────────┘

&#x20;                           │

&#x20;                           ▼

&#x20;                ┌──────────────────────┐

&#x20;                │   AI Model Runtime   │

&#x20;                │ Detection / Segment. │

&#x20;                └──────────┬───────────┘

&#x20;                           │

&#x20;                           ▼

&#x20;                ┌──────────────────────┐

&#x20;                │ Evidence Generation  │

&#x20;                │ \& Verification       │

&#x20;                └──────────┬───────────┘

&#x20;                           │

&#x20;                           ▼

&#x20;             ┌──────────────────────────────┐

&#x20;             │    Agentic Orchestrator      │

&#x20;             │                              │

&#x20;             │ Case State → Task Graph →    │

&#x20;             │ Tools → Validation → Review  │

&#x20;             └──────────────┬───────────────┘

&#x20;                            │

&#x20;               ┌────────────┼────────────┐

&#x20;               ▼            ▼            ▼

&#x20;       ┌────────────┐ ┌────────────┐ ┌────────────┐

&#x20;       │ Structured │ │ Human      │ │ Audit /    │

&#x20;       │ Reporting  │ │ Review     │ │ Persistence│

&#x20;       └────────────┘ └────────────┘ └────────────┘

```



\---



\## Core Capabilities



\### 1. Agentic Workflow Orchestration



The backend contains an orchestration layer responsible for coordinating multiple stages of the medical imaging workflow.



Key components include:



\* case state management

\* task graph execution

\* tool registration and dispatch

\* workflow lifecycle management

\* communication between workflow components

\* human-review handling

\* safety contracts



\### 2. Medical Image Processing



The preprocessing layer handles CT-oriented image preparation and volume processing.



Current components include:



\* CT preprocessing

\* CT volume preprocessing

\* chest CT preprocessing

\* image/volume preparation for downstream inference



\### 3. AI Model Runtime



The model runtime provides a controlled interface between the application workflow and AI inference components.



The project currently integrates medical-imaging workflows built around \*\*PyTorch and MONAI\*\*, with model artifacts kept outside the Git repository.



\### 4. Medical Imaging Tools



The backend exposes multiple imaging tools, including workflows for:



\* intracranial hemorrhage detection

\* brain tumor segmentation

\* lung nodule detection

\* multi-organ segmentation

\* pancreas/tumor segmentation

\* whole-body segmentation



These tools are coordinated through the project's tool registry and orchestration layer.



\### 5. Verification \& Safety



A major focus of the project is preventing an AI prediction from automatically becoming an unchecked downstream action.



The verification layer includes:



\* evidence verification

\* governed workflow transitions

\* regression testing

\* safety checks

\* final-state validation

\* human-review lifecycle management



\### 6. Structured Reporting



The reporting layer converts validated workflow information into structured outputs rather than relying solely on free-form model responses.



\### 7. Auditability \& Persistence



The system maintains case and workflow information through a persistence layer containing:



\* case persistence

\* audit records

\* repositories

\* database models

\* workflow state

\* review lifecycle information



This is intended to make important workflow decisions traceable.



\---



\## Technology Stack



\### AI / Machine Learning



\* Python

\* PyTorch

\* MONAI

\* Computer Vision

\* Medical Image Processing

\* Object Detection

\* Image Segmentation



\### Backend



\* Python

\* FastAPI

\* PostgreSQL / SQL

\* REST APIs



\### Agentic AI



\* Agent orchestration

\* Tool-based workflows

\* Task graphs

\* LLM-based workflow coordination

\* Retrieval and clinical-context integration

\* Human-in-the-loop validation



\### Medical Imaging



\* DICOM

\* CT volumes

\* Medical image preprocessing

\* MONAI Model Zoo workflows



\### Engineering



\* Git / GitHub

\* Pytest

\* VS Code

\* Jupyter

\* Google Colab



\---



\## Project Structure



```text

agentic-medical-ai/

│

├── backend/

│   ├── agent/

│   │   ├── case\_state.py

│   │   ├── communication.py

│   │   ├── human\_review.py

│   │   ├── orchestrator.py

│   │   ├── review\_lifecycle.py

│   │   ├── safety\_contract.py

│   │   └── task\_graph.py

│   │

│   ├── database/

│   │   ├── audit.py

│   │   ├── case\_audit.py

│   │   ├── case\_persistence.py

│   │   ├── connection.py

│   │   ├── models.py

│   │   └── repository.py

│   │

│   ├── model\_runtime/

│   │   └── inference.py

│   │

│   ├── preprocessing/

│   │   ├── chest\_ct\_preprocessing.py

│   │   ├── ct\_preprocessing.py

│   │   └── ct\_volume\_preprocessing.py

│   │

│   ├── reporting/

│   │   └── structured\_report.py

│   │

│   ├── tools/

│   │   ├── brain\_tumor\_segmentation.py

│   │   ├── ich\_detection.py

│   │   ├── lung\_nodule\_detection.py

│   │   ├── multi\_organ\_segmentation.py

│   │   ├── pancreas\_tumor\_segmentation.py

│   │   ├── register\_tools.py

│   │   ├── registry.py

│   │   └── whole\_body\_segmentation.py

│   │

│   ├── verification/

│   │   ├── ct2\_verification.py

│   │   ├── ct3\_verification.py

│   │   ├── ct4\_verification.py

│   │   ├── ct5\_verification.py

│   │   └── verifier.py

│   │

│   └── main.py

│

├── tests/

│

├── docs/

├── models/

├── notebooks/

├── .gitignore

└── README.md

```



\---



\## Engineering Approach



The project follows a \*\*modular, governed workflow architecture\*\* rather than putting the complete process inside a single AI agent.



The intended execution flow is approximately:



```text

Input

&#x20; ↓

Preprocess

&#x20; ↓

Model Inference

&#x20; ↓

Generate Evidence

&#x20; ↓

Verify Evidence

&#x20; ↓

Update Case State

&#x20; ↓

Agentic Orchestration

&#x20; ↓

Human Review / Validation

&#x20; ↓

Structured Report

&#x20; ↓

Audit \& Persist

```



This separation makes individual stages easier to test, replace, and evaluate.



\---



\## Testing



The repository contains tests covering multiple parts of the system, including:



\* case state

\* evidence objects

\* verification

\* database models

\* persistence

\* human review

\* workflow lifecycle

\* safety behaviour

\* model loading

\* synthetic inference

\* lung nodule detection

\* structured reporting

\* integration workflows

\* regression behaviour



Testing is an important part of the project's design because medical AI workflows require more than checking whether an individual model produces an output.



\---



\## Model \& Dataset Policy



Large model weights, datasets, uploaded medical images, generated outputs, and local environment files are \*\*not committed to this repository\*\*.



Examples include:



```text

\*.pt

\*.pth

\*.onnx

\*.safetensors

\*.dcm

\*.nii

\*.nii.gz

data/

datasets/

uploads/

outputs/

```



The repository may contain configuration files, model definitions, scripts, and licensing information associated with supported MONAI workflows. Model weights are kept separately.



\---



\## Medical Safety \& Limitations



This is a \*\*research and engineering project\*\*, not a clinically validated medical device.



The system is not intended to:



\* diagnose patients independently

\* replace radiologists or other healthcare professionals

\* provide medical advice

\* make autonomous clinical decisions

\* be deployed in a clinical environment without appropriate validation and regulatory approval



AI-generated findings require appropriate verification and human oversight.



The project is being developed primarily as an exploration of \*\*agentic AI architecture, medical imaging workflows, verification, and clinical workflow automation\*\*.



\---



\## Current Development Status



The project is under active development.



Current work focuses on:



\* strengthening the non-contrast head CT workflow

\* improving model-runtime integration

\* expanding evidence verification

\* improving agent orchestration

\* strengthening human-review workflows

\* integrating structured reporting

\* improving persistence and auditability

\* expanding automated tests

\* evaluating reliability and uncertainty handling



\---



\## Research



This project is also being developed alongside research into \*\*agentic AI for medical imaging and clinical workflow automation\*\*.



The work explores how AI agents can coordinate specialized models and software tools while maintaining verification, traceability, and human oversight.



\---



\## Author



\*\*Adavally Lokesh Reddy\*\*



B.Tech — Artificial Intelligence \& Machine Learning

Malla Reddy University



\* GitHub: `AdavallyLokeshReddy`

\* LinkedIn: `lokeshreddyadavalli`



\---



\## Disclaimer



This repository is intended for research, education, and software engineering experimentation in medical AI.



No clinical claims are made by this project, and outputs should not be used as a substitute for professional medical judgment.



