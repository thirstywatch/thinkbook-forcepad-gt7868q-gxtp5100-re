@echo off
rem ============================================================================
rem  put_to_esp.bat -- copy the ACPI patch driver into the built-in ESP.
rem
rem  WHY: the firmware returns EFI_INVALID_PARAMETER when a UEFI app tries to
rem       create files on the ESP. Windows can do it (block device driver path).
rem
rem  USAGE: just double-click it. It asks for administrator rights by itself.
rem         (mountvol /s requires admin.)
rem
rem  IT ONLY: mounts the ESP, creates \EFI\Tpad, copies one 3 KB .efi there,
rem           and unmounts. It does NOT touch any Windows boot file.
rem ============================================================================
setlocal EnableExtensions EnableDelayedExpansion
title put_to_esp

rem ---- self-elevate ----
net session >nul 2>&1
if errorlevel 1 (
  echo.
  echo Requesting administrator rights...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

set "BASE=%~dp0"
set "SRC="

rem ---- locate the driver file (several known locations) ----
if exist "%BASE%usb\EFI\Tpad\TpadAcpiProbe.efi"                 set "SRC=%BASE%usb\EFI\Tpad\TpadAcpiProbe.efi"
if not defined SRC if exist "%BASE%TpadAcpiProbe.efi"           set "SRC=%BASE%TpadAcpiProbe.efi"
if not defined SRC if exist "%BASE%standalone\TpadAcpiPatch.efi" set "SRC=%BASE%standalone\TpadAcpiPatch.efi"
if not defined SRC if exist "%~1"                                set "SRC=%~1"

echo.
echo === put_to_esp ===
if not defined SRC (
  echo [ERROR] driver file not found. Looked in:
  echo         %BASE%usb\EFI\Tpad\TpadAcpiProbe.efi
  echo         %BASE%TpadAcpiProbe.efi
  echo         %BASE%standalone\TpadAcpiPatch.efi
  echo.
  echo You can also drag a .efi file onto this script.
  pause
  exit /b 1
)
echo source : %SRC%

rem ---- mount the ESP on a free drive letter ----
set "ESP="
for %%D in (X Y Z W V U) do (
  if not defined ESP (
    mountvol %%D: /s >nul 2>&1
    if not errorlevel 1 set "ESP=%%D:"
  )
)

if not defined ESP (
  echo [ERROR] cannot mount the EFI System Partition.
  echo         Close any DiskGenius / Explorer windows on hidden drives and retry.
  pause
  exit /b 1
)
echo esp    : %ESP%

rem ---- create directory + copy ----
echo.
if not exist "%ESP%\EFI\Tpad" mkdir "%ESP%\EFI\Tpad"
copy /Y "%SRC%" "%ESP%\EFI\Tpad\TpadAcpiProbe.efi" >nul
if errorlevel 1 (
  echo [ERROR] copy failed.
  mountvol %ESP% /d >nul 2>&1
  pause
  exit /b 1
)

echo === %ESP%\EFI\Tpad now contains: ===
dir /b "%ESP%\EFI\Tpad"
echo.
certutil -hashfile "%ESP%\EFI\Tpad\TpadAcpiProbe.efi" MD5 2>nul | findstr /r "^[0-9a-fA-F]"

rem ---- unmount ----
mountvol %ESP% /d >nul 2>&1
echo.
echo === DONE - ESP unmounted ===
echo Next: reboot, press F12, pick the USB stick, run TpadInstall (steps [5] and [6]).
echo.
pause
endlocal
