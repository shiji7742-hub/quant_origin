@echo off
chcp 65001 >nul
echo ========================================
echo 尾盘回落分析系统
echo ========================================
echo.
echo 核心逻辑：盘中托价 + 尾盘回落 = 好信号！
echo.
echo 为什么尾盘回落是好事？
echo   1. 洗盘：吓出短线客
echo   2. 隐蔽：不想暴露意图
echo   3. 降成本：第二天继续吸筹
echo.
echo 正在扫描市场...
echo.
python analyze_closing_pullback.py
echo.
echo 分析完成！
pause
