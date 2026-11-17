@echo off
title Customer Audience Engine - Visual Web App
echo =====================================================================
echo           CUSTOMER DATA & AUDIENCE SEGMENTATION ENGINE
echo =====================================================================
echo.
echo Launching your local web browser to http://localhost:8000 ...
start "" "http://localhost:8000"
echo.
echo Starting FastAPI Backend Server on port 8000...
echo (Press Ctrl+C to stop the server at any time)
echo.
.\.venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000
pause
