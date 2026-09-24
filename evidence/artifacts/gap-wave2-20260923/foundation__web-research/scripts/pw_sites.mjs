import { chromium } from 'playwright';
const sites = [
  "https://example.com",
  "https://en.wikipedia.org/wiki/Special:Random",
  "https://www.iana.org/domains/reserved",
  "https://playwright.dev",
  "https://httpstat.us/200",
];
const results = [];
const browser = await chromium.launch();
for (const url of sites) {
  const t0 = Date.now();
  const page = await browser.newPage();
  try {
    await page.goto(url, { timeout: 20000 });
    const title = await page.title();
    results.push({ url, success: true, ms: Date.now() - t0, title });
  } catch (e) {
    results.push({ url, success: false, ms: Date.now() - t0, error: String(e).slice(0, 200) });
  }
  await page.close();
}
await browser.close();
console.log(JSON.stringify(results, null, 1));
