import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendHttp = env.VITE_BACKEND_URL ?? 'http://localhost:8000'
  let backendWs: string
  if (backendHttp.startsWith('https://')) {
    backendWs = backendHttp.replace('https://', 'wss://')
  } else if (backendHttp.startsWith('http://')) {
    backendWs = backendHttp.replace('http://', 'ws://')
  } else {
    throw new Error(`VITE_BACKEND_URL must start with http:// or https://, got: ${backendHttp}`)
  }
  const port = Number(env.VITE_PORT ?? '5173')
  const serverPort = Number.isInteger(port) && port >= 1 && port <= 65535 ? port : 5173

  return {
    plugins: [react()],
    server: {
      port: serverPort,
      proxy: {
        '/ws': { target: backendWs, ws: true },
        '/api': { target: backendHttp, changeOrigin: true },
      },
    },
  }
})
