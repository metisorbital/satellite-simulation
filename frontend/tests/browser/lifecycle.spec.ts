import { expect, test, type Page, type WebSocketRoute } from '@playwright/test';
import { frameAt, framesBetween, statusAt } from '../fixtures';

async function pausedMission(page: Page): Promise<void> {
  const status = statusAt(40, 'paused');
  await page.route('**/v1/viewer/bootstrap', route =>
    route.fulfill({ json: { csrf_token: 'test-csrf', allowed_actions: ['start', 'pause', 'resume', 'set_speed', 'stop'], run: status } }));
  await page.route('**/v1/runs/test-run/snapshot?history=41', route =>
    route.fulfill({ json: { status, frames: framesBetween(0, 40) } }));
  await page.route('**/v1/runs/test-run/trajectory?*', route => route.fulfill({
    json: { run_id: 'test-run', frame: 'ITRS', kind: 'predicted_orbit', satellites: [] },
  }));
  await page.routeWebSocket('**/v1/runs/test-run/visual', () => {});
}

test('late control acknowledgement cannot restore the replaced mission', async ({ page }) => {
  const original = statusAt(40, 'paused');
  const replacement = {
    ...statusAt(-1, 'created', 1), run_id: 'replacement-run',
    epoch_utc: '2026-09-21T00:00:20Z', committed_at: null,
    satellites: original.satellites.map((satellite: Record<string, any>) => ({
      ...satellite, stream_id: `replacement-${satellite.stream_id}`,
      name: `Replacement ${satellite.satellite_id}`,
    })),
  };
  let reconnecting = false, oldSnapshots = 0;
  let originalSocket: WebSocketRoute | undefined, replacementSocket: WebSocketRoute | undefined;
  let releaseControl!: () => void, releaseSnapshot!: () => void;
  const controlGate = new Promise<void>(resolve => { releaseControl = resolve; });
  const snapshotGate = new Promise<void>(resolve => { releaseSnapshot = resolve; });
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/v1/viewer/bootstrap', route => route.fulfill({
    json: { csrf_token: reconnecting ? 'replacement-csrf' : 'test-csrf', allowed_actions: ['start', 'pause', 'resume', 'set_speed', 'stop'], run: reconnecting ? replacement : original },
  }));
  await page.route('**/v1/runs/test-run/snapshot?history=41', route => {
    oldSnapshots++;
    return route.fulfill({ json: { status: original, frames: framesBetween(0, 40) } });
  });
  await page.route('**/v1/runs/replacement-run/snapshot?history=41', async route => {
    await snapshotGate;
    await route.fulfill({ json: { status: replacement, frames: [] } });
  });
  await page.route('**/trajectory?*', route => route.fulfill({ json: {
    run_id: route.request().url().includes('replacement-run') ? replacement.run_id : original.run_id,
    frame: 'ITRS', kind: 'predicted_orbit', satellites: [],
  } }));
  await page.route('**/v1/runs/test-run/control', async route => {
    await controlGate;
    await route.fulfill({ json: { ...original, requested_speed: 5, status_revision: 42 } });
  });
  await page.routeWebSocket('**/v1/runs/test-run/visual', socket => { originalSocket = socket; });
  await page.routeWebSocket('**/v1/runs/replacement-run/visual', socket => { replacementSocket = socket; });
  try {
    await page.goto('/');
    await expect(page.getByText(/322\.4 W/)).toBeVisible();
    await expect.poll(() => Boolean(originalSocket)).toBe(true);
    const controlRequest = page.waitForRequest('**/v1/runs/test-run/control');
    await page.getByRole('checkbox', { name: '5×', exact: true }).click();
    await controlRequest;
    originalSocket!.send(JSON.stringify({
      visual_schema_version: 'visual.v1', type: 'error', run_id: original.run_id,
      sent_at: new Date().toISOString(), status: null, frames: [], ranges: [],
      message: 'Prepared mission changed. Reconnect to continue.',
    }));
    reconnecting = true;
    await page.getByRole('button', { name: 'Reconnect', exact: true }).click();
    await expect(page.getByText(/Replacement METIS\-01/)).toBeVisible();
    await expect(page.getByText(/Awaiting measurements/)).toBeVisible();
    await expect(page.getByText(/322\.4 W/)).toHaveCount(0);
    const delayedResponse = page.waitForResponse('**/v1/runs/test-run/control');
    releaseControl();
    await (await delayedResponse).finished();
    // Let the Dart fetch future and ChangeNotifier frame finish after the HTTP response.
    await page.waitForTimeout(250);
    expect(oldSnapshots).toBe(1);
    await expect(page.getByText(/Replacement METIS\-01/)).toBeVisible();
    await expect(page.getByText(/Awaiting measurements/)).toBeVisible();
    await expect(page.getByRole('button', { name: 'Applying…', exact: true })).toBeDisabled();
    releaseSnapshot();
    await expect.poll(() => Boolean(replacementSocket)).toBe(true);
    await expect(page.getByRole('button', { name: 'Start run', exact: true })).toBeEnabled();
    replacementSocket!.send(JSON.stringify({
      visual_schema_version: 'visual.v1', type: 'samples', run_id: replacement.run_id,
      sent_at: new Date().toISOString(), ranges: [], message: null,
      status: { ...replacement, status: 'paused', status_revision: 2, committed_tick: 0,
        committed_at: replacement.epoch_utc, frame_count: 3 },
      frames: [1, 2, 3].map(satellite => {
        const frame = frameAt(0, satellite);
        return { ...frame, stream_id: `replacement-${frame.stream_id}`, observed_at: replacement.epoch_utc,
          channels: { ...frame.channels, 'eps.battery_soc': { value: 0.35, quality: 'valid' },
            'orbit.altitude_m': { value: 825400, quality: 'valid' } } };
      }),
    }));
    await expect(page.getByText(/35\.0%/)).toBeVisible();
    await expect(page.getByText(/825\.4 km/)).toBeVisible();
    await expect(page.getByText(/T\+ 0.0 s/)).toBeVisible();
    expect(errors).toEqual([]);
  } finally {
    releaseControl();
    releaseSnapshot();
  }
});

test('Cesium WebGL failure retains the Flutter telemetry and controls', async ({ page }) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (this: HTMLCanvasElement, type: string, ...args: unknown[]) {
      // Flutter CanvasKit also uses WebGL. Fail only the Cesium platform view.
      if (this.closest('#metis-earth') && ['webgl', 'webgl2', 'experimental-webgl'].includes(type)) return null;
      return Reflect.apply(original, this, [type, ...args]);
    } as typeof original;
  });
  await pausedMission(page);
  await page.goto('/');
  await expect(page.getByRole('group', { name: /The 3D view needs WebGL 2/ })).toBeVisible();
  await expect(page.getByText(/322\.4 W/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Resume', exact: true })).toBeEnabled();
});
