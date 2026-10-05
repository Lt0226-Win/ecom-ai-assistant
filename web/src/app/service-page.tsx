import * as React from "react"
import { IconHeadset, IconSend } from "@tabler/icons-react"

import { Badge } from "@/registry/new-york-v4/ui/badge"
import { Button } from "@/registry/new-york-v4/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/registry/new-york-v4/ui/card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/registry/new-york-v4/ui/collapsible"
import { Input } from "@/registry/new-york-v4/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/registry/new-york-v4/ui/tabs"
import { Textarea } from "@/registry/new-york-v4/ui/textarea"
import { apiGet, apiPost, ApiError, type BatchResult, type ServiceResult, type Status, type TicketResult } from "./api"
import { Note, PageBody, PageIntro, Section, SimpleTable } from "./bits"
import { HBars } from "./charts"

type Turn = { q: string; ans?: ServiceResult; error?: string }

function ServiceAnswer({ a }: { a: ServiceResult }) {
  // 两种“转人工”：1) 知识库里没有可靠依据（检索得分低于门槛，不调用 AI）；2) 有依据，但 AI 判断涉及投诉 / 账户安全，需要人工跟进
  const noBasis = a.top_score < a.no_answer_score
  return (
    <div className="flex flex-col gap-3">
      {a.error && <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{a.error}</div>}
      {noBasis ? (
        <div className="flex items-start gap-3 rounded-lg border border-dashed p-4">
          <IconHeadset className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
          <div className="text-sm leading-relaxed">
            <div className="font-medium">知识库里没有可靠的依据，已转人工客服</div>
            {a.answer && <div className="mt-1">{a.answer}</div>}
            <div className="mt-1 text-muted-foreground">
              最相关资料的检索得分 {a.top_score.toFixed(2)}，低于“有把握回答”的门槛 {a.no_answer_score.toFixed(2)}，所以不调用 AI，宁可转人工，也不让它编一个听起来合理的答案。
            </div>
          </div>
        </div>
      ) : (
        <>
          {a.answer && <p className="text-sm leading-relaxed whitespace-pre-wrap">{a.answer}</p>}
          {a.need_human && (
            <div className="flex w-fit items-center gap-2 rounded-md border border-up/30 bg-up/10 px-2.5 py-1 text-xs text-up">
              <IconHeadset className="size-4" />AI 判断这个问题需要人工客服跟进（涉及投诉、账户安全或资料无法完全覆盖）
            </div>
          )}
        </>
      )}
      {a.hits.length > 0 && (
        <Collapsible>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="-ml-2 text-muted-foreground">查看检索到的知识库片段（{a.hits.length} 条）· {a.mode}</Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2 flex flex-col gap-2">
            {a.hits.map((h, i) => (
              <div key={i} className="rounded-lg border bg-muted/30 p-3">
                <div className="mb-1 flex items-center justify-between gap-2 text-xs">
                  <span className="font-medium">{h.source}</span>
                  <Badge variant="outline" className="tabular-nums">相关度 {h.score.toFixed(2)}</Badge>
                </div>
                <div className="text-xs leading-relaxed whitespace-pre-wrap text-muted-foreground">{h.text}</div>
              </div>
            ))}
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  )
}

function KnowledgeQA({ status }: { status: Status }) {
  const [turns, setTurns] = React.useState<Turn[]>([])
  const [text, setText] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const ask = async (q: string) => {
    q = q.trim()
    if (!q || busy) return
    setBusy(true)
    setText("")
    const history = turns.filter((t) => t.ans && !t.ans.need_human).slice(-2).map((t) => ({ question: t.q, answer: t.ans!.answer }))
    setTurns((t) => [...t, { q }])
    try {
      const ans = await apiPost<ServiceResult>("service/answer", { question: q, history })
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, ans } : x)))
    } catch (e) {
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, error: (e as Error).message } : x)))
    }
    setBusy(false)
  }
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted-foreground">试试这些问题</span>
        {status.service_examples.map((q) => (
          <Button key={q} variant="outline" size="sm" className="rounded-full" disabled={busy} onClick={() => ask(q)}>{q}</Button>
        ))}
        {turns.length > 0 && <Button variant="ghost" size="sm" onClick={() => setTurns([])}>清空对话</Button>}
      </div>
      {turns.map((t, i) => (
        <Card key={i} className="shadow-xs">
          <CardHeader><CardTitle className="text-base">{t.q}</CardTitle></CardHeader>
          <CardContent>
            {t.ans ? <ServiceAnswer a={t.ans} /> : t.error ? <div className="text-sm text-destructive">{t.error}</div> : <div className="text-sm text-muted-foreground">正在检索知识库…</div>}
          </CardContent>
        </Card>
      ))}
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); ask(text) }}>
        <Input value={text} onChange={(e) => setText(e.target.value)} placeholder="像顾客一样提问，例如：退款退到银行卡要多久？" disabled={busy} />
        <Button type="submit" disabled={busy || !text.trim()}><IconSend />发送</Button>
      </form>
    </div>
  )
}

