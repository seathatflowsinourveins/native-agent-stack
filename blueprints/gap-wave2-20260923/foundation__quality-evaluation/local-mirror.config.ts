// Wrapper around the unchanged upstream examples/todomvc playwright.config.ts.
// Chromium resolves demo.playwright.dev to the loopback TLS mirror, so the
// upstream specs and fixtures.ts run byte-identical against local app bytes.
import base from './playwright.config';
import { defineConfig } from '@playwright/test';

const port = process.env.MIRROR_PORT;
if (!port) throw new Error('MIRROR_PORT is required');

export default defineConfig({
  ...base,
  reporter: [['list']],
  use: {
    ...base.use,
    ignoreHTTPSErrors: true,
    launchOptions: { args: [`--host-resolver-rules=MAP demo.playwright.dev 127.0.0.1:${port}`] },
  },
});
