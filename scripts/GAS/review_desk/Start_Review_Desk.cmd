@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_preview.ps1"
if errorlevel 1 (
  echo.
  echo Review Desk could not be started. See the message above.
  pause
)
endlocal
