@echo off
chcp 65001 >nul
echo ========================================
echo 生成每日推荐股票
echo ========================================
echo.
echo 正在扫描市场...
echo.

python generate_daily_recommendations.py

echo.
echo ========================================
echo 完成！
echo ========================================
echo.
pause
