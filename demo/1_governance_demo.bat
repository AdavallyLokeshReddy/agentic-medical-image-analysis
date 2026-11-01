@echo off
rem Governance behaviour on synthetic test inputs. No model runs. About 1.5 minutes to narrate.
call "%~dp0config.bat"
cd /d "%~dp0.."
title GOVERNANCE DEMO
cls
python scripts\demo_governed_workflow.py
echo.
pause
