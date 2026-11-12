@echo off
rem Starts the tuner server (all cars) and opens the tuner page in the default browser.
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" (
    echo Python not found at "%PY%".
    echo Install Python 3.12 for the current user, or edit the PY line in this file.
    pause
    exit /b 1
)
cd /d "%~dp0.."
start "" /min cmd /c "ping -n 3 127.0.0.1 >nul & start http://127.0.0.1:8765/"
"%PY%" -I tools\tuner_server.py --port 8765
echo.
echo The tuner server has stopped.
pause
