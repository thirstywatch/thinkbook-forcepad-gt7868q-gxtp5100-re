@echo off
REM ===================================================================
REM  W1-R2  step 9 : restore the original security settings from
REM                  state-before.txt, then reboot.  ADMIN REQUIRED.
REM ===================================================================
setlocal
set "HERE=%~dp0"
set "IN=%HERE%state-before.txt"

net session >nul 2>&1
if not "%errorlevel%"=="0" (
  echo [!] Administrator required. Right-click -^> Run as administrator.
  echo.
  pause
  exit /b 1
)

echo ===================================================================
echo  W1-R2 step 9 : restore HVCI + blocklist, then reboot
echo ===================================================================
echo.

echo Restoring HVCI = 1 ...
reg add "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity" /v Enabled /t REG_DWORD /d 1 /f
echo Restoring blocklist = 1 ...
reg add "HKLM\SYSTEM\CurrentControlSet\Control\CI\Config" /v VulnerableDriverBlocklistEnable /t REG_DWORD /d 1 /f
echo.
echo Reverting BCD test-mode switches (step 0b) ...
bcdedit /set nointegritychecks off
bcdedit /set testsigning off
echo.

echo Current state (should be 0x1 / 0x1):
reg query "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity" /v Enabled
reg query "HKLM\SYSTEM\CurrentControlSet\Control\CI\Config" /v VulnerableDriverBlocklistEnable
echo.

if exist "%IN%" (
  echo Original backup for reference:
  type "%IN%"
) else (
  echo [!] state-before.txt not found - the defaults above were used.
)
echo.
echo If you ever changed Secure Boot in BIOS, turn it back ON now.
echo.
echo Rebooting in 15 seconds. Press Ctrl+C to cancel.
timeout /t 15
shutdown /r /t 0
