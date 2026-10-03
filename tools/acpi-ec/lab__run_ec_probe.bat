@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ec_probe_pawnio.ps1"
echo.
echo === ????????? ===
pause >nul

