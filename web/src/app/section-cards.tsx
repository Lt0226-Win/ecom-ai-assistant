import { IconTrendingDown, IconTrendingUp } from "@tabler/icons-react"

import { Badge } from "@/registry/new-york-v4/ui/badge"
import {
  Card,
  CardAction,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/registry/new-york-v4/ui/card"
import { rate, signedPct, wan } from "./format"
import type { Overview } from "./use-data"

/** 涨跌颜色：红涨绿跌（和国内习惯一致）。要改成绿涨红跌，只需在 index.css 里对调 --up / --down */
function Delta({ v }: { v: number }) {
  const up = v >= 0
  return (
    <Badge variant="outline" className={up ? "border-up/30 bg-up/10 text-up" : "border-down/30 bg-down/10 text-down"}>
      {up ? <IconTrendingUp /> : <IconTrendingDown />}
      {signedPct(v)}
    </Badge>
  )
}

export function SectionCards({ d }: { d: Overview }) {
  const t = d.totals
  const cards = [
    { label: "GMV（模拟，万元）", value: <>{wan(t.gmv, 0)}</>,
      delta: d.wow.gmv, line: `比上周同日 ${signedPct(d.wow.gmv)}`, sub: `${d.wow_label} · 金额基于模拟价格` },
    { label: "订单数（万）", value: <>{wan(t.orders, 1)}</>,
      delta: d.wow.order_cnt, line: `比上周同日 ${signedPct(d.wow.order_cnt)}`, sub: `${d.wow_label}` },
    { label: "日均活跃用户（万）", value: <>{wan(t.avg_active, 1)}</>,
      delta: d.wow.active_users, line: `比上周同日 ${signedPct(d.wow.active_users)}`, sub: `${d.wow_label}` },
    { label: "付费用户（万）", value: <>{wan(t.buyers, 1)}</>,
      delta: null, line: `占全部用户 ${rate(t.buyers / t.users)}`, sub: `复购率 ${rate(t.repeat_buyers / t.buyers)}（付费用户中 2 天及以上有购买）` },
  ]
  return (
    <div className="grid grid-cols-1 gap-4 px-4 *:data-[slot=card]:bg-gradient-to-t *:data-[slot=card]:from-primary/5 *:data-[slot=card]:to-card *:data-[slot=card]:shadow-xs lg:px-6 @xl/main:grid-cols-2 @5xl/main:grid-cols-4 dark:*:data-[slot=card]:bg-card">
      {cards.map((c) => (
        <Card key={c.label} className="@container/card">
          <CardHeader>
            <CardDescription>{c.label}</CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">{c.value}</CardTitle>
            {c.delta !== null && <CardAction><Delta v={c.delta} /></CardAction>}
          </CardHeader>
          <CardFooter className="flex-col items-start gap-1.5 text-sm">
            <div className="line-clamp-1 flex gap-2 font-medium">{c.line}</div>
            <div className="text-muted-foreground">{c.sub}</div>
          </CardFooter>
        </Card>
      ))}
    </div>
  )
}
