import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './browser',
  timeout: 30000,
  retries: 0,
  workers: 1,
  reporter: [['list'], ['json', { outputFile: '.runtime/browser-results.json' }]],
  webServer: {
    command: 'python3 serve.py',
    url: 'http://127.0.0.1:18080',
    reuseExistingServer: false,
    timeout: 30000,
    gracefulShutdown: { signal: 'SIGTERM', timeout: 10000 },
  },
  use: { baseURL: 'http://127.0.0.1:18080', browserName: 'chromium', channel: 'chrome', headless: true, trace: 'retain-on-failure' },
});
