#!/bin/bash
# 在服务器上运行：部署“电商 AI 运营助手”在线演示版（地址：你的网站/demo/）
# 前提：已经把精简数据库 ecom_demo.duckdb 上传到服务器的家目录（~/ecom_demo.duckdb）
# 用法：bash setup_demo.sh          可以重复运行（代码更新后再运行一次即可）
set -e

APP_DIR="$HOME/ecom-ai-assistant"
REPO="https://github.com/Lt0226-Win/ecom-ai-assistant.git"

echo "== 1/5 安装 Python 和 Git =="
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip git

echo "== 2/5 下载 / 更新代码 =="
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone "$REPO" "$APP_DIR"
fi
cd "$APP_DIR"

echo "== 3/5 安装依赖（第一次约 2–3 分钟）=="
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

echo "== 4/5 准备数据库和配置 =="
mkdir -p data/warehouse
if [ -f "$HOME/ecom_demo.duckdb" ]; then
  mv "$HOME/ecom_demo.duckdb" data/warehouse/ecom_demo.duckdb
fi
if [ ! -f data/warehouse/ecom_demo.duckdb ]; then
  echo "找不到数据库：请先在 Mac 上把 ecom_demo.duckdb 上传到服务器（见说明）"; exit 1
fi
if [ ! -f .env ]; then
  echo ""
  read -r -s -p "请粘贴 DeepSeek API Key（输入时不会显示，粘贴后按回车）：" KEY; echo ""
  cat > .env <<ENV
DEEPSEEK_API_KEY=$KEY
DEEPSEEK_MODEL=deepseek-chat
DB_PATH=$APP_DIR/data/warehouse/ecom_demo.duckdb
DUCKDB_MEMORY_LIMIT=1GB
DUCKDB_THREADS=2
DEMO_MODE=1
DEMO_DAILY_LIMIT=100
ENV
  chmod 600 .env
fi

echo "== 5/5 设置为后台服务（开机自动启动、崩溃自动重启）=="
sudo tee /etc/systemd/system/ecom-demo.service >/dev/null <<UNIT
[Unit]
Description=ecom-ai-assistant demo (Streamlit)
After=network.target

[Service]
User=$USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/streamlit run app/app.py --server.port 8502 --server.address 127.0.0.1 --server.baseUrlPath demo --server.headless true --browser.gatherUsageStats false
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable ecom-demo
sudo systemctl restart ecom-demo

sleep 5
if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8502/demo/_stcore/health | grep -q 200; then
  echo ""
  echo "完成！在线演示地址：http://你的网站地址/demo/"
else
  echo "服务没有正常启动，查看日志：sudo journalctl -u ecom-demo -n 50"
fi
