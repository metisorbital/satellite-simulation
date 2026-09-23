import { writeFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import assert from 'node:assert/strict';
import { chromium } from '@playwright/test';

const baseURL = process.env.METIS_VIEWER_URL ?? 'http://127.0.0.1:8000';
const artifactDirectory = process.env.METIS_ARTIFACT_DIRECTORY ?? 'artifacts';
const requiredSatelliteCount = Number(process.env.METIS_EXPECTED_SATELLITES ?? 0);
assert(Number.isInteger(requiredSatelliteCount) && requiredSatelliteCount >= 0);
const viewport = { width: 1400, height: 950 };
const browser = await chromium.launch({
  channel: 'chromium',
  args:
    process.env.METIS_SOFTWARE_RENDERER === '1'
      ? ['--use-gl=angle', '--use-angle=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist']
      : [],
});
const page = await browser.newPage({ viewport });
const errors = [];
const externalRequests = [];
const failedRequests = [];
page.on('pageerror', (error) => errors.push(error.message));
page.on('request', (request) => {
  if (/^https?:/.test(request.url()) && new URL(request.url()).origin !== new URL(baseURL).origin)
    externalRequests.push(request.url());
});
page.on('websocket', (socket) => {
  if (new URL(socket.url()).host !== new URL(baseURL).host) externalRequests.push(socket.url());
});
page.on('response', (response) => {
  if (response.status() >= 400)
    failedRequests.push({ url: response.url(), status: response.status() });
});
page.on('requestfailed', (request) => {
  failedRequests.push({ url: request.url(), error: request.failure()?.errorText });
});
let started = false;
try {
  const bootstrapResponse = page.waitForResponse((response) =>
    response.url().endsWith('/v1/viewer/bootstrap'),
  );
  await page.goto(baseURL);
  const { run } = await (await bootstrapResponse).json();
  const expectedIds = run.satellites.map((satellite) => satellite.satellite_id).sort();
  if (requiredSatelliteCount) assert.equal(expectedIds.length, requiredSatelliteCount);
  if (['completed', 'stopped', 'failed', 'aborted'].includes(run.status)) {
    throw new Error(
      `The prepared demo is ${run.status}; prepare a runnable mission before measuring.`,
    );
  }
  await page.locator('.globe canvas').waitFor({ state: 'visible', timeout: 30000 });
  const renderer = await page.evaluate(() => {
    const canvas = document.querySelector('.globe canvas');
    const gl = canvas?.getContext('webgl2');
    const debug = gl?.getExtension('WEBGL_debug_renderer_info');
    return {
      webgl: gl?.getParameter(gl.VERSION) ?? null,
      renderer: debug
        ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL)
        : gl?.getParameter(gl.RENDERER),
      vendor: debug ? gl.getParameter(debug.UNMASKED_VENDOR_WEBGL) : gl?.getParameter(gl.VENDOR),
    };
  });
  const selectSatellite = async (id) => {
    await page
      .locator('.satellite-row')
      .filter({ has: page.getByText(id, { exact: true }) })
      .click();
    await page.getByRole('heading', { name: id, exact: true }).waitFor();
  };
  const selectedId = run.satellites[1]?.satellite_id ?? run.satellites[0].satellite_id;
  const listedIds = (await page.locator('.satellite-row-top strong').allTextContents()).sort();
  assert.deepEqual(listedIds, expectedIds);
  await selectSatellite(selectedId);
  await page.getByRole('button', { name: '20×', exact: true }).click();
  const resume = page.getByRole('button', { name: 'Resume simulation', exact: true });
  const start = page.getByRole('button', { name: 'Start simulation', exact: true });
  if (await resume.count()) await resume.click();
  else if (await start.count()) await start.click();
  await page.getByRole('button', { name: 'Pause simulation', exact: true }).waitFor();
  started = true;
  await page.waitForFunction(
    (expectedIds) => {
      const diagnostic = document.querySelector('.scene-fps');
      const positioned = diagnostic?.getAttribute('data-positioned-spacecraft')?.split(',') ?? [];
      return (
        Number(diagnostic?.getAttribute('data-fps')) > 0 &&
        positioned.length === expectedIds.length &&
        expectedIds.every((id) => positioned.includes(id))
      );
    },
    expectedIds,
    { timeout: 30000 },
  );
  await page.waitForTimeout(2000);
  const cadence = await page.evaluate(
    ({ epoch, expectedIds }) =>
      new Promise((resolve) => {
        const timestamps = [];
        const lags = [];
        const sceneWindows = new Map();
        let missingReadings = 0;
        let staleReadings = 0;
        const start = performance.now();
        function observe(now) {
          timestamps.push(now);
          const seconds = Number(
            document.querySelector('.globe')?.getAttribute('data-simulation-seconds'),
          );
          const observed = document
            .querySelector('.sample-stamp')
            ?.getAttribute('data-observed-at');
          if (Number.isFinite(seconds) && observed)
            lags.push(seconds - (Date.parse(observed) - Date.parse(epoch)) / 1000);
          else missingReadings++;
          if (document.querySelector('.stream-indicator.stale')) staleReadings++;
          const sceneRate = document.querySelector('.scene-fps');
          const observedAt = Number(sceneRate?.getAttribute('data-observed-at'));
          if (Number.isFinite(observedAt) && observedAt >= start && !sceneWindows.has(observedAt)) {
            const fps = sceneRate?.getAttribute('data-fps');
            sceneWindows.set(observedAt, {
              observed_at_ms: observedAt,
              frames: Number(sceneRate?.getAttribute('data-frames')),
              window_ms: Number(sceneRate?.getAttribute('data-window-ms')),
              fps: fps == null ? null : Number(fps),
              positioned_spacecraft:
                sceneRate?.getAttribute('data-positioned-spacecraft')?.split(',').filter(Boolean) ??
                [],
            });
          }
          if (now - start < 15000) {
            requestAnimationFrame(observe);
            return;
          }
          const intervals = timestamps
            .slice(1)
            .map((value, index) => value - timestamps[index])
            .sort((a, b) => a - b);
          const elapsed = timestamps.at(-1) - timestamps[0];
          const percentile = (fraction) => intervals[Math.floor((intervals.length - 1) * fraction)];
          const windows = [...sceneWindows.values()];
          const available = windows.filter(
            (window) => window.fps !== null && Number.isFinite(window.fps),
          );
          const renderedFrames = windows.reduce((total, window) => total + window.frames, 0);
          const renderWindowMs = windows.reduce((total, window) => total + window.window_ms, 0);
          resolve({
            measurement:
              'browser requestAnimationFrame cadence; not direct GPU or Cesium postRender throughput',
            elapsed_ms: elapsed,
            callbacks: timestamps.length,
            frames_per_second: (timestamps.length - 1) / (elapsed / 1000),
            median_interval_ms: percentile(0.5),
            p95_interval_ms: percentile(0.95),
            max_interval_ms: intervals.at(-1),
            intervals_over_50ms: intervals.filter((interval) => interval > 50).length,
            sample_lag_min_s: Math.min(...lags),
            sample_lag_max_s: Math.max(...lags),
            missing_measurement_callbacks: missingReadings,
            stale_callbacks: staleReadings,
            scene_rendering: {
              measurement:
                'Cesium scene.postRender callbacks, aggregated in wall-time windows of at least one second',
              sample_windows: windows.length,
              unavailable_windows: windows.length - available.length,
              complete_position_windows: windows.filter(
                (window) =>
                  window.positioned_spacecraft.length === expectedIds.length &&
                  expectedIds.every((id) => window.positioned_spacecraft.includes(id)),
              ).length,
              positioned_spacecraft_ids: [
                ...new Set(windows.flatMap((window) => window.positioned_spacecraft)),
              ].sort(),
              rendered_frames: renderedFrames,
              total_window_ms: renderWindowMs,
              frames_per_second:
                available.length && renderWindowMs > 0
                  ? (renderedFrames * 1000) / renderWindowMs
                  : null,
              minimum_window_fps: available.length
                ? Math.min(...available.map((window) => window.fps))
                : null,
              maximum_window_fps: available.length
                ? Math.max(...available.map((window) => window.fps))
                : null,
              windows,
            },
          });
        }
        requestAnimationFrame(observe);
      }),
    { epoch: run.epoch_utc, expectedIds },
  );
  await page.getByRole('button', { name: 'Pause simulation', exact: true }).click();
  await resume.waitFor();
  started = false;
  await page.waitForTimeout(500);
  const spacecraftReadings = [];
  for (const id of expectedIds) {
    await selectSatellite(id);
    const reading = await page.evaluate(() => {
      const observedAt = document.querySelector('.sample-stamp')?.getAttribute('data-observed-at');
      const seconds = document.querySelector('.globe')?.getAttribute('data-simulation-seconds');
      const soc = document.querySelector('[role="meter"]')?.getAttribute('aria-valuenow');
      return {
        observed_at: observedAt ?? null,
        display_seconds: seconds == null ? null : Number(seconds),
        battery_soc_percent: soc == null ? null : Number(soc),
      };
    });
    spacecraftReadings.push({
      satellite_id: id,
      ...reading,
      sample_lag_s:
        reading.observed_at && reading.display_seconds !== null
          ? reading.display_seconds -
            (Date.parse(reading.observed_at) - Date.parse(run.epoch_utc)) / 1000
          : null,
    });
  }
  await selectSatellite(selectedId);
  await mkdir(artifactDirectory, { recursive: true });
  await page.screenshot({ path: join(artifactDirectory, 'mission-control.png') });
  const checks = {
    scene_at_least_30_fps: cadence.scene_rendering.frames_per_second >= 30,
    positioned_every_spacecraft_in_every_window:
      cadence.scene_rendering.sample_windows > 0 &&
      cadence.scene_rendering.complete_position_windows === cadence.scene_rendering.sample_windows,
    scene_rate_available: cadence.scene_rendering.unavailable_windows === 0,
    active_sample_lag_within_one_second:
      cadence.sample_lag_min_s >= -1e-7 && cadence.sample_lag_max_s <= 1 + 1e-7,
    no_missing_measurements: cadence.missing_measurement_callbacks === 0,
    no_stale_callbacks: cadence.stale_callbacks === 0,
    every_selected_spacecraft_has_current_measurements: spacecraftReadings.every(
      (reading) =>
        reading.sample_lag_s !== null &&
        reading.sample_lag_s >= -1e-7 &&
        reading.sample_lag_s <= 1 + 1e-7 &&
        reading.battery_soc_percent !== null &&
        reading.battery_soc_percent >= 0 &&
        reading.battery_soc_percent <= 100,
    ),
    no_browser_errors: errors.length === 0,
    no_failed_requests: failedRequests.length === 0,
    local_runtime_only: externalRequests.length === 0,
  };
  const result = {
    recorded_at: new Date().toISOString(),
    browser: await browser.version(),
    mode: 'headless Chromium',
    platform: process.platform,
    architecture: process.arch,
    viewport,
    renderer,
    requested_speed: 20,
    satellite_count: run.satellites.length,
    satellite_inventory: listedIds,
    run_id: run.run_id,
    duration_s: run.duration_s,
    spacecraft_readings_after_pause: spacecraftReadings,
    cadence,
    checks,
    errors,
    failed_requests: failedRequests,
    external_requests: externalRequests,
    final_clock: await page.locator('.mission-clock').textContent(),
    final_sample: await page.locator('.sample-stamp').textContent(),
    final_state: await page.locator('.run-state').textContent(),
  };
  await writeFile(
    join(artifactDirectory, 'browser-performance.json'),
    JSON.stringify(result, null, 2) + '\n',
  );
  console.log(JSON.stringify(result, null, 2));
  assert(
    Object.values(checks).every(Boolean),
    'One or more browser acceptance checks failed; inspect the recorded artifact.',
  );
} finally {
  if (started)
    await page
      .getByRole('button', { name: 'Pause simulation', exact: true })
      .click()
      .catch(() => {});
  await browser.close();
}
