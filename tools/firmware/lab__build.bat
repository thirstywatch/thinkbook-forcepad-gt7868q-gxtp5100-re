@echo off
rem ============================================================
rem  TpadAcpi driver build (MSVC only, no EDK2 / no NASM needed)
rem  Output: TpadAcpiProbe.efi (probe), TpadAcpiPatch.efi (real driver)
rem ============================================================
setlocal
set "VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat"
if not exist "%VCVARS%" goto no_vs
echo [1/3] init MSVC x64 ...
call "%VCVARS%" x64 >nul
if errorlevel 1 goto vs_fail
cd /d "%~dp0"
echo [2/3] build TpadAcpiProbe.efi ...
cl /nologo /c /GS- /Gs9999999 /Zl /O2 /W3 /Fo:TpadAcpiProbe.obj TpadAcpiProbe.c
if errorlevel 1 goto fail
link /nologo /NODEFAULTLIB /SUBSYSTEM:EFI_BOOT_SERVICE_DRIVER /ENTRY:TpadAcpiProbeEntry /MACHINE:X64 /OUT:TpadAcpiProbe.efi TpadAcpiProbe.obj
if errorlevel 1 goto fail
echo [3/3] build TpadAcpiPatch.efi ...
cl /nologo /c /GS- /Gs9999999 /Zl /O2 /W3 /Fo:TpadAcpiPatch.obj TpadAcpiPatch.c
if errorlevel 1 goto fail
link /nologo /NODEFAULTLIB /SUBSYSTEM:EFI_BOOT_SERVICE_DRIVER /ENTRY:TpadAcpiPatchEntry /MACHINE:X64 /OUT:TpadAcpiPatch.efi TpadAcpiPatch.obj
if errorlevel 1 goto fail
echo [4/4] build TpadBootTest.efi (application) ...
cl /nologo /c /GS- /Gs9999999 /Zl /O2 /W3 /Fo:TpadBootTest.obj TpadBootTest.c
if errorlevel 1 goto fail
link /nologo /NODEFAULTLIB /SUBSYSTEM:EFI_APPLICATION /ENTRY:TpadBootTestEntry /MACHINE:X64 /OUT:TpadBootTest.efi TpadBootTest.obj
if errorlevel 1 goto fail
echo [5/5] build TpadClear.efi (application) ...
cl /nologo /c /GS- /Gs9999999 /Zl /O2 /W3 /Fo:TpadClear.obj TpadClear.c
if errorlevel 1 goto fail
link /nologo /NODEFAULTLIB /SUBSYSTEM:EFI_APPLICATION /ENTRY:TpadClearEntry /MACHINE:X64 /OUT:TpadClear.efi TpadClear.obj
if errorlevel 1 goto fail
echo [6/6] build TpadInstall.efi (application) ...
cl /nologo /c /GS- /Gs9999999 /Zl /O2 /W3 /Fo:TpadInstall.obj TpadInstall.c
if errorlevel 1 goto fail
link /nologo /NODEFAULTLIB /SUBSYSTEM:EFI_APPLICATION /ENTRY:TpadInstallEntry /MACHINE:X64 /OUT:TpadInstall.efi TpadInstall.obj
if errorlevel 1 goto fail
del /q TpadAcpiProbe.obj TpadAcpiPatch.obj TpadBootTest.obj TpadClear.obj TpadInstall.obj 2>nul
echo [post] clean IMAGE_FILE_DLL ...
python fix_pe.py TpadAcpiProbe.efi TpadAcpiPatch.efi TpadBootTest.efi TpadClear.efi TpadInstall.efi
echo.
echo ==== BUILD OK ====
dir /b *.efi
endlocal
exit /b 0
:no_vs
echo [ERROR] vcvarsall.bat not found: %VCVARS%
exit /b 1
:vs_fail
echo [ERROR] vcvarsall init failed
exit /b 1
:fail
echo [ERROR] build failed
exit /b 1
