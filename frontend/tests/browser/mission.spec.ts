import { expect, test } from '@playwright/test';
import { framesBetween, statusAt } from '../fixtures';

test('Flutter controls, telemetry, offline Cesium, and stale freeze', async ({ page }) => {
  let current = statusAt(40);
  const commands: Record<string, any>[] = [];
  const errors: string[] = [], external: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', request => {
    if (/^https?:/.test(request.url()) && !request.url().startsWith('http://127.0.0.1:4173/')) external.push(request.url());
  });
  await page.route('**/v1/viewer/bootstrap', route => route.fulfill({json: {csrf_token: 'test-csrf', allowed_actions: ['start', 'pause', 'resume', 'set_speed', 'stop'], run: current}}));
  await page.route('**/v1/runs/test-run/snapshot?history=41', route => route.fulfill({json: {status: current, frames: framesBetween(Math.max(0, current.committed_tick-40), current.committed_tick)}}));
  await page.route('**/v1/runs/test-run/trajectory?*', route => route.fulfill({json: {run_id:'test-run', frame:'ITRS', kind:'predicted_orbit', satellites:[]}}));
  await page.route('**/v1/runs/test-run/control', async route => {
    const body = route.request().postDataJSON();
    commands.push({...body, csrf: route.request().headers()['x-csrf-token'], key: route.request().headers()['idempotency-key']});
    current = statusAt(body.action === 'pause' ? 44 : current.committed_tick, body.action === 'pause' ? 'paused' : body.action === 'resume' ? 'running' : body.action === 'stop' ? 'stopped' : current.status, body.speed ?? current.requested_speed);
    await route.fulfill({json: current});
  });
  await page.routeWebSocket('**/v1/runs/test-run/visual', socket => socket.send(JSON.stringify({visual_schema_version:'visual.v1', type:'snapshot', sent_at:new Date().toISOString(), run_id:'test-run', status:current, frames:framesBetween(0,40), ranges:[], message:null})));
  await page.goto('/');
  await expect(page.getByRole('heading', {name:'Orbital overview', exact:true})).toBeVisible();
  await expect(page.locator('#metis-earth canvas')).toBeVisible();
  await expect(page.getByText(/322\.4 W/)).toBeVisible();
  await page.getByRole('button', {name:/METIS-02 Sunlit/}).click();
  await expect(page.getByRole('button', {name:/METIS-02 Sunlit/})).toHaveAttribute('aria-current', 'true');
  await page.getByRole('button', {name:'Follow selected satellite', exact:true}).click();
  await page.mouse.move(0, 0);
  await page.getByRole('button', {name:'Reset Earth view', exact:true}).click();
  await page.getByRole('checkbox', {name:'5×', exact:true}).click();
  await expect.poll(() => commands.length).toBe(1);
  await page.getByRole('button', {name:'Pause', exact:true}).click();
  await expect(page.getByRole('button', {name:'Resume', exact:true})).toBeVisible();
  await expect(page.getByText(/T\+ 44\.0 s/)).toBeVisible();
  await page.getByRole('button', {name:'Resume', exact:true}).click();
  await expect(page.getByText(/Data stale · view frozen/)).toBeVisible({timeout:8000});
  await page.getByRole('button', {name:'Model & credits', exact:true}).click();
  await expect(page.getByText('Simulation model & credits', {exact:true})).toBeVisible();
  await page.getByRole('button', {name:'Close', exact:true}).click();
  await expect(page.getByText('Simulation model & credits', {exact:true})).not.toBeVisible();
  expect(commands.every(c => c.csrf === 'test-csrf' && c.key)).toBeTruthy();
  expect(errors).toEqual([]);
  expect(external).toEqual([]);
  await page.screenshot({path:'artifacts/flutter-mission.png'});
});
