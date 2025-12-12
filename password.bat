@echo off
REM Setup a password for AI Bot (first-time setup).

setlocal enabledelayedexpansion
cd /d "%~dp0"

REM Ensure venv
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo Virtual environment not found. Creating one...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo Installing requirements...
    pip install -r requirements.txt
)

python password_setup.py

endlocal
