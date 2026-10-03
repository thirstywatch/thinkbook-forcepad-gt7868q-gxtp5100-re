@echo off
REM ===================================================================
REM  W1-R2  step 0b : enable test mode / disable driver integrity
REM                   checks so that RwDrv.sys can load.
REM                   ADMINISTRATOR REQUIRED.
REM -------------------------------------------------------------------
REM  WHY THIS IS NEEDED (measured 2026-10-03):
REM    step0 already turned OFF  HVCI  and  VulnerableDriverBlocklistEnable.
REM    RwDrv.sys STILL refuses to load, with a NEW CodeIntegrity event:
REM      id=3076  "... did not meet the Authenticode signing level
REM                requirements or violated code integrity policy"
REM    Measured facts:
REM      - RwDrv.sys signature itself is VALID
REM        (Signer CN=ChongKim Chan, issued by GlobalSign CodeSigning CA-G2)
REM      - the string "ChongKim" IS present inside
REM        C:\Windows\System32\CodeIntegrity\driversipolicy.p7b
REM        (Microsoft driver blocklist policy data)
REM      - the blocklist registry value alone does NOT stop that policy
REM    => the remaining blocker is kernel driver signature / CI enforcement.
REM
REM  Secure Boot is already OFF on this machine
REM  (UEFISecureBootEnabled = 0), so no BIOS trip is needed.
REM
REM  Touch is limited to two BCD switches.  step9-restore.bat undoes them.
REM ===================================================================
setlocal

net session >nul 2>&1
if not "%errorlevel%"=="0" (
  echo [!] Administrator required.
  echo     Right-click this file  -^>  "Run as administrator".
  echo.
  pause
  exit /b 1
)

echo ===================================================================
echo  W1-R2 step 0b : allow non-WHQL kernel drivers (DSE relaxed)
echo ===================================================================
echo.
echo BEFORE:
bcdedit /enum "{current}" | findstr /I "nointegritychecks testsigning"
echo   (blank line above = both currently unset)
echo.

echo [1/3] Setting  nointegritychecks on  (skip CI integrity checks) ...
bcdedit /set nointegritychecks on
echo.
echo [2/3] Setting  testsigning on  (accept test-signed drivers) ...
bcdedit /set testsigning on
echo.

echo [3/3] Verifying:
bcdedit /enum "{current}" | findstr /I "nointegritychecks testsigning"
echo.

echo ===================================================================
echo  Done.  NOW REBOOT.
echo  After reboot you will see a "Test Mode" watermark on the desktop.
echo  Then run step1-scan.bat  (or just tell the agent, it can drive Rw itself).
echo.
echo  TO UNDO EVERYTHING:  step9-restore.bat
echo ===================================================================
echo.
echo  While this is active, driver signature enforcement is relaxed:
echo    - any kernel driver can be loaded
echo    - do NOT install or run unknown software
echo.
pause
