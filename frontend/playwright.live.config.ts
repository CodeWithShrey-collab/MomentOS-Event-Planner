import { defineConfig } from '@playwright/test';

const backendPort = process.env.MOMENTOS_LIVE_TEST_PORT ?? '5002';
const frontendPort = process.env.MOMENTOS_LIVE_TEST_WEB_PORT ?? '4174';
const backendURL = `http://127.0.0.1:${backendPort}`;
const baseURL = `http://127.0.0.1:${frontendPort}`;
const pythonExecutable = process.env.MOMENTOS_PYTHON ?? (process.platform === 'win32' ? 'python' : 'python3');
const quotedPython = pythonExecutable.includes(' ') ? `"${pythonExecutable}"` : pythonExecutable;

export default defineConfig({
  testDir: './e2e-live',
  testMatch: '*.spec.ts',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: 'list',
  outputDir: './test-results/stage07-live-mock',
  use: {
    baseURL,
    browserName: 'chromium',
    viewport: { width: 1440, height: 900 },
    reducedMotion: 'reduce',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: `${quotedPython} e2e-live/test_server.py`,
      url: `${backendURL}/api/v1/health/ready`,
      timeout: 30_000,
      reuseExistingServer: false,
      env: { MOMENTOS_LIVE_TEST_PORT: backendPort, MOMENTOS_LIVE_TEST_WEB_PORT: frontendPort },
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort} --strictPort`,
      url: baseURL,
      timeout: 30_000,
      reuseExistingServer: false,
      env: {
        MOMENTOS_BACKEND_URL: backendURL,
        VITE_MOMENTOS_MODE: 'live',
      },
    },
  ],
});
