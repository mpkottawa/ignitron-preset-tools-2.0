@echo off
setlocal
cd /d "%~dp0"
py -3 ignitron_preset_tools_v2.0.py
if errorlevel 1 (
  echo.
  echo Ignitron Preset Tools v2.0 could not start.
  echo Make sure Python 3 is installed and available through the py launcher.
  pause
)
