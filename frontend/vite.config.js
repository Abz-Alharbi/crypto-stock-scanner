import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const previewAllowedHosts = [
  'scannerfrontend-production.up.railway.app',
  process.env.RAILWAY_PUBLIC_DOMAIN,
].filter(Boolean)

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        timeout: 600000,
        proxyTimeout: 600000,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
  preview: {
    allowedHosts: previewAllowedHosts,
  },
})
