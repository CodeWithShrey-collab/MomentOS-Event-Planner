import { defineConfig } from '@playwright/test';

const baseURL = 'http://127.0.0.1:4173';
const pythonExecutable = process.env.MOMENTOS_PYTHON ?? (process.platform === 'win32' ? 'python' : 'python3');
const quotedPython = pythonExecutable.includes(' ') ? `"${pythonExecutable}"` : pythonExecutable;

export default defineConfig({
  testDir: './e2e',
  testMatch: 'momentos.spec.ts',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: 'list',
  use: {
    baseURL,
    browserName: 'chromium',
    viewport: { width: 1440, height: 1000 },
    reducedMotion: 'reduce',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: `${quotedPython} e2e/test_server.py`,
      url: 'http://127.0.0.1:5001/api/v1/health/ready',
      timeout: 30_000,
      reuseExistingServer: false,
      env: { MOMENTOS_TEST_PORT: '5001' },
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 4173 --strictPort',
      url: baseURL,
      timeout: 30_000,
      reuseExistingServer: false,
      env: {
        MOMENTOS_BACKEND_URL: 'http://127.0.0.1:5001',
        VITE_MOMENTOS_MODE: 'live',
      },
    },
  ],
});
