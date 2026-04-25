# 量化选股与扫描工具集

这是一个以 Python 为主的量化分析项目，包含全市场扫描、板块扫描、策略回测、Web 工作台、桌面盯盘提醒和模拟交易相关脚本。

## 主要能力

- Flask Web 应用：登录、工作台、全市场扫描、板块扫描、策略页
- 多种选股/回测脚本：均线、洗盘、箱体、板块异动等
- 桌面提醒工具：`stock_alert_gui.py`
- 模拟交易与复盘：`auto_trading_system.py`、`ai_trader.py`、`ai_review.py`

## 目录说明

- `app.py`：当前主要 Web 应用入口
- `templates/`：Web 页面模板
- `scripts/`：辅助启动脚本
- `deploy/`：部署示例文件
- `virtual_trading_data/`：本地模拟交易数据目录，默认不提交
- `cache/`、`build/`、`dist/`：运行/构建产物，默认不提交

## 环境要求

- Python 3.11+
- Windows 本地开发优先

安装依赖：

```bash
pip install -r requirements.txt
```

## 本地配置

复制 `.env.example` 为 `.env`，再按本地环境填写：

```bash
copy .env.example .env
```

关键配置项：

- `FLASK_SECRET_KEY`
- `QUANT_APP_USERNAME`
- `QUANT_APP_PASSWORD` 或 `QUANT_APP_PASSWORD_HASH`
- `SESSION_COOKIE_SECURE`
- `MARKET_SCAN_MAX_CANDIDATES`
- `MARKET_SCAN_MAX_WORKERS`
- `STOCK_HISTORY_PROVIDER`
- `TUSHARE_TOKEN`（仅在相关脚本需要时配置）

## 启动方式

启动 Web 应用：

```bash
python app.py
```

打开浏览器访问：

```text
http://localhost:5000
```

常见入口：

- `/workspace`
- `/market`
- `/sector`
- `/dashboard`

## 相关文档

- `FRONTEND_GUIDE.md`
- `README_AI_TRADING.md`
- `README_SECTOR_STOCK.md`
- `README_MACD_GOLDEN_CROSS.md`
- `README_ANNUAL_TURNAROUND.md`

## 安全说明

- 不要提交 `.env`、本地缓存、运行日志、导出的回测结果和个人持仓文件
- 第三方平台 token 只放环境变量或本地未提交文件
- 如果某个 token 曾经提交到 Git 历史，除了从代码中删除，还应去对应平台立即作废或重置

## 仓库状态

当前仓库主要保留源码、模板、部署脚本和说明文档；运行产物和本地数据已通过 `.gitignore` 排除。
