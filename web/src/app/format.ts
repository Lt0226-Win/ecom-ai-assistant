export const wan = (v: number, nd = 1) => (v / 1e4).toLocaleString("en-US", { minimumFractionDigits: nd, maximumFractionDigits: nd })
export const rate = (v: number, nd = 1) => `${(v * 100).toFixed(nd)}%`
export const num = (v: number, nd = 0) => v.toLocaleString("en-US", { minimumFractionDigits: nd, maximumFractionDigits: nd })
export const signedPct = (v: number, nd = 1) => `${v >= 0 ? "+" : ""}${(v * 100).toFixed(nd)}%`
