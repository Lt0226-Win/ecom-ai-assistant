import * as React from "react"

/** 读取 public/data/<name>.json（由 tools/export_dashboard_data.py 从数仓导出） */
export function useData<T>(name: string): T | null {
  const [data, setData] = React.useState<T | null>(null)
  React.useEffect(() => {
    fetch(`./data/${name}.json`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null))
  }, [name])
  return data
}

export type Overview = {
  period: { start: string; end: string }
  wow_label: string
  totals: { gmv: number; orders: number; avg_active: number; users: number; buyers: number; repeat_buyers: number }
  wow: { gmv: number; order_cnt: number; active_users: number }
  daily: {
    dt: string; weekday: string; active_users: number; pv_cnt: number; cart_cnt: number; fav_cnt: number
    order_cnt: number; buyers: number; gmv: number; pay_user_rate: number; pv_order_rate: number; arppu: number
  }[]
  hourly: { hour: number; avg_pv: number; avg_cart: number; avg_fav: number; avg_buy: number; pv_order_rate: number }[]
  findings: { title: string; text: string }[]
}
