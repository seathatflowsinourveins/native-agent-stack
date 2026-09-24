import { chromium } from 'playwright';
const BASE = process.env.BASE_URL;
const t0 = Date.now();
const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(BASE + '/greeting.html');
await page.fill('#name', 'Kill Test');
console.error('READY_FOR_KILL pid=' + process.pid + ' elapsed_ms=' + (Date.now() - t0));
// Simulate a slow in-progress task the kill will interrupt.
await page.waitForTimeout(15000);
await page.click('#greet');
console.log(JSON.stringify({ finished: true, status: await page.textContent('#status') }));
