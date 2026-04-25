@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 启动逐笔成交查看器 Web应用...
echo.
python tick_viewer_app.py
pause
