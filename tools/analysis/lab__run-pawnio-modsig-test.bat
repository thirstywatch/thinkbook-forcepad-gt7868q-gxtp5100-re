@echo off
REM ===================================================================
REM  PawnIO module-signature gate test  (W2 route gate)
REM  See: 2026-10-01-software-RE-book section 19.33.6
REM  Pure ASCII only.  ASCII-only on purpose (PowerShell 5.1 GBK issue).
REM
REM  What it does: tries to load a 1-bit-modified copy of the signed
REM  PawnIO module Echo.bin. If that loads, PawnIO does NOT verify
REM  module signatures => route W2 is immediately feasible.
REM
REM  Read-only. Does not touch the touchpad, does not write any device.
REM ===================================================================

setlocal
set "HERE=%~dp0"
set "PY=<HOME>\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PY%" set "PY=python"
set "LOG=%HERE%pawnio-modsig-result.txt"

net session >nul 2>&1
if %errorlevel%==0 goto :run

echo [i] Need administrator. A UAC prompt will appear - click Yes.
powershell -NoProfile -Command "Start-Process -FilePath '%PY%' -ArgumentList '\"%HERE%pawnio_modsig_test.py\"' -Verb RunAs"
echo [i] After it finishes, the result is in:
echo     %LOG%
echo.
pause
exit /b

:run
echo [i] Running as administrator...
"%PY%" "%HERE%pawnio_modsig_test.py"
echo.
echo [i] Log saved to: %LOG%
pause
