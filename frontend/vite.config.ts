import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In development the Vite server proxies API and evidence-file requests to the
// FastAPI backend, so the browser sees a single origin (same as production,
// where FastAPI serves the built frontend itself).
const backend = 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': backend,
      '/files': backend,
      '/docs': backend,
      '/openapi.json': backend,
    },
  },
  build: {
    chunkSizeWarningLimit: 1200,
  },
});
