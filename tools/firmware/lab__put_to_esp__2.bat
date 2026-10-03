@echo off
rem ============================================================================
rem  put_to_esp.bat -- copy the ACPI patch driver into the built-in ESP.
rem
rem  WHY: the firmware refuses to let a UEFI app create files on the ESP
rem       (status 0x800000000000000F = WRITE_PROTECTED). So we put the file there
rem       from Windows instead - Windows can mount the ESP with mountvol.
rem
rem  HOW TO RUN: right-click this file -> "Run as administrator".
rem              (mountvol /s requires admin. No admin = it will fail.)
rem
rem  WHAT IT DOES:
rem    1. mount the EFI System Partition as X:
rem    2. create \EFI\Tpad\ on it
rem    3. copy TpadAcpiProbe.efi into it
rem    4. unmount X:
rem  IT DOES NOT TOUCH any Windows boot files.
rem ============================================================================
setlocal

set "SRC=%~1"
if "%SRC%"=="" set "SRC=%~dp0..\usb\EFI\Tpad\TpadAcpiProbe.efi"
if not exist "%SRC%" set "SRC=%~dp0TpadAcpiProbe.efi"

echo.
echo === put_to_esp ===
echo source file : %SRC%
if not exist "%SRC%" (
  echo.
  echo [ERROR] source file not found.
  echo Pass it as argument:  put_to_esp.bat "D:\somewhere\TpadAcpiProbe.efi"
  pause
  exit /b 1
)

echo.
echo mounting EFI System Partition as X: ...
mountvol X: /s
if errorlevel 1 (
  echo.
  echo [ERROR] mountvol failed - are you running as Administrator?
  pause
  exit /b 1
)

echo.
echo creating X:\EFI\Tpad ...
if not exist "X:\EFI\Tpad" mkdir "X:\EFI\Tpad"

echo copying ...
copy /Y "%SRC%" "X:\EFI\Tpad\TpadAcpiProbe.efi"

echo.
echo === content of X:\EFI\Tpad ===
dir "X:\EFI\Tpad"

echo.
echo unmounting X: ...
mountvol X: /d

echo.
echo === DONE ===
echo Now reboot, press F12, pick the USB stick, and re-run the installer app
echo (it will register the ESP path in step [5]).
echo.
pause
endlocal
