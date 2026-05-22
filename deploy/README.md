# 服务器部署与更新

## 适用环境

- Ubuntu / Debian
- systemd
- Python 3.11+

## 首次部署

```bash
cd /opt/quant-ai
bash deploy.sh
```

首次部署后请检查：

```bash
systemctl status quant-ai --no-pager
curl http://127.0.0.1:5000/healthz
```

## 日常更新

```bash
cd /opt/quant-ai
bash scripts/server_update.sh
```

如服务器目录或服务名不同，可显式传入：

```bash
APP_DIR=/opt/quant-ai APP_NAME=quant-ai REMOTE_NAME=quant-origin BRANCH_NAME=main VENV_DIR=/opt/quant-ai/.venv HEALTHCHECK_URL=http://127.0.0.1:5000/healthz bash scripts/server_update.sh
```

## 回滚

先找目标 commit：

```bash
git log --oneline -5
```

执行回滚：

```bash
cd /opt/quant-ai
bash scripts/server_rollback.sh <commit>
```

## 常见排查命令

```bash
systemctl status quant-ai --no-pager
journalctl -u quant-ai -n 100 --no-pager
curl http://127.0.0.1:5000/healthz
git rev-parse HEAD
```

## 配置说明

- `.env` 不进入 Git
- 服务器代码目录不要手工改生产代码
- 默认更新来源为 `quant-origin/main`

## 腾讯云单 IP 部署

如果服务器只有公网 IP（例如 `134.175.124.122`），建议这样接入：

1. 先把代码同步到服务器仓库：

```bash
sudo -i
cd /root/量化/quant_ai
git fetch quant-origin
git reset --hard quant-origin/main
```

2. 让后端继续只监听 `127.0.0.1:5000`，然后用 Nginx 反代公网入口。

示例配置见 `deploy/nginx/quant-ai.conf.example`。

3. 后端健康检查：

```bash
curl http://127.0.0.1:5000/healthz
```

4. 如果后面拿到了 IP 证书，再把 `SESSION_COOKIE_SECURE=true` 打开。
