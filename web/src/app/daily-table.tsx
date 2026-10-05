"use client"

import * as React from "react"
import {
  IconChevronDown,
  IconChevronLeft,
  IconChevronRight,
  IconChevronsLeft,
  IconChevronsRight,
  IconLayoutColumns,
} from "@tabler/icons-react"
import {
  columnVisibilityFeature,
  createColumnHelper,
  createPaginatedRowModel,
  createSortedRowModel,
  FlexRender,
  rowPaginationFeature,
  rowSortingFeature,
  tableFeatures,
  useTable,
  type ColumnVisibilityState,
  type SortingState,
} from "@tanstack/react-table"

import { Button } from "@/registry/new-york-v4/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/registry/new-york-v4/ui/dropdown-menu"
import { Label } from "@/registry/new-york-v4/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/registry/new-york-v4/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/registry/new-york-v4/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/registry/new-york-v4/ui/tabs"
import { num, rate } from "./format"
import type { Overview } from "./use-data"

const features = tableFeatures({
  columnVisibilityFeature,
  rowPaginationFeature,
  rowSortingFeature,
  paginatedRowModel: createPaginatedRowModel(),
  sortedRowModel: createSortedRowModel(),
})

type Daily = Overview["daily"][number]
type Hourly = Overview["hourly"][number]

const dayHelper = createColumnHelper<typeof features, Daily>()
const hourHelper = createColumnHelper<typeof features, Hourly>()
const right = "text-right tabular-nums"

const dayColumns = dayHelper.columns([
  dayHelper.accessor("dt", { header: "日期", cell: ({ row }) => <span className="font-medium">{row.original.dt}</span>, enableHiding: false }),
  dayHelper.accessor("weekday", { header: "星期", cell: ({ row }) => <span className="text-muted-foreground">{row.original.weekday}</span> }),
  dayHelper.accessor("active_users", { header: "日活", cell: ({ row }) => <div className={right}>{num(row.original.active_users)}</div> }),
  dayHelper.accessor("pv_cnt", { header: "浏览", cell: ({ row }) => <div className={right}>{num(row.original.pv_cnt)}</div> }),
  dayHelper.accessor("cart_cnt", { header: "加购", cell: ({ row }) => <div className={right}>{num(row.original.cart_cnt)}</div> }),
  dayHelper.accessor("fav_cnt", { header: "收藏", cell: ({ row }) => <div className={right}>{num(row.original.fav_cnt)}</div> }),
  dayHelper.accessor("order_cnt", { header: "订单", cell: ({ row }) => <div className={right}>{num(row.original.order_cnt)}</div> }),
  dayHelper.accessor("buyers", { header: "付费用户", cell: ({ row }) => <div className={right}>{num(row.original.buyers)}</div> }),
  dayHelper.accessor("gmv", { header: "GMV（元）", cell: ({ row }) => <div className={right}>{num(row.original.gmv)}</div> }),
  dayHelper.accessor("pay_user_rate", { header: "付费率", cell: ({ row }) => <div className={right}>{rate(row.original.pay_user_rate)}</div> }),
  dayHelper.accessor("pv_order_rate", { header: "浏览转化", cell: ({ row }) => <div className={right}>{rate(row.original.pv_order_rate, 2)}</div> }),
  dayHelper.accessor("arppu", { header: "客单价（元）", cell: ({ row }) => <div className={right}>{num(row.original.arppu, 1)}</div> }),
])

const hourColumns = hourHelper.columns([
  hourHelper.accessor("hour", { header: "时段", cell: ({ row }) => <span className="font-medium">{row.original.hour} 点</span>, enableHiding: false }),
  hourHelper.accessor("avg_pv", { header: "平均浏览", cell: ({ row }) => <div className={right}>{num(row.original.avg_pv)}</div> }),
  hourHelper.accessor("avg_cart", { header: "平均加购", cell: ({ row }) => <div className={right}>{num(row.original.avg_cart)}</div> }),
  hourHelper.accessor("avg_fav", { header: "平均收藏", cell: ({ row }) => <div className={right}>{num(row.original.avg_fav)}</div> }),
  hourHelper.accessor("avg_buy", { header: "平均购买", cell: ({ row }) => <div className={right}>{num(row.original.avg_buy)}</div> }),
  hourHelper.accessor("pv_order_rate", { header: "浏览→购买转化率", cell: ({ row }) => <div className={right}>{rate(row.original.pv_order_rate, 2)}</div> }),
])

function useGrid<T>(data: T[], columns: any, pageSize: number) {
  const [columnVisibility, setColumnVisibility] = React.useState<ColumnVisibilityState>({})
  const [sorting, setSorting] = React.useState<SortingState>([])
  const [pagination, setPagination] = React.useState({ pageIndex: 0, pageSize })
  return useTable({
    features,
    data,
    columns,
    state: { sorting, columnVisibility, pagination },
    onSortingChange: setSorting,
    onColumnVisibilityChange: setColumnVisibility,
    onPaginationChange: setPagination,
  } as any) as any
}

