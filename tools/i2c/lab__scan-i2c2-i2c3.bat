@echo off
REM ===================================================================
REM  scan-i2c2-i2c3.bat   v3   (2026-10-03)      [PURE-ASCII / CRLF]
REM  Scan I2C2 / I2C3 : BAR check FIRST; address probe only if usable.
REM  MUST RUN AS ADMINISTRATOR (right-click -> Run as administrator)
REM ===================================================================
REM  HISTORY
REM   v1 : used out-of-range Rw variable names (letters past LocalF)
REM        -> never executed. archived: scan-i2c2-i2c3.bat.v1-original
REM   v2 : ran 2026-10-03 11:45 (see _logs\scan-i2c2-3-console-output-
REM        20261003.txt). Found BAR base = 0 for BOTH controllers.
REM        Defects found in v2: (a) UTF-8 Chinese comments caused a cmd
REM        line-offset drift under a GBK console - comment fragments
REM        were executed as commands (cosmetic; functional lines all
REM        ran); (b) this portable Rw build silently ignores /LogFile=
REM        when the path contains spaces ("no log file produced").
REM        archived: scan-i2c2-i2c3.bat.v2-utf8-ran
REM   v3 : this file. Pure ASCII + CRLF; stdout redirect for logs;
REM        HARD GATE: if BAR base == 0 the script SKIPS steps 2-3.
REM        (Without a valid BAR, "register" accesses land in low
REM        physical memory and read back garbage or our own writes.)
REM ===================================================================
REM  KNOWN STATE (2026-10-03): I2C2/I2C3 BAR base = 0 (unassigned);
REM   pnputil /restart-device succeeds but does NOT assign a BAR
REM   => expected result here is NOT HOST-ACCESSIBLE (same as I2C5).
REM  SAFETY: touches only the I2C controller's own registers, and only
REM   when the BAR is valid. No I2C slave register is ever written.
REM  REFERENCE: book sections 19.36 / 19.37.
REM ===================================================================
setlocal
set "HERE=%~dp0"
set "RWE=<LAB>\touchpad-lab\rwe\Win64\Portable\Rw.exe"
set "LOG=%HERE%scan-i2c2-3-result.txt"
set "FP=%HERE%scan-i2c2-3-fingerprint.txt"

net session >nul 2>&1
if not "%errorlevel%"=="0" (
  echo [!] Administrator required. Right-click this file -^> "Run as administrator".
  pause
  exit /b 1
)
if not exist "%RWE%" (
  echo [!] Rw.exe not found: %RWE%
  pause
  exit /b 1
)
tasklist /FI "IMAGENAME eq Rw.exe" 2>nul | findstr /I "Rw.exe" >nul
if not errorlevel 1 (
  echo [!] Another Rw.exe is already running - close it first.
  echo     Rw is single-instance; a new start would only focus the old window.
  pause
  exit /b 1
)

echo ============================================================
echo  STEP 1/3  I2C2 / I2C3 : BAR + IC_COMP_TYPE (before restart)
echo ============================================================
"%RWE%" /Min /Nologo /Stdout /Command="Cout --I2C2 0:15.2--;Local0=Rpci32(0,0x15,2,0x10);Local1=Rpci32(0,0x15,2,0x14);Local0=And(Local0,0xFFFFFFF0);Local1=Shl(Local1,32);LocalA=Or(Local0,Local1);Cout BARBASE=%Lah;LocalB=Add(LocalA,0xFC);r32(LocalB);Cout --I2C3 0:15.3--;Local0=Rpci32(0,0x15,3,0x10);Local1=Rpci32(0,0x15,3,0x14);Local0=And(Local0,0xFFFFFFF0);Local1=Shl(Local1,32);LocalA=Or(Local0,Local1);Cout BARBASE=%Lah;LocalB=Add(LocalA,0xFC);r32(LocalB);Cout STEP1-DONE;RwExit" > "%FP%" 2>&1
if exist "%FP%" ( type "%FP%" ) else ( echo [!] no output file from STEP1 )
for %%A in ("%FP%") do if %%~zA LSS 10 (
  echo [!] STEP1 produced no output. Rw likely failed to start. Report this and stop.
  goto :final
)
echo.

