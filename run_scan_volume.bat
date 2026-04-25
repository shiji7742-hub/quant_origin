@echo off
chcp 65001 >nul
cd /d "%~dp0"
python scan_volume_stocks.py
pause
