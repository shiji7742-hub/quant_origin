@echo off
chcp 65001 >nul
echo ========================================
echo AI自主交易系统
echo ========================================
echo.
echo 请选择操作：
echo 1. 运行今日交易（交易+复盘）
echo 2. 仅查看账户状态
echo 3. 仅运行复盘分析
echo 4. 启动定时自动交易
echo 5. 退出
echo.
set /p choice=请输入选项 (1-5): 

if "%choice%"=="1" (
    echo.
    echo 正在运行今日交易...
    python auto_trading_system.py
    pause
) else if "%choice%"=="2" (
    echo.
    echo 正在查看账户...
    python view_portfolio.py
    pause
) else if "%choice%"=="3" (
    echo.
    echo 正在复盘分析...
    python ai_review.py
    pause
) else if "%choice%"=="4" (
    echo.
    echo 启动定时器...
    python schedule_trading.py
) else (
    exit
)
