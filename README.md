# Agentic AI for Autonomous Medical Image Analysis & Clinical Workflow Automation



> A governed agentic AI architecture for coordinating medical image analysis workflows with verification, uncertainty handling, human oversight, structured reporting, and auditability.



**Status:** Active Development

**Primary Focus:** Non-contrast Head CT Analysis

**Domain:** Medical Imaging, Agentic AI, Computer Vision, Clinical Workflow Automation



\---



## Overview



This project explores how agentic AI architectures can coordinate medical image analysis and downstream clinical workflows rather than treating an ML model as an isolated prediction service.



The current development focus is **non-contrast head CT analysis**, while the architecture is designed to support additional medical imaging workflows.



The system separates and coordinates:



* Medical image preprocessing

* AI model inference

* Evidence generation

* Evidence verification

* Tool selection and dispatch

* Case-state management

* Workflow orchestration

* Human review and escalation

* Structured reporting

* Auditability and persistence



The project follows a **human-in-the-loop design**. AI-generated outputs are treated as evidence that must pass appropriate validation and workflow governance before being used for downstream actions.



> **Important:** This is a research and engineering project, not a clinically validated medical device.



\---



## Why This Project?



A conventional medical AI pipeline often looks like:



```text

Medical Image

    |

    v

ML Model

    |

    v

Prediction

```



That approach can be useful for model evaluation, but real-world clinical workflows involve additional requirements:



* Multiple specialized models and tools

* Different imaging modalities

* Preprocessing requirements

* Evidence validation

* Uncertainty and abstention

* Human review

* Workflow state

* Structured reporting

* Traceability

* Auditability

* Controlled downstream actions



This project investigates how these components can be coordinated through a **governed agentic architecture**.



The goal is not simply to build another image classifier. The goal is to explore how AI models, software tools, verification logic, workflow state, and human oversight can operate together as a controlled system.



\---



## System Architecture



```text

                        +----------------------+

                        |     CT / DICOM       |

                        |        Input         |

                        +----------+-----------+

                                   |

                                   v

                        +----------------------+

                        | Image Preprocessing  |

                        | & Volume Processing  |

                        +----------+-----------+

                                   |

                                   v

                        +----------------------+

                        |    Model Runtime     |

                        | Detection / Segment. |

                        +----------+-----------+

                                   |

                                   v

                        +----------------------+

                        | Evidence Generation  |

                        |   & Verification     |

                        +----------+-----------+

                                   |

                                   v

               +-------------------------------------------+

               |           Governed Orchestrator            |

               |-------------------------------------------|

               | Case State -> Task Graph -> Tools         |

               |       -> Validation -> Review             |

               |                                           |

               | Safety Contracts + Workflow Controls      |

               +-------------------+-----------------------+

                                   |

                   +---------------+---------------+

                   |               |               |

                   v               v               v

            +-----------+   +-----------+   +-----------+

            | Structured|   |  Human    |   |  Audit &  |

            | Reporting |   |  Review   |   | Persistence|

            +-----------+   +-----------+   +-----------+

```



The architecture intentionally separates **model inference** from **workflow governance**.



This makes it possible to reason about what a model produced, whether the evidence is valid, what actions are permitted, whether human review is required, and what happened throughout the case lifecycle.



\---



## Core Engineering Components



### 1. Governed Agentic Orchestration



The orchestration layer coordinates workflow components while keeping execution bounded by explicit state, available tools, safety constraints, and verification requirements.



Key responsibilities include:



* Case state management

* Task graph construction

* Tool registration and discovery

* Tool selection and dispatch

* Workflow lifecycle management

* Human-review handling

* Safety contracts

* Communication between workflow components



The orchestrator is designed to provide controlled workflow coordination rather than unrestricted autonomous execution.



\---



### 2. Case State Management



An imaging case is represented as a stateful workflow rather than a single model request.



Case state can include:



* Case identity

* Input modality

* Body region

* Available evidence

* Selected tools

* Workflow progress

* Verification state

* Review state

* Finalization state



This allows workflow components to operate against a shared representation of the current case.



\---



### 3. Safety Contracts



Safety contracts define constraints around workflow execution.



The architecture considers controls such as:



* Supported modalities

* Body regions

* Approved tools

* Task preconditions

* Permitted operations

* Uncertainty handling

* Abstention

* Escalation

* Retry limits

* Timeouts

* Concurrent tool execution



The objective is to prevent workflow components from performing actions outside their defined operating boundaries.



\---



### 4. Task Graphs



Complex workflows can be represented as bounded sequences of tasks.



A simplified workflow can be represented as:



```text

Inspect Case

   |

   v

Discover Available Tools

   |

   v

Apply Safety Constraints

   |

   v

Build Bounded Tasks

   |

   v

Execute / Evaluate Workflow

   |

   v

Verify Evidence

   |

   +-------> Escalate if Required

   |

   v

Finalize Case

```



This provides a structured representation of workflow dependencies and state transitions.



\---



### 5. Medical Image Processing



