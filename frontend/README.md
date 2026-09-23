# Metis Orbital viewer

A React/TypeScript mission interface with a CesiumJS Earth scene. The Python backend owns all orbital, environmental, and electrical calculations. The browser presents committed measurements and an explicitly labelled orbit-only preview.

## Run locally

Start the repository's backend on `127.0.0.1:8000`, then:

```sh
npm ci
npm run dev
```

Open <http://127.0.0.1:5173>. Vite proxies `/v1` and `/health` to the backend, including the visual WebSocket. The bootstrap endpoint prepares the scoped HttpOnly viewer session; the control client sends the supplied CSRF token and a fresh idempotency key.

`npm run build` creates `dist/`, which the backend can serve at the same origin. Cesium workers and assets are copied from the locked dependency into `dist/cesium/`. Earth imagery and the decorative starfield are bundled under `public/assets/`; no external runtime network service, imagery provider, ion token, or web font is required. Attribution and third-party licenses accompany those assets.

## Presentation boundaries

- `src/api/useMission.ts` owns bootstrap, reconnect, bounded snapshot resynchronization, and command acknowledgement.
- `src/scene/playback.ts` owns committed-time clamping, freshness, nearest prior measurement selection, and bounded history. Each satellite retains 41 interpolation samples and at most 600 chart samples. Unknown or unavailable measurements remain unavailable.
- `src/scene/Globe.tsx` uses backend ITRS positions and velocities in Cesium's `FIXED` frame, cubic Hermite interpolation, and no extrapolation. Its clock is updated in the same React commit as the textual readings. Pausing drains to the acknowledged committed endpoint.
- `src/api/generated.ts` is generated from the backend's serialization schemas. Do not edit it by hand.

The initial image uses an Earth-fixed camera. Drag to rotate, scroll to zoom, or use the labelled camera buttons. The satellite list and telemetry panels remain usable with a keyboard and when WebGL is unavailable. Power values retain their actual sample timestamp and interval-mean semantics. Lighting is an explicitly approximate visual aid; the backend owns eclipse and power values.

## Validation

```sh
npm run build
npm test
npx playwright install chromium
npm run test:e2e
npm run format:check
```

The focused tests cover stale freeze, committed sample bounds, a shared spacecraft time bracket, pause acknowledgement, sequence deduplication, bounded buffers, snapshot races, quality handling, and fixed-frame Hermite interpolation. Browser tests check rendering, local-only runtime requests, controls/CSRF/idempotency headers, stale behavior, and keyboard selection in a compact viewport. Their fixtures exist only in `tests/`; the application never substitutes demonstration data for the backend.

Cesium is loaded as a separate lazy bundle (approximately 4.1 MB before compression); the mission interface loads independently. Real browser frame rate depends on the graphics hardware and is a separate measured acceptance gate.
