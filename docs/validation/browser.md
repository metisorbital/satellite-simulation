# Browser validation

The final ten-spacecraft machine-readable evidence is retained in [browser-ten.json](browser-ten.json).

The production viewer was exercised against local Python/PostgreSQL services on 2026-09-23 (Asia/Yerevan), using the compiled application served at `http://127.0.0.1:8000` for three spacecraft and isolated port `8002` for ten spacecraft.

## Environment and scope

- MacBook Pro, Apple M3 Pro, 11 CPU cores, 18 GB memory; macOS arm64.
- Desktop viewport: 1400 × 950 CSS pixels. Browser fixtures also cover 1536 × 1024 and a compact 760 × 1024 viewport.
- CesiumJS 1.145.0, React 19.3.0, Vite 8.3.0; exact dependencies and transitive packages are locked in `frontend/package-lock.json`.
- Earth texture, decorative starfield, Cesium workers, and supporting assets are local. The runtime does not configure ion, online map imagery, a terrain provider, or external fonts.

## Functional evidence

Live checks exercised start, pause, resume, 5× and 20× speed selection, spacecraft selection, follow, and reset-to-Earth. A pause at tick 100 displayed `00:01:40` simulation UTC and a selected measurement timestamp of `00:01:40` UTC. The final screenshot has no viewport clipping; the status bar occupies y=919–950 in the 1400 × 950 viewport.

The live browser reported zero JavaScript page errors and zero external HTTP(S) requests. The orbit preview and power readings came from the backend; browser-test fixtures are confined to `frontend/tests/` and are never used by the application.

The renderer uses `ReferenceFrame.FIXED`, one supplied velocity derivative, cubic Hermite interpolation, and disabled extrapolation. The scene clock and the textual readings commit in the same React update. Both the JS sample buffer and Cesium's internal sampled-position store are pruned. Pausing fetches the acknowledged endpoint before freezing. Reconnect snapshots explicitly request 41 frames per spacecraft.

Root module review identified and corrected integration defects: same-tick lifecycle/speed response races now compare `status_revision`; snapshot resynchronization now requests its complete bounded history; and the client surfaces the API's normative `message` error field. Overlapping bootstrap requests share their in-flight session response so cookies and CSRF tokens remain paired.

Reconnects also isolate missions that reuse spacecraft IDs. A run change clears Cesium entities, position properties, paths, and tracking before the next paint; trajectory responses must match the active run. Responses from prior connection generations cannot restore old telemetry, errors, or control state. A real Cesium unit regression verifies sample-store clearing. A browser regression reconnects to a new epoch with reused IDs and no initial frames, releases a delayed old control response, verifies the new controls remain busy until their own snapshot arrives, then checks the replacement measurements and follow reset.

## Reproduction

From `frontend/`:

```sh
npm ci
npm run build
npm test
npx playwright install chromium
npm run test:e2e
npm run format:check
node scripts/measure-viewer.mjs
```

The focused suite has 17 passing tests across clock/measurement/transport semantics, real Cesium interpolation against independent orbital reference data, run isolation, and scene render counting. The four compiled-browser tests pass for the local-only scene, control headers, selection, pause timestamp agreement, stale freeze, model information, compact keyboard navigation, unavailable frame-rate reporting when WebGL cannot initialize, and reconnecting reused spacecraft IDs. Browser startup assertions allow 15 seconds for cold SwiftShader initialization; the first browser check also requires observed Cesium scene renders. The final command requires a runnable prepared mission, selects 20×, measures an active browser interval, and leaves the mission paused. Set `METIS_VIEWER_URL` to use another local endpoint or `METIS_SOFTWARE_RENDERER=1` to explicitly measure SwiftShader instead of the default renderer.

Machine-readable measurements and a screenshot are written to `frontend/artifacts/browser-performance.json` and `frontend/artifacts/mission-control.png`. The original three-spacecraft evidence is also preserved under `frontend/artifacts/three-spacecraft/`. Set `METIS_ARTIFACT_DIRECTORY` to keep another measurement separate. These generated local artifacts are ignored by Git.

## Performance limits

The active three-spacecraft mission was measured at requested 20× for 15.0162 wall seconds, after a two-second warmup. The measurement completed at `2026-09-22T21:33:27.683Z` (2026-09-23 in Asia/Yerevan). Chromium `153.0.8010.12` used WebGL 2 through `ANGLE Metal Renderer: Apple M3 Pro` in headless mode, with the 1400 × 950 viewport and a stationary Earth-fixed camera.

| Observation | Result |
|---|---:|
| Cesium completed scene renders | 900 |
| Cesium render windows / total window duration | 10 / 14.9981 s |
| Cesium weighted scene frame rate | 60.01 FPS |
| Minimum / maximum scene window frame rate | 59.88 / 60.07 FPS |
| Unavailable scene windows | 0 |
| Browser animation callbacks | 902 |
| Browser animation cadence | 60.00 callbacks/s |
| Median / p95 callback interval | 16.70 / 16.80 ms |
| Maximum callback interval | 16.80 ms |
| Callback intervals over 50 ms | 0 |
| Display time minus selected sample time | 0.002425–0.997302 simulated seconds |
| Missing selected-measurement callbacks | 0 |
| Stale callbacks | 0 |
| JavaScript page errors | 0 |
| External HTTP(S) or WebSocket requests | 0 |

