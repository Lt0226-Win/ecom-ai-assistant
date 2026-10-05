import path from "path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
      cn: path.resolve(__dirname, "src/lib/cn.ts"),
    },
  },
  base: "./",
  server: { proxy: { "/api": "http://localhost:8600" } },
})
