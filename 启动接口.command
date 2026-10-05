#!/bin/bash
# 双击运行：启动 HTTP 接口（给 n8n / Dify 调用），文档地址 http://localhost:8000/docs
cd "$(dirname "$0")" || exit 1
echo "接口启动中…（关闭这个窗口 = 关闭接口）"
( sleep 3; open "http://localhost:8000/docs" ) &
exec .venv/bin/uvicorn api.server:app --host 0.0.0.0 --port 8000
