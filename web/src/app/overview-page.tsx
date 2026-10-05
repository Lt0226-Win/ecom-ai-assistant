import { Card, CardDescription, CardHeader, CardTitle } from "@/registry/new-york-v4/ui/card"
import { ChartAreaInteractive } from "./chart-area-interactive"
import { DailyTable } from "./daily-table"
import { SectionCards } from "./section-cards"
import { useData, type Overview } from "./use-data"

export function OverviewPage() {
  const d = useData<Overview>("overview")
  if (!d) return <div className="p-6 text-sm text-muted-foreground">正在加载数据…</div>
  return (
    <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
      <SectionCards d={d} />
      <div className="px-4 lg:px-6">
        <ChartAreaInteractive d={d} />
      </div>
      <div className="grid grid-cols-1 gap-4 px-4 *:data-[slot=card]:shadow-xs lg:px-6 @3xl/main:grid-cols-2">
        {d.findings.map((f) => (
          <Card key={f.title} className="@container/card">
            <CardHeader>
              <CardTitle className="text-base">{f.title}</CardTitle>
              <CardDescription className="text-sm leading-relaxed">{f.text}</CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>
      <DailyTable d={d} />
    </div>
  )
}
