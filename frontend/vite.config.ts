import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendHttp = env.VITE_BACKEND_URL ?? 'http://localhost:8000'
  const backendWs = backendHttp.replace(/^http/, 'ws')
  const port = Number(env.VITE_PORT ?? '5173')

  return {
    plugins: [react()],
    server: {
      port: Number.isFinite(port) ? port : 5173,
      proxy: {
        '/ws': { target: backendWs, ws: true },
        '/api': { target: backendHttp, changeOrigin: true },
      },
    },
  }
})
