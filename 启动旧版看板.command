#!/bin/bash
# 双击运行：启动旧版（Streamlit）看板，浏览器会自动打开 http://localhost:8502
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/streamlit ]; then
  echo "还没有安装，请先运行 安装.command"; read -r -p "按回车键退出…"; exit 1
fi
if curl -s -o /dev/null http://localhost:8502/_stcore/health; then
  echo "看板已经在运行，正在打开浏览器…"; open "http://localhost:8502"; exit 0
fi
echo "电商 AI 运营助手 启动中…（关闭这个窗口 = 关闭看板）"
( for i in $(seq 1 30); do
    sleep 1
    if curl -s -o /dev/null http://localhost:8502/_stcore/health; then open "http://localhost:8502"; break; fi
  done ) &
exec .venv/bin/streamlit run app/app.py --server.headless true --server.port 8502 --browser.gatherUsageStats false
