@echo off
title AgenDino Server
cd /d "%~dp0\src"
start "" "http://127.0.0.1:8000"
"%~dp0\.venv\Scripts\uvicorn.exe" main:app --host 127.0.0.1 --port 8000