The repository contains preprocessing components for medical imaging workflows, including:



* CT preprocessing

* CT volume preprocessing

* Chest CT preprocessing

* Image and volume preparation for downstream inference



These components provide the preprocessing layer between medical imaging inputs and downstream AI model execution.



\---



### 6. AI Model Runtime



The model runtime provides infrastructure for loading and executing AI models used by the imaging workflows.



The project uses:



* Python

* PyTorch

* MONAI

* Medical image processing

* Detection

* Segmentation



Model weights are intentionally kept outside the normal source repository workflow.



\---



### 7. Medical Imaging Tools



The repository contains specialized imaging tool integrations, including workflows related to:



* Intracranial hemorrhage detection

* Brain tumor segmentation

* Lung nodule detection

* Multi-organ segmentation

* Pancreas and tumor segmentation

* Whole-body segmentation



These tools provide specialized capabilities that can be coordinated by the broader workflow architecture.



\---



### 8. Verification & Validation



Verification is treated as a separate engineering concern from model inference.



Testing and verification components cover areas such as:



* Evidence validation

* Workflow transitions

* Safety behavior

* Final-state validation

* Model loading

* Synthetic inference

* Integration workflows

* Regression behavior



The goal is to ensure that AI outputs become actionable only after passing appropriate verification and governance checks.



\---



### 9. Human-in-the-Loop Review



The system includes explicit human-review concepts for cases where automated processing should not proceed without additional validation.



Review can be triggered when:



* Evidence is insufficient

* Validation fails

* Uncertainty requires review

* A workflow reaches a governed review state



This allows the system to distinguish between automated processing and situations requiring human intervention.



\---



### 10. Structured Reporting



Structured reporting components provide a controlled representation of workflow results.



The reporting layer is intended to separate:



```text

AI Evidence

   |

   v

Verification

   |

   v

Workflow Decision

   |

   v

Structured Report

```



This provides a clearer boundary between raw model output and information produced by the overall workflow.



\---



### 11. Auditability & Persistence



The repository contains persistence and audit components for tracking workflow state and important system events.



These include:



* Case persistence

* Audit records

* Repository operations

* Database models

* Workflow state

* Review lifecycle information



The purpose is to make important workflow events and decisions **traceable and reproducible**.



\---



# Current Implementation vs. Roadmap



## Implemented / Under Active Testing



The repository currently contains engineering components for:



* Governed agent orchestration architecture

* Case state management

* Task graph concepts

* Tool registry

* Safety contracts

* Human-review lifecycle

* Evidence objects and verification

* Medical imaging tool integrations

* CT preprocessing components

* Structured reporting

* Database persistence

* Audit structures

* Regression and integration tests

* MONAI-based model workflow integration



## In Progress



Current development is focused on:



* Strengthening the non-contrast head CT workflow

* Expanding autonomous tool execution under safety constraints

* Improving model-runtime integration

* Improving evidence verification

* Expanding uncertainty handling

* Strengthening human-review workflows

* Expanding structured reporting

* Improving auditability

* Evaluating end-to-end workflow reliability

* Further integrating agentic AI components with specialized imaging models



This distinction is intentional. The repository documents the **current engineering state** rather than presenting planned functionality as completed functionality.



\---



# Technology Stack



## AI / Machine Learning



* Python

* PyTorch

* MONAI

* Computer Vision

* Medical Image Processing

* Object Detection

* Image Segmentation



## Agentic AI



* Governed agent orchestration

* Tool-based workflows

* Task graphs

* Safety-constrained workflow execution

* Verification and validation

* Human-in-the-loop review

* Workflow state management



## Backend



* Python

* FastAPI

* REST APIs

* SQL / PostgreSQL-oriented persistence



## Medical Imaging



* DICOM

* CT volumes

* Medical image preprocessing

* MONAI Model Zoo workflows



## Engineering



* Git

* GitHub

* Pytest

* VS Code

* Jupyter

* Google Colab



\---



# Project Structure



```text

agentic-medical-image-analysis/

|

+-- backend/

|   |

|   +-- agent/

|   |   +-- case\_state.py

|   |   +-- communication.py

|   |   +-- human\_review.py

|   |   +-- orchestrator.py

|   |   +-- review\_lifecycle.py

|   |   +-- safety\_contract.py

|   |   +-- task\_graph.py

|   |

|   +-- database/

|   |   +-- audit.py

|   |   +-- case\_audit.py

|   |   +-- connection.py

|   |   +-- models.py

|   |   +-- persistence.py

|   |   +-- repository.py

|   |

|   +-- model\_runtime/

|   |   +-- inference.py

|   |

|   +-- preprocessing/

|   |   +-- chest\_ct.py

|   |   +-- ct.py

|   |   +-- ct\_volume.py

|   |

|   +-- reporting/

|   |   +-- structured\_report.py

|   |

|   +-- tools/

|   |   +-- brain\_tumor\_segmentation.py

|   |   +-- ich\_detection.py

|   |   +-- lung\_nodule\_detection.py

|   |   +-- multi\_organ\_segmentation.py

|   |   +-- pancreas\_tumor\_segmentation.py

|   |   +-- register\_tools.py

|   |   +-- registry.py

|   |   +-- whole\_body\_segmentation.py

|   |

|   +-- verification/

|       +-- ct2\_verification.py

|       +-- ct3\_verification.py

|       +-- ct4\_verification.py

|       +-- ct5\_verification.py

|       +-- mri1\_verification.py

|       +-- verifier.py

|

+-- backend/models/monai/

|

+-- backend/tests/

|

+-- tests/

|

+-- .gitignore

+-- README.md

```



