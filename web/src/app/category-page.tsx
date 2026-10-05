import * as React from "react"
import { CartesianGrid, ReferenceLine, Scatter, ScatterChart, XAxis, YAxis, ZAxis } from "recharts"

import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/registry/new-york-v4/ui/card"
import { ChartContainer, ChartTooltip, type ChartConfig } from "@/registry/new-york-v4/ui/chart"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/registry/new-york-v4/ui/select"
import { ToggleGroup, ToggleGroupItem } from "@/registry/new-york-v4/ui/toggle-group"
import { Loading, Note, PageBody, PageIntro, Section, SimpleTable, Stats } from "./bits"
import { MiniArea } from "./charts"
import { num, rate, wan } from "./format"
import { useData } from "./use-data"

type Cat = { category_id: number; pv_cnt: number; buy_cnt: number; gmv: number; pv_order_rate: number; gmv_rank: number; pv_rank: number }
type D = {
  stats: { n_cat: number; n_buy: number; top10_share: number; n_80: number; conv: number; gmv_total: number }
  top10: (Cat & { cart_cnt: number; fav_cnt: number })[]
  by_pv: Cat[]
  top50: { category_id: number; gmv_rank: number }[]
  daily: { category_id: number; dt: string; weekday: string; pv_cnt: number; buy_cnt: number; gmv: number }[]
}

const median = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}
const cfg = { gmv: { label: "品类", color: "var(--chart-2)" } } satisfies ChartConfig

function Quadrant({ rows, xMid, yMid }: { rows: Cat[]; xMid: number; yMid: number }) {
  const data = rows.map((r) => ({ ...r, id: String(r.category_id) }))
  const lo = Math.floor(Math.log10(Math.min(...rows.map((r) => r.pv_cnt))))
  const hi = Math.ceil(Math.log10(Math.max(...rows.map((r) => r.pv_cnt))))
  const ticks = Array.from({ length: hi - lo + 1 }, (_, i) => 10 ** (lo + i))
  return (
    <div className="relative">
      <ChartContainer config={cfg} className="aspect-auto h-[420px] w-full">
        <ScatterChart margin={{ left: 4, right: 16, top: 16, bottom: 8 }}>
          <CartesianGrid />
          <XAxis type="number" dataKey="pv_cnt" scale="log" domain={[10 ** lo, 10 ** hi]} ticks={ticks} tickLine={false} axisLine={false}
            tickFormatter={(v) => (v >= 1e4 ? `${wan(v, 0)}万` : String(v))} name="浏览量" />
          <YAxis type="number" dataKey="pv_order_rate" tickLine={false} axisLine={false} width={48} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} name="转化率" />
          <ZAxis type="number" dataKey="gmv" range={[30, 420]} name="GMV" />
          <ReferenceLine x={xMid} stroke="var(--muted-foreground)" strokeDasharray="4 4" />
          <ReferenceLine y={yMid} stroke="var(--muted-foreground)" strokeDasharray="4 4" />
          <ChartTooltip cursor={false} content={({ payload }) => {
            const p = payload?.[0]?.payload
            if (!p) return null
            return (
              <div className="rounded-lg border bg-background px-2.5 py-1.5 text-xs shadow-xl">
                <div className="font-medium">品类 {p.id}</div>
                <div className="tabular-nums text-muted-foreground">浏览 {num(p.pv_cnt)}　转化率 {rate(p.pv_order_rate, 2)}</div>
                <div className="tabular-nums text-muted-foreground">GMV {num(p.gmv)} 元</div>
              </div>
            )
          }} />
          <Scatter data={data} fill="var(--chart-2)" fillOpacity={0.55} stroke="var(--background)" />
        </ScatterChart>
      </ChartContainer>
      <span className="pointer-events-none absolute top-3 right-6 text-[11px] text-muted-foreground">高流量 · 高转化</span>
      <span className="pointer-events-none absolute top-3 left-14 text-[11px] text-muted-foreground">低流量 · 高转化</span>
      <span className="pointer-events-none absolute right-6 bottom-14 text-[11px] font-medium text-foreground">高流量 · 低转化</span>
      <span className="pointer-events-none absolute bottom-14 left-14 text-[11px] text-muted-foreground">低流量 · 低转化</span>
    </div>
  )
}

