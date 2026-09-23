import { chromium } from 'playwright';

const BASE = process.env.BASE_URL;
const results = [];

async function timeIt(name, fn) {
  const t0 = Date.now();
  try {
    const out = await fn();
    results.push({ task: name, success: true, ms: Date.now() - t0, detail: out });
  } catch (e) {
    results.push({ task: name, success: false, ms: Date.now() - t0, detail: String(e).slice(0, 300) });
  }
}

const browser = await chromium.launch();
const page = await browser.newPage();

await timeIt('task1_open_read_title', async () => {
  await page.goto(BASE + '/greeting.html');
  return await page.title();
});

await timeIt('task2_fill_click_read_status', async () => {
  await page.fill('#name', 'Gap Wave 2');
  await page.click('#greet');
  return await page.textContent('#status');
});

await timeIt('task3_nonexistent_selector', async () => {
  await page.click('#does-not-exist', { timeout: 2000 });
  return 'unexpected-success';
});

await browser.close();
console.log(JSON.stringify(results, null, 1));
