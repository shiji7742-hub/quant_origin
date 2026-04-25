@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0.."

echo ========================================
echo 量化 Web 应用
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo 未找到 Python，请先安装 Python 3 并确保 ^`python^` 可用。
    pause
    exit /b 1
)

powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5000/ -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 (
    echo 检测到服务已在运行: http://127.0.0.1:5000/
    echo.
    start "" http://127.0.0.1:5000/
    exit /b 0
)

echo 正在启动服务...
echo 启动后访问: http://127.0.0.1:5000/
echo 按 Ctrl+C 可停止服务。
echo.

python -c "from app import app; app.run(host='127.0.0.1', port=5000, debug=False)"

echo.
echo 服务已停止。
pause
