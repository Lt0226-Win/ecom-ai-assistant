import * as React from "react"

import { Card, CardAction, CardDescription, CardFooter, CardHeader, CardTitle } from "@/registry/new-york-v4/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/registry/new-york-v4/ui/table"

/** 页面顶部的一排数字卡片（模板 section-cards 的通用版） */
export type Stat = { label: string; value: React.ReactNode; line: string; sub?: string; badge?: React.ReactNode }
export function Stats({ items }: { items: Stat[] }) {
  return (
    <div className="grid grid-cols-1 gap-4 px-4 *:data-[slot=card]:bg-gradient-to-t *:data-[slot=card]:from-primary/5 *:data-[slot=card]:to-card *:data-[slot=card]:shadow-xs lg:px-6 @xl/main:grid-cols-2 @5xl/main:grid-cols-4 dark:*:data-[slot=card]:bg-card">
      {items.map((c) => (
        <Card key={c.label} className="@container/card">
          <CardHeader>
            <CardDescription>{c.label}</CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">{c.value}</CardTitle>
            {c.badge && <CardAction>{c.badge}</CardAction>}
          </CardHeader>
          <CardFooter className="flex-col items-start gap-1.5 text-sm">
            <div className="line-clamp-1 flex gap-2 font-medium">{c.line}</div>
            {c.sub && <div className="text-muted-foreground">{c.sub}</div>}
          </CardFooter>
        </Card>
      ))}
    </div>
  )
}

export function PageBody({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">{children}</div>
}

export function Section({ children, cols = 1 }: { children: React.ReactNode; cols?: 1 | 2 }) {
  return (
    <div className={`grid grid-cols-1 gap-4 px-4 *:data-[slot=card]:shadow-xs lg:px-6 ${cols === 2 ? "@3xl/main:grid-cols-2" : ""}`}>
      {children}
    </div>
  )
}

export function PageIntro({ children }: { children: React.ReactNode }) {
  return <p className="px-4 text-sm leading-relaxed text-muted-foreground lg:px-6">{children}</p>
}

export function Loading() {
  return <div className="p-6 text-sm text-muted-foreground">正在加载数据…</div>
}

export function Note({ children }: { children: React.ReactNode }) {
  return <p className="text-xs leading-relaxed text-muted-foreground">{children}</p>
}

export type Col<T> = { header: string; cell: (r: T, i: number) => React.ReactNode; align?: "right"; className?: string }
/** 简单数据表：外观用模板的 Table 组件 */
export function SimpleTable<T>({ cols, rows }: { cols: Col<T>[]; rows: T[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border">
      <Table>
        <TableHeader className="bg-muted">
          <TableRow>
            {cols.map((c) => (
              <TableHead key={c.header} className={`whitespace-nowrap ${c.align === "right" ? "text-right" : ""}`}>{c.header}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r, i) => (
            <TableRow key={i}>
              {cols.map((c) => (
                <TableCell key={c.header} className={`${c.align === "right" ? "text-right tabular-nums" : ""} ${c.className ?? ""}`}>
                  {c.cell(r, i)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

/** 表格里的占比条 */
export function ShareBar({ v }: { v: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-28 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, v * 100)}%` }} />
      </div>
      <span className="tabular-nums">{(v * 100).toFixed(1)}%</span>
    </div>
  )
}

/** 很小的 Markdown 渲染：标题、列表、加粗、引用（周报够用） */
export function Prose({ md }: { md: string }) {
  const inline = (t: string) =>
    t.split(/(\*\*[^*]+\*\*)/g).map((p, i) => (p.startsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong> : <React.Fragment key={i}>{p}</React.Fragment>))
  const out: React.ReactNode[] = []
  let list: string[] = []
  let ordered = false
  const flush = () => {
    if (!list.length) return
    const items = list.map((l, i) => <li key={i}>{inline(l)}</li>)
    out.push(ordered ? <ol key={out.length} className="ml-5 list-decimal space-y-1.5">{items}</ol> : <ul key={out.length} className="ml-5 list-disc space-y-1.5">{items}</ul>)
    list = []
  }
  for (const raw of md.split("\n")) {
    const line = raw.trimEnd()
    const ul = /^[-*]\s+(.*)/.exec(line)
    const ol = /^\d+\.\s+(.*)/.exec(line)
    if (ul || ol) {
      const isOrdered = !!ol
      if (list.length && isOrdered !== ordered) flush()
      ordered = isOrdered
      list.push((ul ?? ol)![1])
      continue
    }
    flush()
    if (!line.trim()) continue
    const h = /^(#{1,6})\s+(.*)/.exec(line)
    if (h) out.push(h[1].length === 1 ? <h2 key={out.length} className="text-lg font-semibold">{h[2]}</h2> : <h3 key={out.length} className="pt-2 text-base font-semibold">{h[2]}</h3>)
    else if (line.startsWith(">")) out.push(<p key={out.length} className="text-sm text-muted-foreground">{inline(line.replace(/^>\s?/, ""))}</p>)
    else out.push(<p key={out.length} className="text-sm leading-relaxed">{inline(line)}</p>)
  }
  flush()
  return <div className="flex flex-col gap-2 text-sm leading-relaxed">{out}</div>
}
