import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev proxy to your FastAPI on http://localhost:8000
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
})
