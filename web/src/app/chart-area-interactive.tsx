"use client"

import * as React from "react"
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts"

import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/registry/new-york-v4/ui/card"
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/registry/new-york-v4/ui/chart"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/registry/new-york-v4/ui/select"
import { ToggleGroup, ToggleGroupItem } from "@/registry/new-york-v4/ui/toggle-group"
import { num, rate, wan } from "./format"
import type { Overview } from "./use-data"

type Key = "gmv" | "order_cnt" | "active_users" | "pay_user_rate" | "pv_order_rate" | "arppu"
const METRICS: { key: Key; label: string; tick: (v: number) => string; full: (v: number) => string; desc: string }[] = [
  { key: "gmv", label: "GMV（模拟）", tick: (v) => `${wan(v, 0)}万`, full: (v) => `${num(v)} 元`, desc: "每日 GMV，金额基于模拟价格" },
  { key: "order_cnt", label: "订单数", tick: (v) => `${wan(v, 0)}万`, full: (v) => `${num(v)} 单`, desc: "每日订单数" },
  { key: "active_users", label: "日活跃用户", tick: (v) => `${wan(v, 0)}万`, full: (v) => `${num(v)} 人`, desc: "每日活跃用户数" },
  { key: "pv_order_rate", label: "浏览转化率", tick: (v) => rate(v, 1), full: (v) => rate(v, 2), desc: "购买次数 ÷ 浏览次数" },
]

const chartConfig = { value: { label: "数值", color: "var(--chart-2)" } } satisfies ChartConfig

export function ChartAreaInteractive({ d }: { d: Overview }) {
  const [key, setKey] = React.useState<Key>("gmv")
  const m = METRICS.find((x) => x.key === key)!
  const data = d.daily.map((r) => ({ date: r.dt, weekday: r.weekday, value: r[key] }))
  return (
    <Card className="@container/card">
      <CardHeader>
        <CardTitle>每日走势</CardTitle>
        <CardDescription>
          <span className="hidden @[540px]/card:block">{m.desc}</span>
          <span className="@[540px]/card:hidden">{m.desc}</span>
        </CardDescription>
        <CardAction>
          <ToggleGroup
            type="single"
            value={key}
            onValueChange={(v) => v && setKey(v as Key)}
            variant="outline"
            className="hidden *:data-[slot=toggle-group-item]:px-4! @[767px]/card:flex"
          >
            {METRICS.map((x) => (
              <ToggleGroupItem key={x.key} value={x.key}>{x.label}</ToggleGroupItem>
            ))}
          </ToggleGroup>
          <Select value={key} onValueChange={(v) => setKey(v as Key)}>
            <SelectTrigger className="flex w-40 **:data-[slot=select-value]:block **:data-[slot=select-value]:truncate @[767px]/card:hidden" size="sm" aria-label="选择指标">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="rounded-xl">
              {METRICS.map((x) => (
                <SelectItem key={x.key} value={x.key} className="rounded-lg">{x.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardAction>
      </CardHeader>
      <CardContent className="px-2 pt-4 sm:px-6 sm:pt-6">
        <ChartContainer config={chartConfig} className="aspect-auto h-[250px] w-full">
          <AreaChart data={data} margin={{ left: 4, right: 12 }}>
            <defs>
              <linearGradient id="fillValue" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-value)" stopOpacity={0.9} />
                <stop offset="95%" stopColor="var(--color-value)" stopOpacity={0.08} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="date" tickLine={false} axisLine={false} tickMargin={8} tickFormatter={(v) => String(v).slice(5)} />
            <YAxis tickLine={false} axisLine={false} width={56} tickFormatter={m.tick} domain={[0, "auto"]} />
            <ChartTooltip
              cursor={false}
              content={
                <ChartTooltipContent
                  indicator="dot"
                  labelFormatter={(v, p) => `${String(v).slice(5)} ${p?.[0]?.payload?.weekday ?? ""}`}
                  formatter={(v) => <span className="font-mono font-medium tabular-nums">{m.full(Number(v))}</span>}
                />
              }
            />
            <Area dataKey="value" type="monotone" fill="url(#fillValue)" stroke="var(--color-value)" strokeWidth={2} />
          </AreaChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}
