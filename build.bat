@echo off
setlocal
cd /d "%~dp0"
title Building Voice Control by Axword
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)
python -m pip install -r requirements-dev.txt
if errorlevel 1 exit /b 1
python build.py --with-webui
if errorlevel 1 exit /b 1
echo Installer: dist\installer\AxwordVoiceSetup.exe
echo Portable: dist\AxwordVoice-*-portable.zip