The mission was paused after measurement at tick 647. Both the simulation UTC and selected sample timestamp read `00:10:47` UTC. Actual Cesium scene rendering exceeded the specification's 30 FPS target on this hardware for this three-spacecraft observation.

The production footer reports completed `scene.postRender` callbacks per elapsed wall second. Its accessible title also lists the spacecraft whose Cesium entities have a resolved position at the current scene time. These are positioned spacecraft; Earth can correctly occlude some markers. The counter uses constant memory, publishes no more than once per second, and clears its timer and listener when the viewer is destroyed. Initial, failed, and empty render windows report `Scene unavailable`; no fallback frame rate is invented. The measurement script reads this same visible diagnostic and records its complete windows separately from browser `requestAnimationFrame` cadence. Because whole scene windows ending during the observation are used, their combined duration differs slightly from the RAF observation interval. A Cesium post-render callback measures completed scene render submission, not independently timed GPU presentation.

## Ten-spacecraft browser method

The isolated capacity-tier browser configuration is `.local/browser-ten.yaml`, derived from `configs/healthy-matched.yaml`. It uses a 1200-second duration, requested 20× speed, the same healthy spacecraft profile, no operations or fault scenarios, and ten unique IDs `METIS-01` through `METIS-10` at true anomalies 0°, 36°, …, 324°. The service binds only `127.0.0.1:8002` and uses the separate migrated `metis_browser` database. Existing local runtime role values are loaded without printing them.

After the isolated service is ready and other build/test workloads have finished, run from `frontend/`:

```sh
METIS_VIEWER_URL=http://127.0.0.1:8002 METIS_EXPECTED_SATELLITES=10 METIS_ARTIFACT_DIRECTORY=artifacts/ten-spacecraft node scripts/measure-viewer.mjs
```

This command requires all ten configured IDs in every sampled scene-position window and at least 30 actual scene frames per second. It also verifies active selected-sample lag, inspects every spacecraft's measurements after pausing, and rejects missing/stale samples, browser/network errors, and external requests. The resulting JSON and screenshot remain separate from the original three-spacecraft evidence.

### Ten-spacecraft result

The native browser check completed at `2026-09-22T22:13:26.536Z`, after the final backend source freeze, production build, and container checks. Other build/test workloads had stopped before measurement. The same Chromium `153.0.8010.12`, Apple M3 Pro ANGLE Metal renderer, 1400 × 950 viewport, and stationary Earth-fixed camera were used. Run `47f973b5-89bd-41ac-9a64-da29410c47ab` remained at requested 20× throughout the active observation.

| Observation | Result |
|---|---:|
| Configured / listed / positioned spacecraft | 10 / 10 / 10 |
| Complete position windows | 10 of 10 |
| Cesium completed scene renders | 901 |
| Cesium render windows / total window duration | 10 / 15.0014 s |
| Cesium weighted scene frame rate | 60.06 FPS |
| Minimum / maximum scene window frame rate | 59.91 / 60.90 FPS |
| Unavailable scene windows | 0 |
| Browser animation callbacks / observation duration | 902 / 15.0161 s |
| Browser animation cadence | 60.00 callbacks/s |
| Median / p95 / maximum callback interval | 16.70 / 16.70 / 16.80 ms |
| Callback intervals over 50 ms | 0 |
| Active display time minus selected sample time | 0–0.998454 simulated seconds |
| Missing selected-measurement / stale callbacks | 0 / 0 |
| JavaScript errors / failed requests / external requests | 0 / 0 / 0 |
| Individually selected spacecraft with current paused readings | 10 of 10 |

All ten IDs, `METIS-01` through `METIS-10`, had resolved Cesium positions in every recorded scene window. After pausing at tick 347, each spacecraft's measurement timestamp matched displayed UTC `00:05:47` with zero sample lag. Every automated browser acceptance check passed. The measurement process closed Chromium, and the isolated service then shut down cleanly with exit code 0; no listener remained on port 8002. Its isolated database and configuration were retained for reproduction.

Detailed evidence is in `frontend/artifacts/ten-spacecraft/browser-performance.json` and `frontend/artifacts/ten-spacecraft/mission-control.png`. The original three-spacecraft artifacts remain preserved independently.

The frontend is split into an approximately 260 KB raw interface bundle and a 4.14 MB raw lazy Cesium bundle; the complete prepared distribution is approximately 14 MB. Cesium's bundle-size warning remains visible during builds. These sizes describe the built artifact, not network-transfer or cold-start guarantees.

The measurement script records both Cesium scene render rate and browser callback cadence, renderer identity, sample age, errors, and external requests. These short three- and ten-spacecraft browser observations establish the 30 FPS target on this graphics hardware during the measured intervals. They do not establish the separate ten-wall-minute backend throughput gate or performance on other graphics hardware. Cold initialization, camera interaction, and software rendering are outside the native-renderer performance observations.
