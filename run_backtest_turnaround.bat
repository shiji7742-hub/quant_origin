@echo off
chcp 65001 >nul
echo ========================================
echo 年报扭亏策略回测工具
echo ========================================
echo.
echo 1. 查找扭亏股票
echo 2. 快速回测
echo 3. 完整回测
echo.
set /p choice="请选择 (1/2/3): "

if "%choice%"=="1" (
    echo.
    echo 启动查找工具...
    python find_turnaround_stocks.py
) else if "%choice%"=="2" (
    echo.
    echo 启动快速回测...
    python quick_backtest_turnaround.py
) else if "%choice%"=="3" (
    echo.
    echo 启动完整回测...
    python backtest_annual_turnaround.py
) else (
    echo 无效选择
)

echo.
pause
