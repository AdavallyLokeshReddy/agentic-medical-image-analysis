# 10-minute demo card

Research & Engineering Prototype - Not for clinical diagnosis or treatment.

## T-30 min (before anyone arrives)
1. `git pull` in the repo, then double-click `demo\0_preflight.bat`. Everything says PASS.
2. Double-click `demo\2_start_backend.bat`. Leave that window open. Do NOT restart it.
3. Double-click `demo\3_job_demo.bat` ONCE as a warm-up (loads the model into memory).
4. Double-click `demo\5_open_pages.bat` (wakes the free Render server).
5. Terminal font large (Ctrl + mouse wheel). Close chat apps, mute notifications, plug in the charger.

## Run of show (10 min)
| Min | Do | Say |
|---|---|---|
| 0:00-1:30 | Slide: problem and contribution | "We did not build a new model. We built the governance layer that controls how medical-imaging AI tools are selected, run, verified and reviewed." |
| 1:30-3:00 | Slide: architecture, Safety Contract | "The system can plan and verify. It cannot diagnose, prescribe, or take irreversible actions. A human always decides." |
| 3:00-7:00 | **`demo\3_job_demo.bat`** (MAIN DEMO) | Narrate while it runs: case created -> plan and Safety Contract -> only the approved tool is selected -> real model runs -> verifier checks -> evidence with provenance -> report is a draft -> I act as the reviewer and accept. |
| 7:00-8:30 | Point at the result | "Probability is one model output, not accuracy. Slices are 5 mm, the verifier warned, so it was escalated to a human. That is the system distrusting the result on purpose." |
| 8:30-9:15 | Hosted site (browser tab already open) | "The shell is online. The model runs locally today. Moving the whole system online is the next phase." |
| 9:15-10:00 | Slide: status and next steps | Done / in development / planned. |

Optional if you have time: `demo\1_governance_demo.bat` (blocked / escalated / verified cases and every refusal).

## If something breaks
| Problem | Do |
|---|---|
| Job run fails | Nothing: `3_job_demo.bat` shows the direct pipeline run and says so. Say it plainly. |
| Backend window closed | Run `2_start_backend.bat`, wait 10 s, run `3_job_demo.bat` (first run is slower). |
| Hosted site slow | It is the free tier waking up. Show the screenshot you saved. |
| Everything fails | Play the screen recording. |

## Never say
- "99.77% accuracy" (it is one model probability; this series has no ground truth)
- "clinically validated", "diagnoses", "detects hemorrhage reliably"
- "fully online" (only the shell is online today)

## Likely questions
- **Is the model yours?** No. It is a published research model (MIT licence). Our contribution is governing it.
- **Why did it escalate?** The slices are 5 mm, coarser than the 3 mm rule, so the verifier sends it to a human.
- **Where is the accuracy?** Needs labelled data. That is the next evaluation stage; today we show governance and safety behaviour.
- **What is next?** Persistent storage, the full system online, frontend screens for review, more models.
