@echo off
chcp 65001 >nul
echo ========================================
echo 年报扭亏策略扫描
echo ========================================
echo.

python scan_annual_report_turnaround.py

echo.
echo ========================================
echo 扫描完成！
echo ========================================
pause
