@echo off
chcp 65001 >nul
echo ========================================
echo 大单吃货市场扫描
echo ========================================
echo.
echo 正在扫描全市场...
echo 这可能需要几分钟时间
echo.
python scan_big_order_absorption.py
echo.
echo 扫描完成！
pause
