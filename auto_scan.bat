@echo off
cd /d C:\Users\shiji\Desktop\量化\quant_ai
echo ========================================
echo 量化扫描启动 - %date% %time%
echo ========================================

REM 检查是否为交易日
python -c "from trading_calendar import is_trading_day; import sys; sys.exit(0 if is_trading_day() else 1)"
if errorlevel 1 (
    echo 今天不是交易日，跳过扫描
    exit /b 0
)

echo 今天是交易日，开始扫描...

echo [1] 检查持仓...
python check_holdings.py

echo [2] 全市场扫描...
python scan_market.py

echo [3] 检查BBG...
python check_bbg.py

echo ========================================
echo 扫描完成！
pause