export function CategoryPage() {
  const d = useData<D>("category")
  const [n, setN] = React.useState("300")
  const [cat, setCat] = React.useState<string>("")
  if (!d) return <Loading />
  const s = d.stats
  const rows = d.by_pv.slice(0, Number(n))
  const xMid = median(rows.map((r) => r.pv_cnt))
  const yMid = median(rows.map((r) => r.pv_order_rate))
  const opp = rows.filter((r) => r.pv_cnt >= xMid && r.pv_order_rate < yMid).slice(0, 10)
  const extra = opp.reduce((a, r) => a + r.pv_cnt * (yMid - r.pv_order_rate), 0)
  const pick = cat || String(d.top50[0].category_id)
  const daily = d.daily.filter((r) => String(r.category_id) === pick)
  const rank = d.top50.find((r) => String(r.category_id) === pick)?.gmv_rank
  return (
    <PageBody>
      <PageIntro>数据集里品类只有编号（已脱敏），没有名称。这里看品类的集中度，并用四象限找出“流量大但转化差”的机会品类。GMV 基于模拟价格。</PageIntro>
      <Stats
        items={[
          { label: "品类数（个）", value: num(s.n_cat), line: `有成交 ${num(s.n_buy)} 个` },
          { label: "Top 10 品类 GMV 占比", value: rate(s.top10_share), line: "按 GMV 排名" },
          { label: "贡献 80% GMV 的品类（个）", value: num(s.n_80), line: `占全部品类 ${rate(s.n_80 / s.n_cat)}` },
          { label: "整体浏览→购买转化", value: rate(s.conv, 2), line: "所有品类合计" },
        ]}
      />
      <Section>
        <Card className="@container/card">
          <CardHeader>
            <CardTitle>品类四象限</CardTitle>
            <CardDescription>横轴流量（对数刻度），纵轴转化率，点越大 GMV 越高</CardDescription>
            <CardAction>
              <ToggleGroup type="single" value={n} onValueChange={(v) => v && setN(v)} variant="outline" size="sm" className="hidden @[767px]/card:flex">
                {["100", "200", "300", "500"].map((v) => (
                  <ToggleGroupItem key={v} value={v}>浏览量前 {v}</ToggleGroupItem>
                ))}
              </ToggleGroup>
              <Select value={n} onValueChange={setN}>
                <SelectTrigger size="sm" className="w-36 @[767px]/card:hidden"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {["100", "200", "300", "500"].map((v) => (
                    <SelectItem key={v} value={v}>浏览量前 {v}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardAction>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Quadrant rows={rows} xMid={xMid} yMid={yMid} />
            <Note>虚线 = 所选品类的中位数。右下角“高流量 · 低转化”的品类最值得优化：流量已经有了，提升详情页、价格、评价等转化因素，带来的增量最大。</Note>
          </CardContent>
        </Card>
      </Section>
      <Section cols={2}>
        <Card>
          <CardHeader><CardTitle>GMV Top 10 品类</CardTitle></CardHeader>
          <CardContent>
            <SimpleTable
              rows={d.top10}
              cols={[
                { header: "排名", align: "right", cell: (r) => r.gmv_rank },
                { header: "品类编号", cell: (r) => <span className="font-medium">{r.category_id}</span> },
                { header: "GMV", align: "right", cell: (r) => num(r.gmv) },
                { header: "GMV 占比", align: "right", cell: (r) => rate(r.gmv / s.gmv_total) },
                { header: "转化率", align: "right", cell: (r) => rate(r.pv_order_rate) },
                { header: "流量排名", align: "right", cell: (r) => r.pv_rank },
              ]}
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>机会品类：高流量 · 低转化</CardTitle>
            <CardDescription>浏览量前 {n} 中，按浏览量排序</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <SimpleTable
              rows={opp}
              cols={[
                { header: "品类编号", cell: (r) => <span className="font-medium">{r.category_id}</span> },
                { header: "浏览量", align: "right", cell: (r) => num(r.pv_cnt) },
                { header: "转化率", align: "right", cell: (r) => rate(r.pv_order_rate, 2) },
                { header: "订单", align: "right", cell: (r) => num(r.buy_cnt) },
                { header: "GMV", align: "right", cell: (r) => num(r.gmv) },
              ]}
            />
            {opp.length > 0 && <Note>如果这 {opp.length} 个品类的转化率提升到中位数，约可多出 <b>{wan(extra, 1)} 万</b>笔订单（粗略估算）。</Note>}
          </CardContent>
        </Card>
      </Section>
      <Section>
        <Card className="@container/card">
          <CardHeader>
            <CardTitle>单个品类每日走势</CardTitle>
            <CardDescription>GMV 前 50 的品类，可切换</CardDescription>
            <CardAction>
              <Select value={pick} onValueChange={setCat}>
                <SelectTrigger size="sm" className="w-52"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {d.top50.map((r) => (
                    <SelectItem key={r.category_id} value={String(r.category_id)}>品类 {r.category_id}（GMV 第 {r.gmv_rank}）</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardAction>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-6 @3xl/card:grid-cols-2">
            <div>
              <div className="mb-2 text-sm font-medium">浏览量{rank ? `（GMV 第 ${rank}）` : ""}</div>
              <MiniArea id="cat-pv" data={daily.map((r) => ({ name: r.dt.slice(5), value: r.pv_cnt }))} fmt={(v) => (v >= 1e4 ? `${wan(v, 1)}万` : String(v))} />
            </div>
            <div>
              <div className="mb-2 text-sm font-medium">GMV（模拟，元）</div>
              <MiniArea id="cat-gmv" data={daily.map((r) => ({ name: r.dt.slice(5), value: r.gmv }))} fmt={(v) => (v >= 1e4 ? `${wan(v, 1)}万` : String(v))} />
            </div>
          </CardContent>
        </Card>
      </Section>
    </PageBody>
  )
}
