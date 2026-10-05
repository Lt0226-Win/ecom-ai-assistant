#!/bin/bash
# 双击运行：启动网页看板，浏览器会自动打开 http://localhost:8600
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/uvicorn ]; then
  echo "还没有安装，请先运行 安装.command"; read -r -p "按回车键退出…"; exit 1
fi
if curl -sf -o /dev/null http://localhost:8600/api/status; then
  echo "看板已经在运行，正在打开浏览器…"; open "http://localhost:8600"; exit 0
fi
echo "电商 AI 运营助手 启动中…（关闭这个窗口 = 关闭看板）"
( for i in $(seq 1 30); do
    sleep 1
    if curl -sf -o /dev/null http://localhost:8600/api/status; then open "http://localhost:8600"; break; fi
  done ) &
exec .venv/bin/uvicorn api.web:app --host 127.0.0.1 --port 8600
