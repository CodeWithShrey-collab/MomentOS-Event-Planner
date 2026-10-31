import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': { target: process.env.MOMENTOS_BACKEND_URL ?? 'http://127.0.0.1:5000', changeOrigin: false } } },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/recharts')) return 'charts';
          if (id.includes('node_modules/gsap') || id.includes('node_modules/@gsap')) return 'motion-scroll';
          if (id.includes('node_modules/motion')) return 'motion-ui';
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: true,
    globals: true,
    exclude: ['e2e/**', 'e2e-live/**', 'node_modules/**', 'dist/**', 'test-results/**', 'playwright-report/**'],
  },
});
