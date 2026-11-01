@echo off
rem Run this BEFORE the audience arrives. Every line should say PASS or OK.
call "%~dp0config.bat"
cd /d "%~dp0.."
title PREFLIGHT
echo ============================ PREFLIGHT ============================
echo.
echo [1] Python packages
python -c "import fastapi, uvicorn, pydicom, numpy, torch, skp; print('    PASS  torch', torch.__version__)" || echo     FAIL: a package is missing - read the error above
echo.
echo [2] DICOM folder
if exist "%DICOM_DIR%" (
  for /f %%c in ('dir /b /s "%DICOM_DIR%\*.dcm" ^| find /c /v ""') do echo     PASS  %%c .dcm files in %DICOM_DIR%
) else (
  echo     FAIL: folder not found: %DICOM_DIR%
)
echo.
echo [3] Backend process on port 8000
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul && (echo     PASS  backend is running) || (echo     NOTE  not running yet: start 2_start_backend.bat)
echo.
echo [4] Backend answers, and can it run the model?
python -c "import json,urllib.request as u; d=json.load(u.urlopen('%API%/governance/status',timeout=5)); print('    job_execution:', d['job_execution'])" 2>nul || echo     NOTE  backend not reachable yet
echo.
echo [5] Code version
git log --oneline -1
echo.
echo ===================================================================
pause
