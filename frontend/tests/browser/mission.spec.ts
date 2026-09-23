import { expect, test, type Page, type WebSocketRoute } from '@playwright/test';
import { frameAt, framesBetween, statusAt } from '../fixtures';
import type { PublicRunStatus, VisualMessage } from '../../src/api/generated';

test('renders offline globe, scopes controls, changes selection, and freezes stale playback', async ({
  page,
}) => {
  let current: PublicRunStatus = statusAt(40);
  const commands: {
    action: string;
    speed?: number;
    csrf: string | undefined;
    key: string | undefined;
  }[] = [];
  const errors: string[] = [];
  const external: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('request', (request) => {
    if (/^https?:/.test(request.url()) && !request.url().startsWith('http://127.0.0.1:4173/'))
      external.push(request.url());
  });
  await page.route('**/v1/viewer/bootstrap', (route) =>
    route.fulfill({ json: { csrf_token: 'test-csrf', run: current } }),
  );
  await page.route('**/v1/runs/test-run/snapshot?history=41', (route) =>
    route.fulfill({
      json: {
        status: current,
        frames: framesBetween(Math.max(0, current.committed_tick - 40), current.committed_tick),
      },
    }),
  );
  await page.route('**/v1/runs/test-run/trajectory?*', (route) =>
    route.fulfill({
      json: { run_id: 'test-run', frame: 'ITRS', kind: 'predicted_orbit', satellites: [] },
    }),
  );
  await page.route('**/v1/runs/test-run/control', async (route) => {
    const body = route.request().postDataJSON() as { action: string; speed?: 1 | 5 | 20 };
    commands.push({
      ...body,
      csrf: route.request().headers()['x-csrf-token'],
      key: route.request().headers()['idempotency-key'],
    });
    current = statusAt(
      body.action === 'pause' ? 44 : current.committed_tick,
      body.action === 'pause' ? 'paused' : body.action === 'resume' ? 'running' : current.status,
      body.speed ?? current.requested_speed,
    );
    await route.fulfill({ json: current });
  });
  await page.routeWebSocket('**/v1/runs/test-run/visual', (socket) => {
    const message: VisualMessage = {
      visual_schema_version: 'visual.v1',
      type: 'snapshot',
      sent_at: new Date().toISOString(),
      run_id: 'test-run',
      status: current,
      frames: framesBetween(0, 40),
      ranges: [],
      message: null,
    };
    socket.send(JSON.stringify(message));
  });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Orbital overview' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'METIS-01' })).toBeVisible();
  await expect(page.locator('.globe canvas')).toBeVisible({ timeout: 15000 });
  await expect
    .poll(async () => Number(await page.locator('.scene-fps').getAttribute('data-fps')), {
      timeout: 15000,
    })
    .toBeGreaterThan(0);
  await expect(page.locator('.scene-fps')).toHaveAttribute('data-positioned-count', '3', {
    timeout: 15000,
  });
  await expect(page.locator('.scene-fps')).toHaveAttribute(
    'data-positioned-spacecraft',
    'METIS-01,METIS-02,METIS-03',
  );
  await expect(page.getByText('322.4', { exact: false }).first()).toBeVisible();
  await page.getByRole('button', { name: /METIS-02/ }).click();
  await expect(page.getByRole('heading', { name: 'METIS-02' })).toBeVisible();
  await page.getByRole('button', { name: '5×', exact: true }).click();
  await expect(page.getByRole('button', { name: '5×', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await page.getByRole('button', { name: 'Pause simulation' }).click();
  await expect(page.getByRole('button', { name: 'Resume simulation' })).toBeVisible();
  await expect(page.locator('.mission-clock strong')).toContainText('00:00:44');
  await expect(page.getByText('Sample 00:00:44 UTC')).toBeVisible();
  await page.screenshot({ path: 'test-results/mission-control.png' });
  await page.getByRole('button', { name: 'Resume simulation' }).click();
  await expect(page.getByText('Data stale · view frozen')).toBeVisible({ timeout: 5000 });
  const frozenTime = await page.locator('.mission-clock strong').textContent();
  await page.waitForTimeout(250);
  expect(await page.locator('.mission-clock strong').textContent()).toBe(frozenTime);
  await page.getByRole('button', { name: 'View simulation model information' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByText(/Visual lighting is approximate/)).toBeVisible();
  expect(commands.every((command) => command.csrf === 'test-csrf' && !!command.key)).toBe(true);
  expect(errors).toEqual([]);
  expect(external).toEqual([]);
});

async function mockPausedMission(page: Page): Promise<void> {
  const current = statusAt(40, 'paused');
  await page.route('**/v1/viewer/bootstrap', (route) =>
    route.fulfill({ json: { csrf_token: 'test-csrf', run: current } }),
  );
  await page.route('**/v1/runs/test-run/snapshot?history=41', (route) =>
    route.fulfill({ json: { status: current, frames: framesBetween(0, 40) } }),
  );
  await page.route('**/v1/runs/test-run/trajectory?*', (route) =>
    route.fulfill({
      json: { run_id: 'test-run', frame: 'ITRS', kind: 'predicted_orbit', satellites: [] },
    }),
  );
  await page.routeWebSocket('**/v1/runs/test-run/visual', () => {});
}

test('retains keyboard-accessible measurements in a compact viewport', async ({ page }) => {
  await page.setViewportSize({ width: 760, height: 1024 });
  await mockPausedMission(page);
  await page.goto('/');
  await page.getByRole('button', { name: /METIS-03/ }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'METIS-03' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('reports scene FPS unavailable when WebGL cannot initialize', async ({ page }) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (
      this: HTMLCanvasElement,
      type: string,
      ...args: unknown[]
    ) {
      if (type === 'webgl' || type === 'webgl2' || type === 'experimental-webgl') return null;
      return Reflect.apply(original, this, [type, ...args]);
    } as typeof original;
  });
  await mockPausedMission(page);
  await page.goto('/');
  await expect(
    page.getByText('The 3D view needs WebGL 2. Satellite measurements remain available.'),
  ).toBeVisible({ timeout: 15000 });
  await expect(page.locator('.scene-fps')).toHaveText('Scene unavailable');
  await expect(page.getByRole('heading', { name: 'METIS-01' })).toBeVisible();
  expect(await page.locator('.scene-fps').getAttribute('data-fps')).toBeNull();
});

test('reconnects reused satellite IDs without accepting the prior mission control response', async ({
  page,
}) => {
  const original = statusAt(40, 'paused');
  const replacement: PublicRunStatus = {
    ...statusAt(-1, 'created', 1),
    run_id: 'replacement-run',
    // Overlap the first run's sample times, so epoch bounds cannot mask retained samples.
    epoch_utc: '2026-09-21T00:00:20Z',
    committed_at: null,
    satellites: original.satellites.map((satellite) => ({
      ...satellite,
      stream_id: `replacement-${satellite.stream_id}`,
      name: `Replacement ${satellite.satellite_id}`,
    })),
  };
  let reconnecting = false;
  let oldSnapshots = 0;
  let originalSocket: WebSocketRoute | undefined;
  let replacementSocket: WebSocketRoute | undefined;
  let releaseOldControl!: () => void;
  let releaseNewSnapshot!: () => void;
  const oldControlGate = new Promise<void>((resolve) => (releaseOldControl = resolve));
  const newSnapshotGate = new Promise<void>((resolve) => (releaseNewSnapshot = resolve));

  await page.route('**/v1/viewer/bootstrap', (route) =>
    route.fulfill({
      json: { csrf_token: 'test-csrf', run: reconnecting ? replacement : original },
    }),
  );
  await page.route('**/v1/runs/test-run/snapshot?history=41', (route) => {
    oldSnapshots++;
    return route.fulfill({ json: { status: original, frames: framesBetween(0, 40) } });
  });
  await page.route('**/v1/runs/replacement-run/snapshot?history=41', async (route) => {
    await newSnapshotGate;
    await route.fulfill({ json: { status: replacement, frames: [] } });
  });
  await page.route('**/trajectory?*', (route) =>
    route.fulfill({
      json: {
        run_id: route.request().url().includes('replacement-run')
          ? replacement.run_id
          : original.run_id,
        frame: 'ITRS',
        kind: 'predicted_orbit',
        satellites: [],
      },
    }),
  );
  await page.route('**/v1/runs/test-run/control', async (route) => {
    await oldControlGate;
    await route.fulfill({ json: { ...original, requested_speed: 5, status_revision: 42 } });
  });
  await page.routeWebSocket('**/v1/runs/test-run/visual', (socket) => {
    originalSocket = socket;
  });
  await page.routeWebSocket('**/v1/runs/replacement-run/visual', (socket) => {
    replacementSocket = socket;
  });
  await page.goto('/');
  await expect
    .poll(
      async () =>
        Number(
          await page
            .getByRole('meter', { name: 'Battery state of charge' })
            .getAttribute('aria-valuenow'),
        ),
      { timeout: 15000 },
    )
    .toBeCloseTo(80.1);
  await expect(page.locator('.globe canvas')).toBeVisible({ timeout: 15000 });
  await expect.poll(() => Boolean(originalSocket)).toBe(true);
  const follow = page.getByRole('button', { name: 'Follow selected satellite', exact: true });
  await follow.click();
  const oldControlRequest = page.waitForRequest('**/v1/runs/test-run/control');
  await page.getByRole('button', { name: '5×', exact: true }).click();
  await oldControlRequest;
  originalSocket!.send(
    JSON.stringify({
      visual_schema_version: 'visual.v1',
      type: 'error',
      run_id: original.run_id,
      message: 'Prepared mission changed. Reconnect to continue.',
    }),
  );
  reconnecting = true;
  await page.getByRole('button', { name: 'Reconnect', exact: true }).click();
  await expect(page.getByText('Replacement METIS-01', { exact: true })).toBeVisible();
  await expect(page.locator('.mode-row')).toContainText('Awaiting measurements');
  await expect(page.locator('.mission-clock strong')).toContainText('00:00:20');
  const start = page.getByRole('button', { name: 'Start simulation', exact: true });
  await expect(start).toBeDisabled();
  await expect(follow).toHaveAttribute('aria-pressed', 'false');

  const delayedAcknowledgement = page.waitForResponse('**/v1/runs/test-run/control');
  releaseOldControl();
  await (await delayedAcknowledgement).finished();
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );
  expect(oldSnapshots).toBe(1);
  await expect(page.getByText('Replacement METIS-01', { exact: true })).toBeVisible();
  await expect(page.locator('.mode-row')).toContainText('Awaiting measurements');
  await expect(start).toBeDisabled();

  releaseNewSnapshot();
  await expect.poll(() => Boolean(replacementSocket)).toBe(true);
  await expect(start).toBeEnabled();
  const firstSamples = [1, 2, 3].map((satellite) => {
    const frame = frameAt(0, satellite);
    return {
      ...frame,
      stream_id: `replacement-${frame.stream_id}`,
      observed_at: replacement.epoch_utc,
      channels: {
        ...frame.channels,
        'orbit.position_itrf_m': { value: [-1100000, 6400000, 2500000], quality: 'valid' },
        'orbit.altitude_m': { value: 825400, quality: 'valid' },
        'eps.battery_soc': { value: 0.35, quality: 'valid' },
      },
    };
  });
  replacementSocket!.send(
    JSON.stringify({
      visual_schema_version: 'visual.v1',
      type: 'samples',
      run_id: replacement.run_id,
      status: {
        ...replacement,
        status: 'paused',
        status_revision: 2,
        committed_tick: 0,
        committed_at: replacement.epoch_utc,
        frame_count: 3,
      },
      frames: firstSamples,
    }),
  );
  await expect(page.getByRole('meter', { name: 'Battery state of charge' })).toHaveAttribute(
    'aria-valuenow',
    '35',
  );
  await expect(page.locator('.sample-stamp')).toContainText('Sample 00:00:20 UTC');
  await expect(page.locator('.globe')).toHaveAttribute('data-simulation-seconds', '0');
  await expect(page.locator('.run-state')).toHaveText('paused');
  await expect(page.getByText('825.4', { exact: false }).first()).toBeVisible();
});
