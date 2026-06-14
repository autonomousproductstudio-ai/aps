import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The rich UI talks to the backend's rich contract under /v1 (REST + WebSocket). The dev
// server proxies /v1 to the FastAPI app on :8000 so the browser hits one origin (no CORS
// dance in dev) and WebSocket upgrades pass through.
const backend = `http://localhost:${process.env.VITE_API_PORT ?? 8011}`

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    proxy: {
      '/v1': {
        // Backend port. 8000 is often blocked on Windows (Hyper-V reserved range → WinError
        // 10013); 8011 avoids it. Override with VITE_API_PORT if needed.
        target: backend,
        changeOrigin: true,
        ws: true,
      },
      // Dodo Payments billing API (server-side checkout + subscriptions + webhook).
      '/api': {
        target: backend,
        changeOrigin: true,
      },
    },
  },
})
