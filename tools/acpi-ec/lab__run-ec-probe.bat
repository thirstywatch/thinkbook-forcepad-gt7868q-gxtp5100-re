@echo off
chcp 65001 >nul
title EC差分探针 - 采集开始后请按提示做动作
cd /d "%~dp0"
echo ============================================================
echo   EC 差分探针 将以管理员权限启动
echo.
echo   *** 看到 UAC 弹窗时，务必点"是" ***
echo       （上次没点"是"，脚本直接退出，什么都没留下）
echo.
echo   整个过程约 6-8 分钟，每个阶段会提示你要做什么
echo   只读 EC RAM，不会写入任何东西
echo ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-NoExit','-File','%~dp0ec-haptic-probe.ps1'"

echo.
echo ----------------------------------------------------------------
echo  如果新窗口已经打开并显示了阶段提示，采集正在进行。
echo  结束后结果在同目录的  ec-haptic-latest.txt
echo.
echo  如果没有弹 UAC 窗口，说明提权被拒了 —— 请改用下面的方法。
echo ----------------------------------------------------------------
echo.
echo 【备选方法】自己开管理员 PowerShell：
echo     右键开始菜单 -^> PowerShell -^> 以管理员身份运行
echo     然后粘贴这一行：
echo.
echo     cd /d "%~dp0"
echo     powershell -ExecutionPolicy Bypass -File .\ec-haptic-probe.ps1
echo.
pause