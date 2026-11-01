@echo off
rem Verified on the laptop: real DICOM -> real model -> verifier -> evidence -> draft report.
call "%~dp0config.bat"
cd /d "%~dp0.."
title DIRECT PIPELINE RUN
python scripts\run_real_pipeline.py "%DICOM_DIR%" --case-id CASE-REAL-1 --out out_real
if "%1"=="" pause
