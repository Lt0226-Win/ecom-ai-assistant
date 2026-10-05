# 新版看板（web/）

套用 shadcn/ui 官方 `dashboard-01` 模板（React + Tailwind + shadcn 组件），数据来自项目数仓。

## 本地预览（不需要装 Node）
    cd web/dist && python3 -m http.server 8600      # 然后打开 http://localhost:8600

## 修改和重新构建（需要 Node 20+）
    cd web && npm install --legacy-peer-deps && npm run dev      # 开发预览
    npm run build                                                 # 生成 dist/，静态文件，可直接放到服务器

## 数据
    python tools/export_dashboard_data.py     # 从数仓导出 web/public/data/*.json（每加一页，加一个导出函数）

## 改颜色
- 涨跌颜色（红涨绿跌）、图表颜色：`src/index.css` 里的 `--up` / `--down` / `--chart-1…5`
- 其他颜色是模板自带的 shadcn 主题变量，同一个文件里

## 目录
- `src/registry/new-york-v4/ui/`  模板自带的 shadcn 组件，原样未改
- `src/app/`  我们的页面：侧边栏、卡片、趋势图、表格、经营总览页
