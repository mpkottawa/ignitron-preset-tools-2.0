@echo off
setlocal
cd /d "%~dp0\.."

set "PIO_PY=%USERPROFILE%\.platformio\penv\Scripts\python.exe"
if exist "%PIO_PY%" (
    "%PIO_PY%" "%~dp0filesystem_uploader_app.py"
) else (
    py -3 "%~dp0filesystem_uploader_app.py"
)

if errorlevel 1 pause
