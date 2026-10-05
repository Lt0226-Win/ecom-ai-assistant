# 网页看板（web/）

套用 shadcn/ui 官方 `dashboard-01` 模板（React + Tailwind + shadcn 组件），共 7 页：经营总览、用户转化、用户分层、品类分析、AI 问数、自动周报、智能客服。数据来自项目数仓。

## 怎么运行（不需要装 Node）
在项目根目录双击 `启动看板.command`，或命令行：

    uvicorn api.web:app --port 8600       # 然后打开 http://localhost:8600

网页（`web/dist`）和接口（`/api`）由同一个服务提供。前 4 页读 `data/*.json`；AI 问数、自动周报、智能客服 3 页调用 `/api`，没配置 `DEEPSEEK_API_KEY` 时是演示模式。
不要用 `python3 -m http.server` 打开：它只有静态文件，AI 三页会连不上接口。

## 修改页面和重新构建（需要 Node 20+）
    cd web && npm install --legacy-peer-deps && npm run dev      # 开发预览
    npm run build                                                 # 生成 dist/（已提交到仓库，服务器不用装 Node）

## 更新数据
    python tools/export_dashboard_data.py     # 从数仓导出 web/public/data/*.json
    cd web && npm run build                   # 再构建一次，dist/data 才会更新

## 改颜色
- 涨跌颜色（红涨绿跌）、图表颜色：`src/index.css` 里的 `--up` / `--down` / `--chart-1…5`
- 其他颜色是模板自带的 shadcn 主题变量，同一个文件里

## 目录
- `src/registry/new-york-v4/ui/`  从模板拿来、页面实际用到的 shadcn 组件（没用到的已删，需要时再从 shadcn 添加）
- `src/app/`  我们的页面：侧边栏、7 个页面（`*-page.tsx`）、图表（`charts.tsx`）、接口调用（`api.ts`）
