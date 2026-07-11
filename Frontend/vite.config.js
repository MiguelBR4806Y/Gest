import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../Frontend/dist',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '^/(productos|clientes|ventas|reportes|auth|facturas|organizacion|promociones|img)(/.*)?$': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    }
  }
})
