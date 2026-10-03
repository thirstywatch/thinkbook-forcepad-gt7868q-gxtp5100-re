@echo off
REM ===================================================================
REM  W1-R2  step 0 : back up + disable HVCI and the vulnerable driver
REM                  blocklist.   ADMINISTRATOR REQUIRED.
REM -------------------------------------------------------------------
REM  Touches exactly two registry values.  Everything it changes is
REM  written to state-before.txt so step9-restore.bat can undo it.
REM  Nothing else is modified.  No device is touched.
REM ===================================================================
setlocal
set "HERE=%~dp0"
set "OUT=%HERE%state-before.txt"

net session >nul 2>&1
if not "%errorlevel%"=="0" (
  echo [!] Administrator required.
  echo     Right-click this file  -^>  "Run as administrator".
  echo.
  pause
  exit /b 1
)

echo ===================================================================
echo  W1-R2 step 0 : backup + disable HVCI + blocklist
echo ===================================================================
echo.

echo [1/4] Writing current state to state-before.txt ...
>  "%OUT%" echo W1-R2 state backup   %DATE% %TIME%
>> "%OUT%" echo.
>> "%OUT%" reg query "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity" /v Enabled
>> "%OUT%" reg query "HKLM\SYSTEM\CurrentControlSet\Control\CI\Config" /v VulnerableDriverBlocklistEnable
>> "%OUT%" reg query "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard" /v EnableVirtualizationBasedSecurity
>> "%OUT%" reg query "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard" /v RequireMicrosoftSignedBootChain
>> "%OUT%" reg query "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\CredentialGuard" /v Enabled
type "%OUT%"
echo.

echo [2/4] Disabling HVCI (Core isolation / Memory integrity) ...
reg add "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity" /v Enabled /t REG_DWORD /d 0 /f
echo.

echo [3/4] Disabling the Microsoft vulnerable driver blocklist ...
reg add "HKLM\SYSTEM\CurrentControlSet\Control\CI\Config" /v VulnerableDriverBlocklistEnable /t REG_DWORD /d 0 /f
echo.

echo [4/4] Done.
echo.
echo   NEXT:  REBOOT, then run  step1-scan.bat
echo   UNDO:  run  step9-restore.bat   (at any time, also reboots)
echo.
echo   Until you restore, these protections are OFF:
echo     - HVCI / Memory integrity
echo     - Microsoft vulnerable driver blocklist
echo   Do not install or run unknown software in the meantime.
echo.
pause
