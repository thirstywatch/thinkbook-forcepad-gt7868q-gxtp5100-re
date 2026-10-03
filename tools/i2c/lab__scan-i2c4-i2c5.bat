@echo off
REM ===================================================================
REM  scan-i2c4-i2c5.bat  --  扫描 I2C4 / I2C5 上的 0x5A / 0x5B
REM  【必须：右键 -> 以管理员身份运行】
REM -------------------------------------------------------------------
REM  背景：本机 5 个 Intel I2C 控制器全部有 BAR 且已启动：
REM    I2C0 7E78 BAR 0x3FFBFF95000   <- 触控板 0x2C（已知）
REM    I2C2 7E7A BAR 0x3FFBFF94000
REM    I2C3 7E7B BAR 0x3FFBFF93000
REM    I2C4 7E50 BAR 0x3FFBFF92000   <- 从未扫描
REM    I2C5 7E51 BAR 0x3FFBFF96000   <- 从未扫描
REM  目的：看 AW86927（0x5A/0x5B）是否挂在这两条上
REM  纯读设备，不写任何 I2C 从设备寄存器。
REM ===================================================================
setlocal
set "HERE=%~dp0"
set "RWE=<LAB>\touchpad-lab\rwe\Win64\Portable\Rw.exe"
set "LOG=%HERE%scan-i2c4-5-result.txt"

net session >nul 2>&1
if not "%errorlevel%"=="0" (
  echo [!] Administrator required. Right-click -^> Run as administrator.
  pause
  exit /b 1
)
if not exist "%RWE%" (
  echo [!] Rw.exe not found: %RWE%
  pause
  exit /b 1
)

echo Scanning I2C4 (0x3FBFF92000) and I2C5 (0x3FBFF96000) ...
echo Log: %LOG%
"%RWE%" /Min /Nologo /Stdout /LogFile="%LOG%" /Command="Cout ===I2C4 (7E50) BAR===;Local0=Rpci32(0,0x19,0,0x10);Local1=Rpci32(0,0x19,0,0x14);Local0=And(Local0,0xFFFFFFF0);Local1=Shl(Local1,32);LocalA=Or(Local0,Local1);LocalC=Add(LocalA,0x6C);w32(LocalC,1);Delay 5;Cout ===probe 0x5A===;LocalD=Add(LocalA,0x54);r32(LocalD);LocalE=Add(LocalA,0x04);w32(LocalE,0x5A);LocalF=Add(LocalA,0x10);w32(LocalF,0x300);Delay 6;Local0=Add(LocalA,0x80);r32(Local0);Local1=Add(LocalA,0x70);r32(Local1);Cout ===probe 0x5B===;LocalD=Add(LocalA,0x54);r32(LocalD);w32(LocalE,0x5B);w32(LocalF,0x300);Delay 6;Local0=Add(LocalA,0x80);r32(Local0);Local1=Add(LocalA,0x70);r32(Local1);Cout ===probe 0x2C(positive control)===;LocalD=Add(LocalA,0x54);r32(LocalD);w32(LocalE,0x2C);w32(LocalF,0x300);Delay 6;Local0=Add(LocalA,0x80);r32(Local0);Local1=Add(LocalA,0x70);r32(Local1);Cout ===I2C5 (7E51) BAR===;Local0=Rpci32(0,0x19,1,0x10);Local1=Rpci32(0,0x19,1,0x14);Local0=And(Local0,0xFFFFFFF0);Local1=Shl(Local1,32);LocalA=Or(Local0,Local1);LocalC=Add(LocalA,0x6C);w32(LocalC,1);Delay 5;Cout ===probe 0x5A===;LocalD=Add(LocalA,0x54);r32(LocalD);LocalE=Add(LocalA,0x04);w32(LocalE,0x5A);LocalF=Add(LocalA,0x10);w32(LocalF,0x300);Delay 6;Local0=Add(LocalA,0x80);r32(Local0);Local1=Add(LocalA,0x70);r32(Local1);Cout ===probe 0x5B===;LocalD=Add(LocalA,0x54);r32(LocalD);w32(LocalE,0x5B);w32(LocalF,0x300);Delay 6;Local0=Add(LocalA,0x80);r32(Local0);Local1=Add(LocalA,0x70);r32(Local1);Cout ===probe 0x2C(positive control)===;LocalD=Add(LocalA,0x54);r32(LocalD);w32(LocalE,0x2C);w32(LocalF,0x300);Delay 6;Local0=Add(LocalA,0x80);r32(Local0);Local1=Add(LocalA,0x70);r32(Local1);Cout ===DONE===;RwExit"

echo.
echo ===================================================================
echo  RESULT (also saved to %LOG%):
echo ===================================================================
if exist "%LOG%" ( type "%LOG%" ) else ( echo [!] no log file )
echo ===================================================================
echo.
echo  Interpretation:
echo    AB=0 (TX_ABRT_SOURCE=0) + STATUS with 0x08 (RFNE)  =^> device ACKed  ^<== FOUND
echo    AB=1 (TX_ABRT_SOURCE=1)                            =^> NAK / no device
echo.
echo  Send the text above back.
echo.
pause
