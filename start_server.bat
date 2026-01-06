@echo off
echo ============================================================
echo   Windows Audio Streaming Server
echo ============================================================
echo.
echo Installing dependencies...
pip install -r requirements.txt
echo.
echo Starting server...
python server.py
pause