findstr /C:"BARBASE=0" "%FP%" >nul 2>&1
if not errorlevel 1 (
  echo [!] BAR base = 0  ==^> NO address window assigned ==^> NOT host-accessible.
  echo     Skipping STEP 2/3 on purpose. Report this result and stop.
  echo     Without a valid BAR the probe would write into low physical memory.
  goto :final
)

echo ============================================================
echo  STEP 2/3  restart I2C2 / I2C3 (in case they sit in D3)
echo ============================================================
pnputil /restart-device "PCI\VEN_8086&DEV_7E7A&SUBSYS_383217AA&REV_20\3&11583659&0&AA"
pnputil /restart-device "PCI\VEN_8086&DEV_7E7B&SUBSYS_383117AA&REV_20\3&11583659&0&AB"
echo   a device on these buses may blink once - that is expected
echo   waiting 5 s ...
timeout /t 5 >nul

echo.
echo ============================================================
echo  STEP 3/3  full scan AFTER restart
echo    probe: 0x10 0x1C (controls) / 0x2C / 0x43 / 0x50 / 0x5A / 0x5B
echo ============================================================
"%RWE%" /Min /Nologo /Stdout /Command="Cout ===I2C2 0:15.2===;Local0=Rpci32(0,0x15,2,0x10);Local1=Rpci32(0,0x15,2,0x14);Local0=And(Local0,0xFFFFFFF0);Local1=Shl(Local1,32);LocalA=Or(Local0,Local1);LocalB=Add(LocalA,0xFC);r32(LocalB);LocalC=Add(LocalA,0x6C);w32(LocalC,1);Delay 5;Cout --0x10--;LocalD=Add(LocalA,0x54);r32(LocalD);LocalE=Add(LocalA,0x04);w32(LocalE,0x10);LocalF=Add(LocalA,0x10);w32(LocalF,0x300);Delay 6;Local0=Add(LocalA,0x80);r32(Local0);Local1=Add(LocalA,0x70);r32(Local1);r32(LocalF);Cout --0x1C--;LocalD=Add(LocalA,0x54);r32(LocalD);LocalE=Add(LocalA,0x04);w32(LocalE,0x1C);LocalF=Add(LocalA,0x10);w32(LocalF,0x300);Delay 6;Local0=Add(LocalA,0x80);r32(Local0);Local1=Add(LocalA,0x70);r32(Local1);r32(LocalF);Cout --0x2C--;LocalD=Add(LocalA,0x54);r32(LocalD);LocalE=Add(LocalA,0x04);w32(LocalE,0x2C);LocalF=Add(LocalA,0x10);w32(LocalF,0x300);Delay 6;Local0=Add(LocalA,0x80);r32(Local0);Local1=Add(LocalA,0x70);r32(Local1);r32(LocalF);Cout --0x43--;LocalD=Add(LocalA,0x54);r32(LocalD);LocalE=Add(LocalA,0x04);w32(LocalE,0x43);LocalF=Add(LocalA,0x10);w32(LocalF,0x300);Delay 6;Local0=Add(LocalA,0x80);r32(Local0);Local1=Add(LocalA,0x70);r32(Local1);r32(LocalF);Cout --0x50--;LocalD=Add(LocalA,0x54);r32(LocalD);LocalE=Add(LocalA,0x04);w32(LocalE,0x50);LocalF=Add(LocalA,0x10);w32(LocalF,0x300);Delay 6;Local0=Add(LocalA,0x80);r32(Local0);Local1=Add(LocalA,0x70);r32(Local1);r32(LocalF);Cout --0x5A--;LocalD=Add(LocalA,0x54);r32(LocalD);LocalE=Add(LocalA,0x04);w32(LocalE,0x5A);LocalF=Add(LocalA,0x10);w32(LocalF,0x300);Delay 6;Local0=Add(LocalA,0x80);r32(Local0);Local1=Add(LocalA,0x70);r32(Local1);r32(LocalF);Cout --0x5B--;LocalD=Add(LocalA,0x54);r32(LocalD);LocalE=Add(LocalA,0x04);w32(LocalE,0x5B);LocalF=Add(LocalA,0x10);w32(LocalF,0x300);Delay 6;Local0=Add(LocalA,0x80);r32(Local0);Local1=Add(LocalA,0x70);r32(Local1);r32(LocalF);Cout ===I2C3 0:15.3===;Local0=Rpci32(0,0x15,3,0x10);Local1=Rpci32(0,0x15,3,0x14);Local0=And(Local0,0xFFFFFFF0);Local1=Shl(Local1,32);LocalA=Or(Local0,Local1);LocalB=Add(LocalA,0xFC);r32(LocalB);LocalC=Add(LocalA,0x6C);w32(LocalC,1);Delay 5;Cout --0x10--;LocalD=Add(LocalA,0x54);r32(LocalD);LocalE=Add(LocalA,0x04);w32(LocalE,0x10);LocalF=Add(LocalA,0x10);w32(LocalF,0x300);Delay 6;Local0=Add(LocalA,0x80);r32(Local0);Local1=Add(LocalA,0x70);r32(Local1);r32(LocalF);Cout --0x1C--;LocalD=Add(LocalA,0x54);r32(LocalD);LocalE=Add(LocalA,0x04);w32(LocalE,0x1C);LocalF=Add(LocalA,0x10);w32(LocalF,0x300);Delay 6;Local0=Add(LocalA,0x80);r32(Local0);Local1=Add(LocalA,0x70);r32(Local1);r32(LocalF);Cout --0x2C--;LocalD=Add(LocalA,0x54);r32(LocalD);LocalE=Add(LocalA,0x04);w32(LocalE,0x2C);LocalF=Add(LocalA,0x10);w32(LocalF,0x300);Delay 6;Local0=Add(LocalA,0x80);r32(Local0);Local1=Add(LocalA,0x70);r32(Local1);r32(LocalF);Cout --0x43--;LocalD=Add(LocalA,0x54);r32(LocalD);LocalE=Add(LocalA,0x04);w32(LocalE,0x43);LocalF=Add(LocalA,0x10);w32(LocalF,0x300);Delay 6;Local0=Add(LocalA,0x80);r32(Local0);Local1=Add(LocalA,0x70);r32(Local1);r32(LocalF);Cout --0x50--;LocalD=Add(LocalA,0x54);r32(LocalD);LocalE=Add(LocalA,0x04);w32(LocalE,0x50);LocalF=Add(LocalA,0x10);w32(LocalF,0x300);Delay 6;Local0=Add(LocalA,0x80);r32(Local0);Local1=Add(LocalA,0x70);r32(Local1);r32(LocalF);Cout --0x5A--;LocalD=Add(LocalA,0x54);r32(LocalD);LocalE=Add(LocalA,0x04);w32(LocalE,0x5A);LocalF=Add(LocalA,0x10);w32(LocalF,0x300);Delay 6;Local0=Add(LocalA,0x80);r32(Local0);Local1=Add(LocalA,0x70);r32(Local1);r32(LocalF);Cout --0x5B--;LocalD=Add(LocalA,0x54);r32(LocalD);LocalE=Add(LocalA,0x04);w32(LocalE,0x5B);LocalF=Add(LocalA,0x10);w32(LocalF,0x300);Delay 6;Local0=Add(LocalA,0x80);r32(Local0);Local1=Add(LocalA,0x70);r32(Local1);r32(LocalF);Cout DONE2;RwExit" > "%LOG%" 2>&1
if exist "%LOG%" ( type "%LOG%" ) else ( echo [!] no output file from STEP3 )
echo ============================================================
echo.
echo  How to read:
echo    IC_COMP_TYPE = 44570140  =^> controller alive
echo    IC_COMP_TYPE = FFFFFFFF  =^> controller NOT powered (like I2C4)
echo    BAR base = 0             =^> NOT accessible (like I2C5 / 2026-10-03)
echo    ABRT(+0x80)=0 AND STATUS(+0x70) has 0x08  =^> device ACKed (FOUND)
echo    ABRT(+0x80)=1 (7B_ADDR_NOACK)             =^> NAK - no device
echo    !!! If every address shows the SAME values, the probe is void
echo        (check the BAR first). Identical reads everywhere = dead probe.

:final
echo.
echo  Files: %LOG% ; %FP%
echo  REMINDER: when ALL experiments are done, run
echo    poc\W1-r2\step9-restore.bat   (restores HVCI / blocklist / BCD)
echo.
pause
