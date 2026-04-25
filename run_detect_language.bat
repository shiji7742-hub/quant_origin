@echo off
chcp 65001 >nul
echo ========================================
echo 主力对敲语言识别系统
echo ========================================
echo.
echo 识别主力通过对敲手法控盘的"语言"
echo 大单托价 = 主力说"这个价位我要"
echo.
echo 正在扫描市场...
echo.
python detect_market_maker_language.py
echo.
echo 识别完成！
pause
