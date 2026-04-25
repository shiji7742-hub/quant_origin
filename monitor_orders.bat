@echo off
chcp 65001 >nul
echo ====================================
echo 盘口大单监测工具
echo ====================================
echo.
echo 1. 快速监测持仓
echo 2. 详细监测（可自定义）
echo 3. 监测单只股票
echo.
set /p choice="请选择 (1/2/3): "

if "%choice%"=="1" (
    python quick_monitor_orders.py
) else if "%choice%"=="2" (
    python monitor_big_orders.py
) else if "%choice%"=="3" (
    set /p stock="请输入股票代码: "
    python quick_monitor_orders.py %stock%
) else (
    echo 无效选择
)

pause
