"use client"

import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, LabelList, XAxis, YAxis } from "recharts"

import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/registry/new-york-v4/ui/chart"

const one = { value: { label: "数值", color: "var(--chart-2)" } } satisfies ChartConfig

/** 横向条形图：漏斗、人群等。label 是条末尾显示的文字 */
export function HBars({ data, height = 160, color = "var(--chart-2)", yWidth = 72 }: { data: { name: string; value: number; label: string }[]; height?: number; color?: string; yWidth?: number }) {
  return (
    <ChartContainer config={{ value: { label: "数值", color } }} className="aspect-auto w-full" style={{ height }}>
      <BarChart data={data} layout="vertical" margin={{ left: 0, right: 140 }}>
        <XAxis type="number" hide domain={[0, "dataMax"]} />
        <YAxis type="category" dataKey="name" tickLine={false} axisLine={false} width={yWidth} />
        <ChartTooltip cursor={false} content={<ChartTooltipContent hideLabel formatter={(_v, _n, item) => <span className="font-medium">{item.payload.label}</span>} />} />
        <Bar dataKey="value" fill="var(--color-value)" radius={4}>
          <LabelList dataKey="label" position="right" className="fill-foreground text-xs" />
        </Bar>
      </BarChart>
    </ChartContainer>
  )
}

/** 竖向柱状图：分时段、购买天数分布。highlight 的柱子用深色 */
export function VBars({ data, height = 260, highlight, fmt = (v: number) => String(v), xSuffix = "" }: { data: { name: string | number; value: number }[]; height?: number; highlight?: (name: string | number) => boolean; fmt?: (v: number) => string; xSuffix?: string }) {
  return (
    <ChartContainer config={one} className="aspect-auto w-full" style={{ height }}>
      <BarChart data={data} margin={{ left: 4, right: 8 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="name" tickLine={false} axisLine={false} tickMargin={8} tickFormatter={(v) => `${v}${xSuffix}`} interval="preserveStartEnd" />
        <YAxis tickLine={false} axisLine={false} width={52} tickFormatter={fmt} />
        <ChartTooltip cursor={false} content={<ChartTooltipContent hideLabel formatter={(v, _n, item) => <span className="font-medium tabular-nums">{item.payload.name}{xSuffix}：{fmt(Number(v))}</span>} />} />
        <Bar dataKey="value" radius={[4, 4, 0, 0]}>
          {data.map((d, i) => (
            <Cell key={i} fill={highlight?.(d.name) ? "var(--chart-4)" : "var(--chart-1)"} />
          ))}
        </Bar>
      </BarChart>
    </ChartContainer>
  )
}

/** 两组并排的横向条形图：人数占比 vs GMV 占比 */
export function GroupedHBars({ data, a, b, height = 400 }: { data: { name: string; a: number; b: number }[]; a: string; b: string; height?: number }) {
  const cfg = { a: { label: a, color: "var(--chart-1)" }, b: { label: b, color: "var(--chart-3)" } } satisfies ChartConfig
  return (
    <ChartContainer config={cfg} className="aspect-auto w-full" style={{ height }}>
      <BarChart data={data} layout="vertical" margin={{ left: 0, right: 40 }}>
        <CartesianGrid horizontal={false} />
        <XAxis type="number" tickLine={false} axisLine={false} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
        <YAxis type="category" dataKey="name" tickLine={false} axisLine={false} width={88} />
        <ChartTooltip cursor={false} content={<ChartTooltipContent formatter={(v, n) => <span className="font-medium tabular-nums">{n === "a" ? a : b}：{(Number(v) * 100).toFixed(1)}%</span>} />} />
        <ChartLegend content={<ChartLegendContent />} />
        <Bar dataKey="a" fill="var(--color-a)" radius={3} />
        <Bar dataKey="b" fill="var(--color-b)" radius={3} />
      </BarChart>
    </ChartContainer>
  )
}

/** 小面积图：单个品类每日走势 */
export function MiniArea({ data, fmt, id }: { data: { name: string; value: number }[]; fmt: (v: number) => string; id: string }) {
  return (
    <ChartContainer config={one} className="aspect-auto w-full" style={{ height: 200 }}>
      <AreaChart data={data} margin={{ left: 4, right: 12 }}>
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="var(--color-value)" stopOpacity={0.8} />
            <stop offset="95%" stopColor="var(--color-value)" stopOpacity={0.08} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="name" tickLine={false} axisLine={false} tickMargin={8} />
        <YAxis tickLine={false} axisLine={false} width={56} tickFormatter={fmt} domain={[0, "auto"]} />
        <ChartTooltip cursor={false} content={<ChartTooltipContent indicator="dot" formatter={(v) => <span className="font-medium tabular-nums">{fmt(Number(v))}</span>} />} />
        <Area dataKey="value" type="monotone" fill={`url(#${id})`} stroke="var(--color-value)" strokeWidth={2} />
      </AreaChart>
    </ChartContainer>
  )
}
