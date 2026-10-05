import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/registry/new-york-v4/ui/card"
import { Loading, Note, PageBody, PageIntro, Section, ShareBar, SimpleTable, Stats } from "./bits"
import { HBars } from "./charts"
import { num, rate, wan } from "./format"
import { useData } from "./use-data"

type D = {
  funnel: { step_no: number; step_name: string; users: number; conv_from_prev: number | null; conv_from_first: number | null }[]
  path: { path: string; buyers: number; share: number }[]
  retention: { dt: string; active_users: number; d1_retention: number | null; d3_retention: number | null; d7_retention: number | null }[]
  counts: { pv: number; cart_fav: number; buy: number }
}

export function ConversionPage() {
  const d = useData<D>("conversion")
  if (!d) return <Loading />
  const [a, b, c] = d.funnel
  const fun = d.funnel.map((r, i) => ({ name: r.step_name, value: r.users, label: `${wan(r.users)} 万${i ? `（${rate(r.conv_from_prev ?? 0)}）` : ""}` }))
  const cnt = [
    { name: "浏览", value: d.counts.pv, label: `${wan(d.counts.pv, 0)} 万次` },
    { name: "加购/收藏", value: d.counts.cart_fav, label: `${wan(d.counts.cart_fav, 0)} 万次` },
    { name: "购买", value: d.counts.buy, label: `${wan(d.counts.buy, 0)} 万次` },
  ]
  const cart = d.path.filter((p) => p.path.includes("加购")).reduce((s, p) => s + p.share, 0)
  const direct = d.path.find((p) => p.path === "直接购买")?.share ?? 0
  const pct = (v: number | null) => (v == null ? "—" : rate(v))
  return (
    <PageBody>
      <PageIntro>用“用户口径”看漏斗：每一步统计做过这个动作的人数（逐级包含）。再看买过的人走了哪条路径、活跃用户第二天还回不回来。</PageIntro>
      <Stats
        items={[
          { label: "浏览用户（万）", value: wan(a.users), line: "9 天内浏览过商品" },
          { label: "加购 / 收藏用户（万）", value: wan(b.users), line: `浏览用户的 ${rate(b.conv_from_prev ?? 0)}` },
          { label: "购买用户（万）", value: wan(c.users), line: `加购/收藏用户的 ${rate(c.conv_from_prev ?? 0)}` },
          { label: "整体转化", value: rate(c.conv_from_first ?? 0), line: "浏览用户 → 购买用户" },
        ]}
      />
      <Section cols={2}>
        <Card>
          <CardHeader>
            <CardTitle>用户漏斗</CardTitle>
            <CardDescription>人数 · 括号内为上一步转化率</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <HBars data={fun} />
            <div>
              <div className="text-sm font-medium">同样三步，换成“次数口径”</div>
            </div>
            <HBars data={cnt} color="var(--chart-1)" />
            <Note>
              次数口径下，浏览 → 购买只有 {rate(d.counts.buy / d.counts.pv)}；用户口径是 {rate(c.conv_from_first ?? 0)}。两个数都对，回答的问题不同：前者看“流量效率”，后者看“用户最终有没有买”。
            </Note>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>买过的用户走了哪条路径</CardTitle>
            <CardDescription>按是否加购、收藏划分</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <SimpleTable
              rows={d.path}
              cols={[
                { header: "购买路径", cell: (r) => <span className="font-medium">{r.path}</span> },
                { header: "人数", align: "right", cell: (r) => num(r.buyers) },
                { header: "占比", cell: (r) => <ShareBar v={r.share} /> },
              ]}
            />
            <ul className="ml-5 list-disc space-y-2 text-sm leading-relaxed">
              <li><b>加购是最主要的购买前动作</b>：{rate(cart, 0)} 的购买用户加购过商品，购物车是促成下单的关键环节。</li>
              <li><b>约 {rate(direct, 0)} 的人直接下单</b>：多为目标明确的复购或低价商品，适合用“再次购买”入口缩短路径。</li>
              <li><b>可以做的事</b>：针对“加购未购买”的用户做购物车提醒、限时优惠，是最直接的转化抓手。</li>
            </ul>
          </CardContent>
        </Card>
      </Section>
      <Section>
        <Card>
          <CardHeader>
            <CardTitle>活跃留存</CardTitle>
            <CardDescription>某天活跃的用户，N 天后是否再次活跃</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <SimpleTable
              rows={d.retention}
              cols={[
                { header: "日期", cell: (r) => <span className="font-medium">{r.dt}</span> },
                { header: "当天活跃用户", align: "right", cell: (r) => num(r.active_users) },
                { header: "次日留存", align: "right", cell: (r) => pct(r.d1_retention) },
                { header: "3 日留存", align: "right", cell: (r) => pct(r.d3_retention) },
                { header: "7 日留存", align: "right", cell: (r) => pct(r.d7_retention) },
              ]}
            />
            <div className="rounded-lg border bg-muted/40 p-4 text-sm leading-relaxed">
              <div className="mb-2 font-medium">数据解读：留存数字为什么在 12-02 前后突然跳到 98%？</div>
              <ul className="ml-5 list-disc space-y-1.5 text-muted-foreground">
                <li>只要“N 天后”那一天落在 12-02 或 12-03，留存率就会跳到 98% 左右。</li>
                <li>这两天的活跃用户比前一周同期多了约 35%，几乎所有用户都出现了。这更像是<b className="text-foreground">数据集的抽样方式</b>（抽取在这段时间有行为的用户）或大促预热造成的，不代表真实留存能力。</li>
                <li>结论：评估留存只看 11-25 至 11-30 的次日留存（约 78%–80%）更可靠。分析时先怀疑异常值，再下结论。</li>
              </ul>
            </div>
          </CardContent>
        </Card>
      </Section>
    </PageBody>
  )
}
