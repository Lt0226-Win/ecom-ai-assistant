#!/bin/bash
# 双击运行：安装依赖 + 构建数据仓库（第一次使用运行一次即可）
cd "$(dirname "$0")" || exit 1
echo "== 1/3 准备 Python 虚拟环境 =="
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
echo "== 2/3 安装依赖 =="
.venv/bin/pip install -q -r requirements.txt || { echo "安装失败"; read -r -p "按回车键退出…"; exit 1; }
[ -f .env ] || cp .env.example .env
echo "== 3/3 构建数据仓库（约 1 分钟）=="
if [ -f data/warehouse/ecom.duckdb ]; then
  echo "数据库已存在，跳过（要重建请运行：.venv/bin/python pipeline/build_warehouse.py）"
else
  .venv/bin/python pipeline/build_warehouse.py
fi
echo ""
echo "完成！记得在 .env 里填写 DEEPSEEK_API_KEY。然后双击“启动看板.command”。"
read -r -p "按回车键退出…"