const URG: Record<string, string> = { 高: "border-up/30 bg-up/10 text-up", 中: "", 低: "" }

function TicketClassify({ status }: { status: Status }) {
  const [text, setText] = React.useState("")
  const [res, setRes] = React.useState<TicketResult | null>(null)
  const [busy, setBusy] = React.useState(false)
  const [err, setErr] = React.useState("")
  const [batch, setBatch] = React.useState<BatchResult | null>(null)
  const [batchErr, setBatchErr] = React.useState("")
  React.useEffect(() => {
    apiGet<BatchResult>("tickets/batch").then(setBatch).catch((e: ApiError) => setBatchErr(e.message))
  }, [])
  const run = async (t: string) => {
    t = t.trim()
    if (!t) return
    setText(t); setBusy(true); setErr("")
    try { setRes(await apiPost<TicketResult>("tickets/classify", { text: t })) } catch (e) { setErr((e as Error).message) }
    setBusy(false)
  }
  const samples = status.service_examples.slice(0, 3).concat(["等了一周还没到，再不到我就要退款了，气死了"])
  return (
    <div className="flex flex-col gap-4">
      <Card className="shadow-xs">
        <CardHeader>
          <CardTitle className="text-base">给一条工单自动分类</CardTitle>
          <CardDescription>粘贴一条顾客留言，系统判断它属于哪一类问题。规则版按关键词判断，大模型版还能给出紧急程度和情绪。</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="例如：收到的衣服有一股怪味，想退货" rows={3} />
          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={() => run(text)} disabled={busy || !text.trim()}>{busy ? "正在分类…" : "分类"}</Button>
            {samples.map((s) => (
              <Button key={s} variant="outline" size="sm" className="rounded-full" disabled={busy} onClick={() => run(s)}>{s}</Button>
            ))}
          </div>
          {err && <div className="text-sm text-destructive">{err}</div>}
          {res && (
            <div className="grid gap-3 rounded-lg border bg-muted/30 p-4 text-sm @xl/main:grid-cols-2">
              <div>
                <div className="mb-1 text-xs text-muted-foreground">规则分类（关键词）</div>
                <Badge variant="secondary" className="text-sm">{res.rule}</Badge>
              </div>
              <div>
                <div className="mb-1 text-xs text-muted-foreground">大模型分类</div>
                {res.llm ? (
                  <div className="flex flex-col gap-2">
                    <div className="flex flex-wrap gap-2">
                      <Badge variant="secondary" className="text-sm">{res.llm.category}</Badge>
                      {res.llm.urgency && <Badge variant="outline" className={URG[res.llm.urgency] ?? ""}>紧急程度：{res.llm.urgency}</Badge>}
                      {res.llm.sentiment && <Badge variant="outline">情绪：{res.llm.sentiment}</Badge>}
                      {res.llm.need_human && <Badge variant="outline" className="border-up/30 bg-up/10 text-up">建议转人工</Badge>}
                    </div>
                    {res.llm.summary && <div className="text-muted-foreground">{res.llm.summary}</div>}
                  </div>
                ) : (
                  <div className="text-muted-foreground">{res.error || (status.llm ? "未返回结果" : "未配置大模型，只显示规则分类")}</div>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {batchErr && <div className="text-sm text-destructive">{batchErr}</div>}
      {batch && (
        <div className="grid grid-cols-1 gap-4 *:min-w-0 @3xl/main:grid-cols-2">
          <Card className="shadow-xs">
            <CardHeader>
              <CardTitle className="text-base">{batch.total} 条标注工单的批量分类</CardTitle>
              <CardDescription>
                规则版准确率 <b>{(batch.accuracy * 100).toFixed(1)}%</b>（{Math.round(batch.accuracy * batch.total)}/{batch.total}）。样本只有 {batch.total} 条，说明规则能覆盖常见说法，但不代表真实业务里的准确率。
              </CardDescription>
            </CardHeader>
            <CardContent>
              <HBars data={batch.dist.map((d) => ({ name: d.category, value: d.count, label: `${d.count} 条` }))} height={Math.max(160, batch.dist.length * 34)} yWidth={64} />
            </CardContent>
          </Card>
          <Card className="shadow-xs">
            <CardHeader>
              <CardTitle className="text-base">分错的工单</CardTitle>
              <CardDescription>错误都出在“一句话里同时提到两件事”的留言：规则只认关键词，抓不到整句话真正的意图。这类留言需要理解整句话，是大模型分类要解决的部分。</CardDescription>
            </CardHeader>
            <CardContent>
              {batch.wrong.length === 0 ? (
                <Note>全部分对。</Note>
              ) : (
                <SimpleTable
                  rows={batch.wrong}
                  cols={[
                    { header: "留言", cell: (r) => r.text, className: "whitespace-normal min-w-48" },
                    { header: "人工标注", cell: (r) => r.label },
                    { header: "规则判断", cell: (r) => <span className="text-up">{r.pred}</span> },
                  ]}
                />
              )}
            </CardContent>
          </Card>
          <Card className="shadow-xs @3xl/main:col-span-2">
            <CardHeader>
              <CardTitle className="text-base">分类体系</CardTitle>
              <CardDescription>8 个类别，每类的覆盖范围如下。</CardDescription>
            </CardHeader>
            <CardContent>
              <SimpleTable rows={batch.categories} cols={[{ header: "类别", cell: (r) => <span className="font-medium">{r.name}</span> }, { header: "覆盖的问题", cell: (r) => r.desc, className: "whitespace-normal" }]} />
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}

export function ServicePage() {
  const [status, setStatus] = React.useState<Status | null>(null)
  const [fatal, setFatal] = React.useState("")
  React.useEffect(() => {
    apiGet<Status>("status").then(setStatus).catch((e: ApiError) => setFatal(e.message))
  }, [])
  return (
    <PageBody>
      <PageIntro>
        基于一份模拟的平台售后知识库（退款、物流、发票、价保等）做检索增强问答：先找出最相关的条款，再让 AI 只依据这些条款回答，并标注来源；找不到可靠依据时转人工，不瞎编。
      </PageIntro>
      {fatal && <Section><Card><CardContent className="text-sm text-destructive">{fatal}</CardContent></Card></Section>}
      {status && (
        <Section>
          <Tabs defaultValue="qa" className="flex flex-col gap-4">
            <TabsList className="w-fit">
              <TabsTrigger value="qa">知识库问答</TabsTrigger>
              <TabsTrigger value="ticket">工单分类</TabsTrigger>
            </TabsList>
            <TabsContent value="qa"><KnowledgeQA status={status} /></TabsContent>
            <TabsContent value="ticket"><TicketClassify status={status} /></TabsContent>
          </Tabs>
        </Section>
      )}
    </PageBody>
  )
}
