@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

:: ── winget check ─────────────────────────────────────────────────────────────
winget --version >nul 2>&1
if errorlevel 1 (
    echo winget not available on this machine.
    echo Please install prerequisites manually:
    echo   Python 3.10+  : https://www.python.org/downloads/
    echo   ffmpeg        : https://www.gyan.dev/ffmpeg/builds/
    echo Then re-run this script.
    pause & exit /b 1
)

:: ── Python ───────────────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found — installing via winget...
    winget install --id Python.Python.3.10 --source winget --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 ( echo ERROR: Python install failed. & pause & exit /b 1 )
    echo Python installed. Restarting script to pick up new PATH...
    :: Re-launch so the new PATH is active
    start "" /wait "%~f0"
    exit /b
)

:: ── ffmpeg ────────────────────────────────────────────────────────────────────
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo ffmpeg not found — installing via winget...
    winget install --id Gyan.FFmpeg --source winget --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 ( echo ERROR: ffmpeg install failed. & pause & exit /b 1 )
    echo ffmpeg installed. Please close and re-open this window to reload PATH, then run setup again.
    pause & exit /b 0
)

:: ── Virtual environment ───────────────────────────────────────────────────────
echo Creating virtual environment...
python -m venv venv
if errorlevel 1 ( echo ERROR: Failed to create venv. & pause & exit /b 1 )

echo Activating venv and installing dependencies...
call venv\Scripts\activate.bat

python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 ( echo ERROR: pip install failed. & pause & exit /b 1 )

echo.
echo Setup complete.
echo.
echo To activate the environment in future sessions:
echo   venv\Scripts\activate.bat
echo.
echo Next step — download models and clone repos:
echo   python -c "from liveportrait.setup import setup_all; setup_all()"
echo.
echo NOTE: Place a driving video PKL at:
echo   liveportrait\driving_videos\
echo   (run setup_all above to populate defaults)
echo.
pause
