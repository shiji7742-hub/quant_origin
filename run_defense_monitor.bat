@echo off
chcp 65001 >nul
echo ====================================
echo 横盘托单监测工具
echo ====================================
echo.
echo 1. 快速检查持仓
echo 2. 持续监测持仓
echo 3. 全市场扫描
echo 4. 检查单只股票
echo.
set /p choice="请选择 (1/2/3/4): "

if "%choice%"=="1" (
    python quick_check_defense.py
) else if "%choice%"=="2" (
    python monitor_support_defense.py
) else if "%choice%"=="3" (
    python scan_support_defense.py
) else if "%choice%"=="4" (
    set /p stock="请输入股票代码: "
    python quick_check_defense.py %stock%
) else (
    echo 无效选择
)

pause
