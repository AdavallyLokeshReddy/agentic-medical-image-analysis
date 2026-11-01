@echo off
rem MAIN DEMO. Real DICOM -> case -> plan -> authorized tool -> real model -> verification
rem -> evidence -> report -> human review, through the job API.
rem If the job run fails, the verified direct pipeline run is shown instead, and it says so.
call "%~dp0config.bat"
set HERE=%~dp0
cd /d "%~dp0.."
title JOB DEMO
cls
python scripts\run_job_e2e.py "%DICOM_DIR%" --base-url %API% --review accept --reviewer reviewer-1 --out out_e2e
if errorlevel 1 (
  echo.
  echo ================================================================
  echo The job-API run did not complete.
  echo Showing the direct pipeline run instead: the same real DICOM and
  echo the same real model, but WITHOUT the job API.
  echo ================================================================
  call "%HERE%4_fallback_real_pipeline.bat" nopause
)
echo.
pause
