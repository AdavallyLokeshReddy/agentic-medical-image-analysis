@echo off
rem ---- Edit these two lines only if your folders differ ----
set DICOM_DIR=C:\Users\lokes\Downloads\SinoCT_files
set API=http://127.0.0.1:8000
rem ---- Human review decision used by the job demo ----
rem Default: the reviewer REJECTS with a reason (slices are 5 mm, which is what the verifier warned about).
set REVIEW_ARGS=--review reject --reviewer reviewer-1 --reason "Slices are 5 mm - series not suitable for automated assessment"
rem To demonstrate acceptance instead, comment the line above and use this one:
rem set REVIEW_ARGS=--review accept --reviewer reviewer-1
