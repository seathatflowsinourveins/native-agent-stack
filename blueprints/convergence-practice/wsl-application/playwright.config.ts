import path from 'node:path';
import base from '../application-delivery/playwright.config';

// Keep the frozen browser oracle and server lifecycle. Only select the isolated
// Linux browser executable; never attach to an existing personal browser.
const executablePath = process.env.WSL_CHROME_EXECUTABLE;
if (!executablePath || !path.isAbsolute(executablePath)) {
  throw new Error('WSL_CHROME_EXECUTABLE must name the absolute task-owned Chrome executable');
}

export default {
  ...base,
  testDir: path.resolve(__dirname, '../application-delivery/browser'),
  webServer: {
    ...base.webServer,
    cwd: path.resolve(__dirname, '../application-delivery'),
  },
  use: {
    ...base.use,
    launchOptions: { executablePath, args: ['--disable-gpu'] },
  },
};
