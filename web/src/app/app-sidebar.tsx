"use client"

import * as React from "react"
import {
  IconArrowLeft,
  IconBrandGithub,
  IconCategory,
  IconDashboard,
  IconFileDescription,
  IconFilter,
  IconHeadset,
  IconInfoCircle,
  IconInnerShadowTop,
  IconMessageChatbot,
  IconSparkles,
  IconUsers,
  type Icon,
} from "@tabler/icons-react"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/registry/new-york-v4/ui/sidebar"

export type PageId = "overview" | "conversion" | "users" | "category" | "ask" | "report" | "service"
export const PAGES: { id: PageId; title: string; icon: Icon; group: "ops" | "ai" }[] = [
  { id: "overview", title: "经营总览", icon: IconDashboard, group: "ops" },
  { id: "conversion", title: "用户转化", icon: IconFilter, group: "ops" },
  { id: "users", title: "用户分层", icon: IconUsers, group: "ops" },
  { id: "category", title: "品类分析", icon: IconCategory, group: "ops" },
  { id: "ask", title: "AI 问数", icon: IconMessageChatbot, group: "ai" },
  { id: "report", title: "自动周报", icon: IconFileDescription, group: "ai" },
  { id: "service", title: "智能客服", icon: IconHeadset, group: "ai" },
]

const GITHUB = "https://github.com/Lt0226-Win/ecom-ai-assistant"

export function AppSidebar({
  page,
  onNavigate,
  ...props
}: { page: PageId; onNavigate: (p: PageId) => void } & React.ComponentProps<typeof Sidebar>) {
  const item = (p: (typeof PAGES)[number]) => (
    <SidebarMenuItem key={p.id}>
      <SidebarMenuButton tooltip={p.title} isActive={page === p.id} onClick={() => onNavigate(p.id)}>
        <p.icon />
        <span>{p.title}</span>
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
  return (
    <Sidebar collapsible="offcanvas" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton className="data-[slot=sidebar-menu-button]:p-1.5!" onClick={() => onNavigate("overview")}>
              <IconInnerShadowTop className="size-5!" />
              <span className="text-base font-semibold">电商 AI 运营助手</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent className="flex flex-col gap-2">
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  tooltip="向 AI 提问"
                  onClick={() => onNavigate("ask")}
                  className="min-w-8 bg-primary text-primary-foreground duration-200 ease-linear hover:bg-primary/90 hover:text-primary-foreground active:bg-primary/90 active:text-primary-foreground"
                >
                  <IconSparkles />
                  <span>向 AI 提问</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
            <SidebarMenu>{PAGES.filter((p) => p.group === "ops").map(item)}</SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup className="group-data-[collapsible=icon]:hidden">
          <SidebarGroupLabel>AI 助手</SidebarGroupLabel>
          <SidebarMenu>{PAGES.filter((p) => p.group === "ai").map(item)}</SidebarMenu>
        </SidebarGroup>
        <SidebarGroup className="mt-auto">
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild>
                  <a href={GITHUB} target="_blank" rel="noopener noreferrer"><IconBrandGithub /><span>GitHub 仓库</span></a>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild>
                  <a href="../"><IconArrowLeft /><span>返回作品集首页</span></a>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <div className="flex items-start gap-2 px-2 py-1.5 text-xs leading-relaxed text-muted-foreground">
          <IconInfoCircle className="mt-0.5 size-4 shrink-0" />
          <span>淘宝用户行为数据（阿里天池公开数据集）· 2017-11-25 至 12-03 · 约 98.8 万用户、1 亿条行为。金额基于模拟价格。</span>
        </div>
      </SidebarFooter>
    </Sidebar>
  )
}