\---



# Testing



Testing is an important part of the project because the system is designed around workflow-level behavior rather than isolated model predictions.



Test coverage includes areas such as:



* Case state

* Evidence objects

* Verification

* Database models

* Persistence

* Human review

* Workflow lifecycle

* Safety behavior

* Model loading

* Synthetic inference

* Lung nodule detection

* Structured reporting

* Integration workflows

* Regression behavior



The project uses testing to validate both individual components and broader workflow and safety behavior.



\---



# Running Tests



Clone the repository and create a Python virtual environment appropriate for your development environment.



### Windows



```cmd

git clone https://github.com/AdavallyLokeshReddy/agentic-medical-image-analysis.git

cd agentic-medical-image-analysis



python -m venv .venv

.venv\\Scripts\\activate

```



### Linux / macOS



```bash

git clone https://github.com/AdavallyLokeshReddy/agentic-medical-image-analysis.git

cd agentic-medical-image-analysis



python3 -m venv .venv

source .venv/bin/activate

```



Install the dependencies required by the current development environment and run:



```bash

pytest

```



Large model weights, medical datasets, and local uploaded case files are intentionally kept outside the repository.



\---



# Model & Dataset Policy



Large or sensitive artifacts are not committed to the normal source repository.



The `.gitignore` excludes items such as:



```text

*.pt

*.pth

*.onnx

*.safetensors

*.bin



*.dcm

*.nii

*.nii.gz



data/

datasets/

uploads/

outputs/

results/

runs/

artifacts/



.env

```



This keeps the repository focused on source code, configuration, tests, documentation, and reproducible engineering logic.



Model definitions, configuration files, and third-party components may remain in the repository where appropriate and permitted by their respective licenses.



\---



# Medical Safety & Limitations



This project is a **research and engineering system**, not a clinically validated medical device.



It is not intended to:



* Diagnose patients independently

* Replace radiologists or healthcare professionals

* Provide medical advice

* Make autonomous clinical decisions

* Be deployed in a clinical environment without appropriate validation

* Serve as a substitute for regulatory approval or clinical evaluation



Any future clinical use would require appropriate clinical validation, safety evaluation, regulatory review, data governance, and human oversight.



\---



# Research Direction



The project is being developed alongside research into **agentic AI for medical imaging and clinical workflow automation**.



Key research themes include:



* Agentic AI architecture

* Medical imaging workflows

* AI tool orchestration

* Verification

* Safety constraints

* Human-in-the-loop systems

* Clinical workflow automation

* Auditability

* Traceability

* Uncertainty handling

* Human oversight

* Workflow governance



The broader goal is to investigate how agentic systems can move beyond isolated model inference toward **structured, auditable AI-assisted workflows**.



\---



# Current Development Status



**Active Development**



Current priorities include:



* Strengthening the non-contrast head CT workflow

* Improving model-runtime integration

* Expanding evidence verification

* Improving governed agent orchestration

* Expanding human-review workflows

* Improving structured reporting

* Strengthening persistence and auditability

* Expanding automated testing

* Evaluating reliability and uncertainty handling

* Expanding support for additional imaging workflows



\---



# Future Direction



Planned areas of development include:



* More autonomous tool execution under safety constraints

* Improved model selection and routing

* Better uncertainty-aware workflow decisions

* Expanded multimodal medical imaging support

* Stronger clinical-context retrieval

* Improved agent evaluation

* End-to-end workflow demonstrations

* More comprehensive observability and audit trails



\---



# Disclaimer



This repository is intended for **research, education, and software engineering experimentation in medical AI**.



The system and its outputs should not be used for diagnosis, treatment decisions, or clinical decision-making.



The authors make no claims regarding clinical accuracy, safety, regulatory compliance, or suitability for medical deployment.



\---



# Author



**Adavally Lokesh Reddy**



AI & ML Undergraduate | Medical AI | Agentic AI | Computer Vision



* GitHub: [AdavallyLokeshReddy](https://github.com/AdavallyLokeshReddy)

* LinkedIn: [lokeshreddyadavalli](https://linkedin.com/in/lokeshreddyadavalli/)



\---



## License & Third-Party Components



This repository may include configuration, documentation, and source components associated with third-party medical AI frameworks and model workflows, including MONAI-based components.



Third-party licenses and attribution requirements remain applicable to their respective components.



Review the relevant third-party licenses and model terms before redistributing or deploying associated components.



