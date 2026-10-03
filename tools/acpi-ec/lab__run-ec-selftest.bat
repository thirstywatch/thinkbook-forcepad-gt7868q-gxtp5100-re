@echo off
chcp 65001 >nul
title EC 读链自检 - 不需要做任何动作
cd /d "%~dp0"
echo ============================================================
echo   EC 读链自检 将以管理员权限启动
echo.
echo   *** 看到 UAC 弹窗时，务必点"是" ***
echo.
echo   自检不需要你做任何动作（约 10 秒）
echo   通过之后，再双击 run-ec-probe.bat 跑 6 相位采集
echo ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-NoExit','-File','%~dp0ec-selftest.ps1'"

echo.
echo ----------------------------------------------------------------
echo  如果新窗口已打开并打印了 [1]-[5] 各步结果：
echo    把最后几行（尤其是 HR=0x... 和读到的 EC 字节）发回即可。
echo.
echo  如果没有弹 UAC 窗口，说明提权被拒了 —— 请改用下面的方法。
echo ----------------------------------------------------------------
echo.
echo 【备选方法】自己开管理员 PowerShell：
echo     右键开始菜单 -^> PowerShell -^> 以管理员身份运行
echo     然后粘贴这两行：
echo.
echo     cd /d "%~dp0"
echo     powershell -ExecutionPolicy Bypass -File .\ec-selftest.ps1
echo.
pause
