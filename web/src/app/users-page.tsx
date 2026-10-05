import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/registry/new-york-v4/ui/card"
import { Loading, Note, PageBody, PageIntro, Section, SimpleTable, Stats } from "./bits"
import { GroupedHBars, VBars } from "./charts"
import { num, rate, wan } from "./format"
import { useData } from "./use-data"

type D = {
  segments: { segment: string; users: number; user_share: number; gmv: number; gmv_share: number; avg_recency_days: number; avg_frequency: number; avg_monetary: number }[]
  repurchase: { buy_days_bucket: string; buyers: number; share: number }[]
  threshold: { r_med: number; m_med: number; n: number; m_avg: number; rep: number }
}

const ACTION: Record<string, string> = {
  重要价值客户: "核心用户：会员权益、专属客服、新品优先体验，重点防流失",
  重要发展客户: "买得多但只买过一次：引导复购，推荐关联商品、发复购券",
  重要保持客户: "以前常买、最近没来：推送召回消息、个性化推荐",
  重要挽留客户: "高价值但沉默：大额优惠券召回，了解流失原因",
  一般价值客户: "常买但金额低：凑单满减、推荐高客单价商品",
  一般发展客户: "新客或低频：新人专享、小额券培养购买习惯",
  一般保持客户: "频次尚可、近期不活跃：低成本推送提醒",
  一般挽留客户: "价值低且沉默：低成本触达，不投入重资源",
}

export function UsersPage() {
  const d = useData<D>("users")
  if (!d) return <Loading />
  const t = d.threshold
  const top = d.segments.find((s) => s.segment === "重要价值客户")
  return (
    <PageBody>
      <PageIntro>把付费用户按 R（最近一次购买距今几天）、F（有购买的天数）、M（消费金额）分成 8 类，不同人群用不同的运营动作。M 基于模拟价格。</PageIntro>
      <Stats
        items={[
          { label: "付费用户（万）", value: wan(t.n), line: "9 天内至少买过一次" },
          { label: "复购率", value: rate(t.rep), line: "2 天及以上有购买" },
          { label: "人均消费（模拟，元）", value: num(t.m_avg), line: `中位数 ${num(t.m_med)} 元` },
          { label: "重要价值客户", value: rate(top?.user_share ?? 0), line: `贡献 ${rate(top?.gmv_share ?? 0)} 的 GMV` },
        ]}
      />
      <Section>
        <Card>
          <CardHeader>
            <CardTitle>各人群画像和运营建议</CardTitle>
            <CardDescription>R / F / M 为人群平均值</CardDescription>
          </CardHeader>
          <CardContent>
            <SimpleTable
              rows={d.segments}
              cols={[
                { header: "人群", cell: (r) => <span className="font-medium whitespace-nowrap">{r.segment}</span> },
                { header: "人数", align: "right", cell: (r) => num(r.users) },
                { header: "人数占比", align: "right", cell: (r) => rate(r.user_share) },
                { header: "GMV 占比", align: "right", cell: (r) => rate(r.gmv_share) },
                { header: "R（天）", align: "right", cell: (r) => num(r.avg_recency_days, 1) },
                { header: "F（天）", align: "right", cell: (r) => num(r.avg_frequency, 1) },
                { header: "M（元）", align: "right", cell: (r) => num(r.avg_monetary) },
                { header: "运营建议", className: "min-w-64 whitespace-normal text-muted-foreground", cell: (r) => ACTION[r.segment] ?? "" },
              ]}
            />
          </CardContent>
        </Card>
      </Section>
      <Section cols={2}>
        <Card>
          <CardHeader>
            <CardTitle>人数占比 vs 成交占比</CardTitle>
            <CardDescription>按 GMV 从高到低</CardDescription>
          </CardHeader>
          <CardContent>
            <GroupedHBars data={d.segments.map((s) => ({ name: s.segment, a: s.user_share, b: s.gmv_share }))} a="人数占比" b="GMV 占比" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>购买天数分布</CardTitle>
            <CardDescription>付费用户 9 天内有几天下过单</CardDescription>
          </CardHeader>
          <CardContent>
            <VBars data={d.repurchase.map((r) => ({ name: r.buy_days_bucket, value: r.buyers }))} height={400} fmt={(v) => `${wan(v, 0)}万`} />
          </CardContent>
        </Card>
      </Section>
      <Section>
        <Card>
          <CardHeader>
            <CardTitle>分层规则</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <ul className="ml-5 list-disc space-y-2 text-sm leading-relaxed">
              <li><b>R 高</b>：最近一次购买距 12-04 不超过 {num(t.r_med)} 天（付费用户中位数）</li>
              <li><b>F 高</b>：有 2 天及以上下过单（即复购用户）。只有 9 天数据，按“天数”比按“次数”更能代表购买习惯</li>
              <li><b>M 高</b>：消费金额不低于 {num(t.m_med)} 元（付费用户中位数）</li>
              <li>三个维度各分高/低，组合成 2×2×2 = 8 类。阈值用中位数而不是平均数，因为消费金额是长尾分布，平均数会被少数大户拉高。</li>
            </ul>
            <Note>真实业务通常用 1–3 个月的数据、按五分位打分（每个维度 1–5 分）；这里数据只有 9 天，用简化的高/低两档。</Note>
          </CardContent>
        </Card>
      </Section>
    </PageBody>
  )
}
