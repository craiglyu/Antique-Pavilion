@echo off
REM CHANGE AP-CONSOLE-LAUNCHER: one-click Windows entrypoint for the loopback-only AP Control Center.
setlocal
title AP Bot Control Center

set "AP_WSL_PROJECT=/mnt/c/Users/A50529/Desktop/Craig/Antique Digital Pavilion"
set "AP_WSL_PYTHON=/home/craig/miniconda3/envs/mamba_env/bin/python3"

echo.
echo  AP Bot Control Center
echo  Browser will open automatically. Keep this window open while using the console.
echo  Press Ctrl+C here only when you want to close the Control Center.
echo.

wsl.exe -d Ubuntu -- bash -lc "cd '%AP_WSL_PROJECT%' && exec '%AP_WSL_PYTHON%' -u scripts/ap_launcher_web.py"
set "AP_LAUNCHER_EXIT=%ERRORLEVEL%"

if not "%AP_LAUNCHER_EXIT%"=="0" (
  echo.
  echo  Control Center stopped with exit code %AP_LAUNCHER_EXIT%.
  pause
)

endlocal
exit /b %AP_LAUNCHER_EXIT%
