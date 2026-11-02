import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Legacy web UI dev server. Proxies /api to the Legacy Task API on :4000.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.LEGACY_API_URL || 'http://127.0.0.1:4000',
        changeOrigin: true,
      },
    },
  },
});
