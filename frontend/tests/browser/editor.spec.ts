import { expect, test } from '@playwright/test';
import { demoOperator, statusAt } from '../fixtures';

test('constellation add and remove create a fresh run', async ({ page }) => {
  const original = statusAt(-1, 'created', 1);
  const replacement = { ...statusAt(-1, 'created', 1), run_id: 'edited-run' };
  let current = original;
  let submitted: Record<string, any> | undefined;
  const satellites = original.satellites.map((item: Record<string, any>) => ({
    satellite_id: item.satellite_id,
    name: item.name,
    profile_id: 'leo_power_demo',
    orbit: { a_m: 6928137, e: 0.001, i_deg: 97.6, raan_deg: 0,
      argp_deg: 0, true_anomaly_deg: 0 },
    initial_mode: 'nominal',
    operations: [{ start_s: 10, end_s: 20, mode: 'safe' }],
    visual: { color: item.color, asset_id: null },
    power: { panel_area_m2: 0.9, panel_efficiency: 0.28,
      battery_capacity_wh: 400, battery_initial_soc: 0.85,
      loads_w: { nominal: 150, payload_active: 210, safe: 70 } },
  }));
  await page.route('**/v1/viewer/session', route => route.fulfill({
    json: { operator: demoOperator, csrf_token: 'test-csrf', allowed_actions: ['start', 'pause', 'resume', 'set_speed', 'stop'], run: current },
  }));
  await page.route('**/v1/viewer/configuration', route => {
    if (route.request().method() === 'GET') return route.fulfill({ json: { satellites } });
    submitted = route.request().postDataJSON();
    current = replacement;
    return route.fulfill({ json: { operator: demoOperator, csrf_token: 'next-csrf', allowed_actions: ['start', 'stop'], run: replacement } });
  });
  await page.route('**/v1/runs/*/snapshot?history=41', route => route.fulfill({
    json: { status: current, frames: [] },
  }));
  await page.routeWebSocket('**/v1/runs/*/visual', () => {});
  await page.goto('/');
  await page.getByRole('button', { name: 'Edit constellation' }).click();
  await expect(page.getByRole('alertdialog')).toBeVisible();
  await page.getByRole('button', { name: 'Add satellite' }).click();
  await expect(page.getByRole('button', { name: /METIS-1 · Metis 1/ })).toBeVisible();
  await page.getByRole('button', { name: 'Remove satellite' }).click();
  await page.getByRole('button', { name: 'Add satellite' }).click();
  await page.getByRole('button', { name: 'Save as new run' }).click();
  await expect.poll(() => submitted?.satellites.length).toBe(4);
  expect(submitted?.satellites[3].name).toBe('Metis 1');
  expect(submitted?.satellites[3].power.panel_area_m2).toBe(0.9);
  expect(submitted?.satellites.every((item: Record<string, any>) => item.operations.length === 0)).toBe(true);
  await expect(page.getByRole('button', { name: 'Start run' })).toBeEnabled();
});
