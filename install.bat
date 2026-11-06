@echo off
setlocal
cd /d "%~dp0"
title Voice Control by Axword - Installation
python --version >nul 2>&1
if errorlevel 1 (
    echo Install Python 3.11 or newer from python.org and add it to PATH.
    exit /b 1
)
node --version >nul 2>&1
if errorlevel 1 (
    echo Install Node.js 22.12 or newer before continuing.
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if errorlevel 1 exit /b 1
pushd webui
call npm ci
if errorlevel 1 (
    popd
    exit /b 1
)
call npm run build
if errorlevel 1 (
    popd
    exit /b 1
)
popd
(
    echo @echo off
    echo cd /d "%%~dp0"
    echo ".venv\Scripts\pythonw.exe" main.py
) > launch.bat
echo Installation complete. Open launch.bat to start Voice Control.
