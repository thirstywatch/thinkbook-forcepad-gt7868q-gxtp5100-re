@echo off
REM ===================================================================
REM  W1-R2  step 1 : verify the two values are off, then run the
REM                  READ-ONLY identity scan with RWEverything.
REM                  ADMINISTRATOR REQUIRED.
REM -------------------------------------------------------------------
REM  This step does NOT write any I2C device register.  It only reads
REM  the I2C controller's own registers.
REM ===================================================================
setlocal
set "HERE=%~dp0"
set "RWE=<LAB>\touchpad-lab\rwe\Win64\Portable\Rw.exe"
set "SCAN=<LAB>\touchpad-lab\poc\rwe-cmd\00-scan.rw"
set "LOG=%HERE%scan-result.txt"

net session >nul 2>&1
if not "%errorlevel%"=="0" (
  echo [!] Administrator required. Right-click -^> Run as administrator.
  echo.
  pause
  exit /b 1
)

echo ===================================================================
echo  W1-R2 step 1 : verify + read-only identity scan
echo ===================================================================
echo.

echo [1/4] Verifying the two security values are now 0 ...
echo --- HVCI ---
reg query "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity" /v Enabled
echo --- blocklist ---
reg query "HKLM\SYSTEM\CurrentControlSet\Control\CI\Config" /v VulnerableDriverBlocklistEnable
echo.
echo   Both must read 0x0. If not, the setting is firmware enforced:
echo   you would have to disable Secure Boot in BIOS. STOP here and report.
echo.

if not exist "%RWE%" (
  echo [!] Rw.exe not found at: %RWE%
  pause
  exit /b 1
)
if not exist "%SCAN%" (
  echo [!] 00-scan.rw not found at: %SCAN%
  pause
  exit /b 1
)

echo [2/4] Checking that the RWEverything driver can load ...
echo   (Rw.exe will open a window. If it reports "Driver cannot be loaded",
echo    close it and STOP here - report that message instead.)
start "" "%RWE%"
timeout /t 6 >nul
echo.

echo [3/4] Running the read-only scan script ...
echo       (If the GUI window is in the way, that is fine - this runs in
echo        the same process family. Close the GUI window afterwards.)
"%RWE%" /Command="%SCAN%" /LogFile="%LOG%" /LogDate /LogTime /Stdout
echo.

echo [4/4] Result:
echo ===================================================================
if exist "%LOG%" ( type "%LOG%" ) else ( echo [!] no log file produced )
echo ===================================================================
echo.
echo   Send the text above back (or the file %LOG%).
echo.
echo   REMEMBER:  after we are done, run step9-restore.bat
echo.
pause