function Grid({ table, colCount }: { table: any; colCount: number }) {
  return (
    <>
      <div className="overflow-hidden rounded-lg border">
        <Table>
          <TableHeader className="sticky top-0 z-10 bg-muted">
            {table.getHeaderGroups().map((hg: any) => (
              <TableRow key={hg.id}>
                {hg.headers.map((h: any) => (
                  <TableHead key={h.id} colSpan={h.colSpan} className="whitespace-nowrap">
                    {h.isPlaceholder ? null : <FlexRender header={h} />}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row: any) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell: any) => (
                    <TableCell key={cell.id}><FlexRender cell={cell} /></TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow><TableCell colSpan={colCount} className="h-24 text-center">没有数据</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-between px-4">
        <div className="hidden flex-1 text-sm text-muted-foreground lg:flex">共 {table.getRowCount?.() ?? table.options.data.length} 行</div>
        <div className="flex w-full items-center gap-8 lg:w-fit">
          <div className="hidden items-center gap-2 lg:flex">
            <Label className="text-sm font-medium">每页行数</Label>
            <Select value={`${table.state.pagination.pageSize}`} onValueChange={(v) => table.setPageSize(Number(v))}>
              <SelectTrigger size="sm" className="w-20"><SelectValue /></SelectTrigger>
              <SelectContent side="top">
                {[10, 24].map((n) => <SelectItem key={n} value={`${n}`}>{n}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="flex w-fit items-center justify-center text-sm font-medium">
            第 {table.state.pagination.pageIndex + 1} / {table.getPageCount()} 页
          </div>
          <div className="ml-auto flex items-center gap-2 lg:ml-0">
            <Button variant="outline" className="hidden h-8 w-8 p-0 lg:flex" onClick={() => table.setPageIndex(0)} disabled={!table.getCanPreviousPage()}>
              <span className="sr-only">第一页</span><IconChevronsLeft />
            </Button>
            <Button variant="outline" className="size-8" size="icon" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>
              <span className="sr-only">上一页</span><IconChevronLeft />
            </Button>
            <Button variant="outline" className="size-8" size="icon" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>
              <span className="sr-only">下一页</span><IconChevronRight />
            </Button>
            <Button variant="outline" className="hidden size-8 lg:flex" size="icon" onClick={() => table.setPageIndex(table.getPageCount() - 1)} disabled={!table.getCanNextPage()}>
              <span className="sr-only">最后一页</span><IconChevronsRight />
            </Button>
          </div>
        </div>
      </div>
    </>
  )
}

function ColumnsMenu({ table }: { table: any }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm">
          <IconLayoutColumns />
          <span className="hidden lg:inline">自定义列</span>
          <span className="lg:hidden">列</span>
          <IconChevronDown />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        {table.getAllColumns().filter((c: any) => typeof c.accessorFn !== "undefined" && c.getCanHide()).map((c: any) => (
          <DropdownMenuCheckboxItem key={c.id} checked={c.getIsVisible()} onCheckedChange={(v) => c.toggleVisibility(!!v)}>
            {typeof c.columnDef.header === "string" ? c.columnDef.header : c.id}
          </DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function DailyTable({ d }: { d: Overview }) {
  const [tab, setTab] = React.useState("daily")
  const dayTable = useGrid(d.daily, dayColumns, 10)
  const hourTable = useGrid(d.hourly, hourColumns, 10)
  return (
    <Tabs value={tab} onValueChange={setTab} className="w-full flex-col justify-start gap-6">
      <div className="flex items-center justify-between px-4 lg:px-6">
        <Select value={tab} onValueChange={setTab}>
          <SelectTrigger className="flex w-fit @4xl/main:hidden" size="sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="daily">每日明细</SelectItem>
            <SelectItem value="hourly">分时段</SelectItem>
          </SelectContent>
        </Select>
        <TabsList className="hidden @4xl/main:flex">
          <TabsTrigger value="daily">每日明细</TabsTrigger>
          <TabsTrigger value="hourly">分时段（9 天平均）</TabsTrigger>
        </TabsList>
        <ColumnsMenu table={tab === "daily" ? dayTable : hourTable} />
      </div>
      <TabsContent value="daily" className="relative flex flex-col gap-4 overflow-auto px-4 lg:px-6">
        <Grid table={dayTable} colCount={dayColumns.length} />
        <p className="px-1 text-xs text-muted-foreground">付费率 = 当天付费用户 ÷ 当天活跃用户；浏览转化 = 订单数 ÷ 浏览次数；客单价 = GMV ÷ 付费用户；金额为模拟价格。</p>
      </TabsContent>
      <TabsContent value="hourly" className="relative flex flex-col gap-4 overflow-auto px-4 lg:px-6">
        <Grid table={hourTable} colCount={hourColumns.length} />
      </TabsContent>
    </Tabs>
  )
}
