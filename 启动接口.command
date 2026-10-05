#!/bin/bash
# 双击运行：启动 HTTP 接口（给 n8n / Dify 调用），文档地址 http://localhost:8000/docs
cd "$(dirname "$0")" || exit 1
echo "接口启动中…（关闭这个窗口 = 关闭接口）"
( sleep 3; open "http://localhost:8000/docs" ) &
# 默认只允许本机访问。需要让局域网里其他设备调用时，先在 .env 设置 API_TOKEN，再把下面的 127.0.0.1 改成 0.0.0.0
exec .venv/bin/uvicorn api.server:app --host 127.0.0.1 --port 8000
