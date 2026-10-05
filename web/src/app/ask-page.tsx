import * as React from "react"
import { IconSend } from "@tabler/icons-react"

import { Button } from "@/registry/new-york-v4/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/registry/new-york-v4/ui/card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/registry/new-york-v4/ui/collapsible"
import { Input } from "@/registry/new-york-v4/ui/input"
import { apiGet, apiPost, ApiError, type AskAnswer, type Status, type Table } from "./api"
import { Note, PageBody, PageIntro, Section, SimpleTable } from "./bits"
import { VBars } from "./charts"
import { MiniArea } from "./charts"

type Turn = { q: string; ans?: AskAnswer; error?: string }

const cell = (v: string | number | null, col: string) =>
  v == null ? "—" : typeof v === "number" ? (/id$/i.test(col) ? String(v) : v.toLocaleString("en-US", { maximumFractionDigits: 4 })) : v

function AutoChart({ t }: { t: Table }) {
  if (t.columns.length !== 2 || t.rows.length < 2 || t.rows.length > 40 || typeof t.rows[0][1] !== "number") return null
  const isDate = /^\d{4}-\d{2}-\d{2}/.test(String(t.rows[0][0]))
  const data = t.rows.map((r) => ({ name: String(r[0]).slice(isDate ? 5 : 0, isDate ? 10 : 10), value: Number(r[1]) }))
  const fmt = (v: number) => (Math.abs(v) >= 1e4 ? `${(v / 1e4).toFixed(1)}万` : String(+v.toFixed(4)))
  return isDate ? <MiniArea id="ask-area" data={data} fmt={fmt} /> : <VBars data={data} height={220} fmt={fmt} />
}

function Answer({ a }: { a: AskAnswer }) {
  return (
    <div className="flex flex-col gap-3">
      {a.error && <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{a.error}</div>}
      {a.summary && <p className="text-sm leading-relaxed">{a.summary}</p>}
      {a.table && a.table.rows.length > 0 && (
        <>
          <AutoChart t={a.table} />
          <div className="max-h-80 overflow-auto rounded-lg">
            <SimpleTable
              rows={a.table.rows}
              cols={a.table.columns.map((c, i) => ({ header: c, align: typeof a.table!.rows[0][i] === "number" ? ("right" as const) : undefined, cell: (r: (string | number | null)[]) => cell(r[i], c) }))}
            />
          </div>
          {a.table.total_rows > a.table.rows.length && <Note>共 {a.table.total_rows} 行，只显示前 {a.table.rows.length} 行。</Note>}
        </>
      )}
      {a.sql && (
        <Collapsible>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="-ml-2 text-muted-foreground">查看 SQL · {a.seconds.toFixed(1)} 秒 · 尝试 {a.attempts} 次</Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2 flex flex-col gap-2">
            {a.explanation && <Note>思路：{a.explanation}</Note>}
            <pre className="overflow-auto rounded-lg border bg-muted/50 p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap">{a.sql}</pre>
            {a.trace.length > 1 && (
              <>
                <Note>第一次生成的 SQL 执行报错，AI 根据报错信息自动修正：</Note>
                {a.trace.slice(0, -1).map((t, i) => (
                  <pre key={i} className="overflow-auto rounded-lg border bg-muted/30 p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap opacity-70">{t.sql}{"\n\n-- 报错："}{t.error.slice(0, 300)}</pre>
                ))}
              </>
            )}
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  )
}

export function AskPage() {
  const [status, setStatus] = React.useState<Status | null>(null)
  const [fatal, setFatal] = React.useState("")
  const [turns, setTurns] = React.useState<Turn[]>([])
  const [text, setText] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  React.useEffect(() => {
    apiGet<Status>("status").then(setStatus).catch((e: ApiError) => setFatal(e.message))
  }, [])

  const ask = async (q: string) => {
    q = q.trim()
    if (!q || busy) return
    setBusy(true)
    setText("")
    const history = turns.filter((t) => t.ans?.sql).slice(-2).map((t) => ({ q: t.q, sql: t.ans!.sql, explanation: t.ans!.explanation }))
    setTurns((t) => [...t, { q }])
    try {
      const ans = await apiPost<AskAnswer>("ask", { question: q, history })
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, ans } : x)))
    } catch (e) {
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, error: (e as Error).message } : x)))
    }
    setBusy(false)
  }

  return (
    <PageBody>
      <PageIntro>不会写 SQL 也能查数：直接用中文提问，AI 根据数据表说明写出 SQL、在只读数据库里执行，再用几句话总结结果。每一步的 SQL 都可以展开检查。</PageIntro>
      {fatal && <Section><Card><CardContent className="text-sm text-destructive">{fatal}</CardContent></Card></Section>}
      {status && (
        <Section>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">离线评测</CardTitle>
              <CardDescription>
                {status.eval_dev && <>开发集 {status.eval_dev.total} 道标准题，执行准确率 <b>{status.eval_dev.accuracy}</b>（{status.eval_dev.correct}/{status.eval_dev.total}）。</>}
                {status.eval_holdout && <> 另有 {status.eval_holdout.total} 道调优时没见过的独立题，答对 {status.eval_holdout.correct} 道（样本小，仅作泛化的初步验证）。</>}
                {status.llm ? ` 当前模型：${status.model}。` : " 当前没有配置大模型，是演示模式：只能回答下面的示例问题，用预先写好的标准 SQL 展示页面效果。"}
                {status.demo && status.daily_limit > 0 && ` 在线体验每天限 ${status.daily_limit} 次 AI 调用。`}
              </CardDescription>
            </CardHeader>
          </Card>
        </Section>
      )}
      {status && (
        <div className="flex flex-wrap items-center gap-2 px-4 lg:px-6">
          <span className="text-sm text-muted-foreground">试试这些问题</span>
          {status.ask_examples.map((q) => (
            <Button key={q} variant="outline" size="sm" className="rounded-full" disabled={busy} onClick={() => ask(q)}>{q}</Button>
          ))}
          {turns.length > 0 && <Button variant="ghost" size="sm" onClick={() => setTurns([])}>清空对话</Button>}
        </div>
      )}
      <Section>
        {turns.map((t, i) => (
          <Card key={i}>
            <CardHeader>
              <CardTitle className="text-base">{t.q}</CardTitle>
            </CardHeader>
            <CardContent>
              {t.ans ? <Answer a={t.ans} /> : t.error ? <div className="text-sm text-destructive">{t.error}</div> : <div className="text-sm text-muted-foreground">AI 正在写 SQL 并查询…</div>}
            </CardContent>
          </Card>
        ))}
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); ask(text) }}>
          <Input value={text} onChange={(e) => setText(e.target.value)} placeholder="用中文提问，例如：12月1日的付费用户比11月30日多多少？" disabled={busy || !!fatal} />
          <Button type="submit" disabled={busy || !text.trim() || !!fatal}><IconSend />提问</Button>
        </form>
      </Section>
    </PageBody>
  )
}
