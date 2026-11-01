@echo off
rem Start the API and LEAVE THIS WINDOW OPEN. Do not restart it: the model stays loaded in memory.
cd /d "%~dp0..\backend"
title BACKEND - leave open
python -m uvicorn main:app --host 127.0.0.1 --port 8000
