@echo off
chcp 65001 >nul
echo ========================================
echo 订单流分析工具
echo ========================================
echo.
echo 区分逐笔大单和3秒合单大单
echo.
echo 信号强度：
echo   逐笔大单托价 = 最强信号（主力直接扫货）
echo   3秒合单大单 = 次强信号（主力分批吃）
echo.
echo 正在分析...
echo.
python analyze_order_flow.py
echo.
echo 分析完成！
pause
