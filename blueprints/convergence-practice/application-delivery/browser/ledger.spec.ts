import { test, expect } from '@playwright/test';
import { randomUUID } from 'node:crypto';

test('create and update a recorded run through the production UI', async ({ page }) => {
  const errors: string[] = [];
  const title = `Release acceptance ${randomUUID()}`;
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Run ledger', exact: true })).toBeVisible();
  await page.getByLabel('Run title').fill(title);
  await page.getByRole('button', { name: 'Create run', exact: true }).click();
  const row = page.getByTestId('run-row').filter({ has: page.getByRole('heading', { name: title, exact: true }) });
  await expect(row).toHaveCount(1);
  await expect(row).toContainText('Revision 1 · 1 recorded changes');
  await row.getByRole('combobox').selectOption('passed');
  await expect(row).toContainText('Revision 2 · 2 recorded changes');
  await page.reload();
  await expect(row.getByRole('combobox')).toHaveValue('passed');
  await expect(row).toContainText('Revision 2 · 2 recorded changes');
  expect(errors).toEqual([]);
});
