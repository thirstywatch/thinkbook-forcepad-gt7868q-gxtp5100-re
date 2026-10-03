@echo off
REM ===================================================================
REM  run-ec-all.bat  v2  (2026-10-03)    [PURE ASCII on purpose]
REM  ONE-SHOT: EC selftest -> gate -> 6-phase probe, in one window.
REM  A UAC prompt will appear - click YES.
REM
REM  v2 fix: v1 contained Chinese text; under the GBK console cmd.exe
REM  line-parsing drifted and chewed lines (even the elevation line),
REM  so no elevated window ever started. A pure-ASCII bat cannot drift.
REM  Elevation result is logged to _elev-log.txt and printed below.
REM  The elevated payload is launched from a space-free path:
REM      <HOME>\ecrun.ps1   (no quoting ambiguity anywhere)
REM ===================================================================
title EC all-in-one (selftest + 6-phase probe)
cd /d "%~dp0"

echo ============================================================
echo   EC all-in-one  -  selftest, then the 6-phase probe
echo.
echo   *** A UAC prompt will appear  -  click YES ***
echo.
echo   Stage 1: selftest (about 20 s, no action needed)
echo   Stage 2: probe (about 7-8 min, follow the on-screen prompts)
echo ============================================================
echo.

if not exist "<HOME>\ecrun.ps1" (
  echo [X] launcher not found: <HOME>\ecrun.ps1
  echo     write this down / tell the agent, then stop.
  pause
  exit /b 1
)

echo Opening the elevated window now ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "foreach ($n in @('http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY','PATH','Path')) { try { [Environment]::SetEnvironmentVariable($n,$null,'Process') } catch {} }; $m='%~dp0_elev-log.txt'; try { Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-NoExit','-File','<HOME>\ecrun.ps1' -ErrorAction Stop; 'ELEV-OK ' + (Get-Date -Format s) | Out-File -Append -LiteralPath $m } catch { 'ELEV-FAIL ' + (Get-Date -Format s) + ' :: ' + $_.Exception.Message | Out-File -Append -LiteralPath $m }"

timeout /t 2 >nul
if exist "%~dp0_elev-log.txt" type "%~dp0_elev-log.txt"

echo.
echo ------------------------------------------------------------
echo  What to do now:
echo    - If a new PowerShell window opened: follow its prompts.
echo    - If NO UAC / no new window appeared, use Plan B:
echo        1) right-click Start  -^>  open PowerShell as Administrator
echo        2) cd /d "<LAB>\touchpad-lab\poc"
echo        3) powershell -ExecutionPolicy Bypass -File .\ec-run-all.ps1
echo.
echo  Results land in:
echo    poc\_logs\ec-run-all-latest.log
echo    poc\ec-haptic-latest.txt
echo ------------------------------------------------------------
echo.
pause
