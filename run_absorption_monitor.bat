@echo off
chcp 65001 >nul
echo ========================================
echo 大单吃货实时监测系统
echo ========================================
echo.
echo 正在启动监测程序...
echo.
python monitor_absorption_realtime.py
echo.
echo 监测已停止
pause
