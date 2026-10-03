@echo off
REM ===================================================================
REM  wake-and-scan-i2c4.bat  --  先唤醒 I2C4/I2C5 到 D0，再扫描
REM  【必须：右键 -> 以管理员身份运行】
REM -------------------------------------------------------------------
REM  上一轮发现：I2C4 的 MMIO 全部返回 0xFFFFFFFF
REM   => 不是"设备 NAK"，而是控制器处于【D3 掉电态】(LPSS 在 D3 时 BAR 不可访问)
REM   => 先 restart-device 让它回 D0，再扫。
REM
REM  本脚本只读 I2C 从设备（不发任何写命令给从设备）。
REM ===================================================================
setlocal enabledelayedexpansion
set "HERE=%~dp0"
set "RWE=<LAB>\touchpad-lab\rwe\Win64\Portable\Rw.exe"
set "LOG=%HERE%scan-i2c4-wake-result.txt"

net session >nul 2>&1
if not "%errorlevel%"=="0" (
  echo [!] Administrator required. Right-click -^> Run as administrator.
  pause
  exit /b 1
)

echo ============================================================
echo  STEP 1/4  read PMCSR (power state) of all 5 controllers
echo ============================================================
"%RWE%" /Min /Nologo /Stdout /LogFile="%LOG%" /Command="Cout PMCSR-0x84;(PMCSR bit0-1: 0=D0 3=D3);Local0=Rpci32(0,0x15,0,0x84);r32(Local0);Local0=Rpci32(0,0x15,2,0x84);r32(Local0);Local0=Rpci32(0,0x15,3,0x84);r32(Local0);Local0=Rpci32(0,0x19,0,0x84);r32(Local0);Local0=Rpci32(0,0x19,1,0x84);r32(Local0);Cout BARS;(I2C0);Local0=Rpci32(0,0x15,0,0x10);r32(Local0);(I2C4);Local0=Rpci32(0,0x19,0,0x10);r32(Local0);Local0=Rpci32(0,0x19,0,0x14);r32(Local0);Cout DONE1;RwExit"

echo.
echo ============================================================
echo  STEP 2/4  restart I2C4 (7E50) and I2C5 (7E51) to bring D0
echo ============================================================
pnputil /restart-device "PCI\VEN_8086&DEV_7E50&SUBSYS_383617AA&REV_20\3&11583659&0&C8"
pnputil /restart-device "PCI\VEN_8086&DEV_7E51&SUBSYS_383717AA&REV_20\3&11583659&0&C9"
echo   (waiting 4 s ...)
timeout /t 4 >nul

echo.
echo ============================================================
echo  STEP 3/4  re-read BAR + IC_CON of I2C4 (is MMIO alive now?)
echo ============================================================
"%RWE%" /Min /Nologo /Stdout /LogFile="%LOG%" /Command="Cout I2C4-BAR-recheck;Local0=Rpci32(0,0x19,0,0x10);Local1=Rpci32(0,0x19,0,0x14);Local0=And(Local0,0xFFFFFFF0);Local1=Shl(Local1,32);LocalA=Or(Local0,Local1);LocalB=Add(LocalA,0xFC);r32(LocalB);Cout ^(expect 0x44570140 = DesignWare id^);Cout I2C5-BAR-recheck;Local0=Rpci32(0,0x19,1,0x10);Local1=Rpci32(0,0x19,1,0x14);Local0=And(Local0,0xFFFFFFF0);Local1=Shl(Local1,32);LocalC=Or(Local0,Local1);LocalD=Add(LocalC,0xFC);r32(LocalD);Cout DONE2;RwExit"

echo.
echo ============================================================
echo  STEP 4/4  scan 0x5A / 0x5B / 0x2C on I2C4
echo ============================================================
"%RWE%" /Min /Nologo /Stdout /LogFile="%LOG%" /Command="Cout ===I2C4 scan after wake===;Local0=Rpci32(0,0x19,0,0x10);Local1=Rpci32(0,0x19,0,0x14);Local0=And(Local0,0xFFFFFFF0);Local1=Shl(Local1,32);LocalA=Or(Local0,Local1);LocalC=Add(LocalA,0x6C);w32(LocalC,1);Delay 8;Cout -- IC_CON --;r32(LocalA);Cout -- probe 0x5A --;LocalD=Add(LocalA,0x54);r32(LocalD);LocalE=Add(LocalA,0x04);w32(LocalE,0x5A);LocalF=Add(LocalA,0x10);w32(LocalF,0x300);Delay 8;Local0=Add(LocalA,0x80);r32(Local0);Local1=Add(LocalA,0x70);r32(Local1);Cout -- probe 0x5B --;r32(LocalD);w32(LocalE,0x5B);w32(LocalF,0x300);Delay 8;r32(Local0);r32(Local1);Cout -- probe 0x2C (control) --;r32(LocalD);w32(LocalE,0x2C);w32(LocalF,0x300);Delay 8;r32(Local0);r32(Local1);Cout DONE3;RwExit"

echo.
echo ============================================================
echo  RESULT (also being written to %LOG%)
echo ============================================================
echo  How to read:
echo    MMIO alive?  IC_COMP_TYPE(+0xFC) should read 0x44570140
echo    device ACK?  TX_ABRT_SOURCE(+0x80) = 0  AND  STATUS(+0x70) has 0x08
echo    no device?   TX_ABRT_SOURCE(+0x80) = 1   (or still FFFFFFFF if D3)
echo.
pause
