@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0smbus_probe.ps1"
echo.
echo === done, press any key ===
pause >nul
