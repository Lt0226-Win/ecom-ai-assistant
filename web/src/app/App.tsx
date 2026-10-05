import * as React from "react"

import { SidebarInset, SidebarProvider } from "@/registry/new-york-v4/ui/sidebar"
import { AppSidebar, PAGES, type PageId } from "./app-sidebar"
import { AskPage } from "./ask-page"
import { CategoryPage } from "./category-page"
import { ConversionPage } from "./conversion-page"
import { OverviewPage } from "./overview-page"
import { ReportPage } from "./report-page"
import { ServicePage } from "./service-page"
import { UsersPage } from "./users-page"
import { SiteHeader } from "./site-header"

function fromHash(): PageId {
  const h = location.hash.replace("#/", "") as PageId
  return PAGES.some((p) => p.id === h) ? h : "overview"
}

export default function App() {
  const [page, setPage] = React.useState<PageId>(fromHash)
  React.useEffect(() => {
    const on = () => setPage(fromHash())
    window.addEventListener("hashchange", on)
    return () => window.removeEventListener("hashchange", on)
  }, [])
  const go = (p: PageId) => {
    location.hash = `#/${p}`
  }
  const title = PAGES.find((p) => p.id === page)!.title
  return (
    <SidebarProvider
      style={{ "--sidebar-width": "calc(var(--spacing) * 72)", "--header-height": "calc(var(--spacing) * 12)" } as React.CSSProperties}
    >
      <AppSidebar variant="inset" page={page} onNavigate={go} />
      <SidebarInset>
        <SiteHeader title={title} />
        <div className="flex flex-1 flex-col">
          <div className="@container/main flex flex-1 flex-col gap-2">
            {page === "overview" ? <OverviewPage />
              : page === "conversion" ? <ConversionPage />
              : page === "users" ? <UsersPage />
              : page === "category" ? <CategoryPage />
              : page === "ask" ? <AskPage />
              : page === "report" ? <ReportPage />
              : <ServicePage />}
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
