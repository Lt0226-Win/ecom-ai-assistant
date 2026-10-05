import * as React from "react"
import { IconDownload, IconSparkles } from "@tabler/icons-react"

import { Badge } from "@/registry/new-york-v4/ui/badge"
import { Button } from "@/registry/new-york-v4/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/registry/new-york-v4/ui/card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/registry/new-york-v4/ui/collapsible"
import { Label } from "@/registry/new-york-v4/ui/label"
import { Switch } from "@/registry/new-york-v4/ui/switch"
import { apiGet, apiPost, type ReportResult, type Status } from "./api"
import { Note, PageBody, PageIntro, Prose, Section } from "./bits"

export function ReportPage() {
  const [status, setStatus] = React.useState<Status | null>(null)
  const [useLlm, setUseLlm] = React.useState(true)
  const [rep, setRep] = React.useState<ReportResult | null>(null)
  const [busy, setBusy] = React.useState(false)
  const [err, setErr] = React.useState("")
  React.useEffect(() => {
    apiGet<Status>("status").then((s) => { setStatus(s); setUseLlm(s.llm) }).catch((e) => setErr(e.message))
  }, [])
  const generate = async () => {
    setBusy(true); setErr("")
    try { setRep(await apiPost<ReportResult>("report", { use_llm: useLlm })) } catch (e) { setErr((e as Error).message) }
    setBusy(false)
  }
  const download = () => {
    if (!rep) return
    const a = document.createElement("a")
    a.href = URL.createObjectURL(new Blob([rep.markdown], { type: "text/markdown" }))
    a.download = `${rep.title}.md`
    a.click()
  }
  return (
    <PageBody>
      <PageIntro>数字全部由 SQL 计算，大模型只负责把数字写成分析文字；生成后自动核对文中数字，对不上的会标出来。每周一早上由 n8n 定时触发，自动推送到飞书群。</PageIntro>
      <Section>
        <Card>
          <CardContent className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <Switch id="llm" checked={useLlm} onCheckedChange={setUseLlm} disabled={!status?.llm} />
              <Label htmlFor="llm">用大模型写分析</Label>
              {status && !status.llm && <Badge variant="outline">未配置大模型：使用模板</Badge>}
            </div>
            <Button onClick={generate} disabled={busy || !status}><IconSparkles />{busy ? "正在生成…" : "生成本周周报"}</Button>
            {err && <span className="text-sm text-destructive">{err}</span>}
          </CardContent>
        </Card>
      </Section>
      {!rep && (
        <Section>
          <Card>
            <CardHeader><CardTitle className="text-base">周报包含什么</CardTitle></CardHeader>
            <CardContent>
              <ul className="ml-5 list-disc space-y-1.5 text-sm leading-relaxed">
                <li>核心结论：本周 GMV、订单、付费用户，以及和上周同期的对比</li>
                <li>指标表现：日活、付费率、最好 / 最差的一天、浏览高峰时段</li>
                <li>值得关注：增长和下滑最快的品类、漏斗、核心用户群</li>
                <li>下周建议：具体可执行的运营动作</li>
              </ul>
            </CardContent>
          </Card>
        </Section>
      )}
      {rep && (
        <div className="grid grid-cols-1 gap-4 px-4 *:data-[slot=card]:shadow-xs lg:px-6 @4xl/main:grid-cols-[1fr_20rem]">
          <Card>
            <CardHeader>
              <CardTitle>{rep.title}</CardTitle>
              <CardDescription>{rep.source === "llm" ? "大模型生成" : "模板生成"}</CardDescription>
            </CardHeader>
            <CardContent><Prose md={rep.markdown.split("\n").slice(1).join("\n")} /></CardContent>
          </Card>
          <div className="flex flex-col gap-4">
            <Card>
              <CardHeader><CardTitle className="text-base">数字核对</CardTitle></CardHeader>
              <CardContent className="flex flex-col gap-2 text-sm leading-relaxed">
                {rep.source !== "llm" ? (
                  <Note>模板生成的周报，数字直接来自 SQL，不需要核对。</Note>
                ) : rep.unverified_numbers.length ? (
                  <>
                    <p className="text-up">以下数字在计算结果里找不到，可能是模型自己算的或编的，发出前请人工确认：</p>
                    <div className="flex flex-wrap gap-1.5">{rep.unverified_numbers.map((n) => <Badge key={n} variant="outline" className="border-up/40 text-up">{n}</Badge>)}</div>
                  </>
                ) : (
                  <p className="text-down">✓ 文中所有数字都能在计算结果中找到</p>
                )}
                {rep.error && <Note>大模型调用失败，已改用模板：{rep.error.slice(0, 200)}</Note>}
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-base">导出</CardTitle></CardHeader>
              <CardContent className="flex flex-col gap-2">
                <Button variant="outline" onClick={download}><IconDownload />下载 Markdown</Button>
                <Note>推送飞书由 n8n 每周一 9 点自动触发，需要在服务器配置 FEISHU_WEBHOOK。</Note>
              </CardContent>
            </Card>
            <Collapsible>
              <CollapsibleTrigger asChild><Button variant="ghost" size="sm" className="w-full justify-start text-muted-foreground">查看 SQL 计算出的原始数据（给大模型的输入）</Button></CollapsibleTrigger>
              <CollapsibleContent><pre className="mt-2 max-h-96 overflow-auto rounded-lg border bg-muted/50 p-3 font-mono text-xs">{JSON.stringify(rep.facts, null, 1)}</pre></CollapsibleContent>
            </Collapsible>
          </div>
        </div>
      )}
    </PageBody>
  )
}
