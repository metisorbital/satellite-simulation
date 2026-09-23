# Flutter mission viewer

Flutter owns the mission controls, state, transport, telemetry and charts. A narrow
`HtmlElementView` bridge embeds locally bundled CesiumJS for the globe. It receives
only backend Cartesian samples, orbit previews and Flutter's committed playback
clock; it never computes orbital dynamics or future electrical health.

```sh
npm ci
npm run prepare:cesium
flutter pub get
flutter analyze
flutter test
flutter build web --no-web-resources-cdn
```

Serve `build/web` behind the same-origin proxy as `/v1` (see the root Compose stack).
Direct `flutter run -d chrome` does not proxy backend routes. The production build
bundles CanvasKit and Cesium, with no CDN or Cesium Ion dependency.

`lib/api/generated.dart` is generated from Python models by
`uv run python scripts/generate_contracts.py` from the repository root. Do not edit
it manually. Public Python API reference is generated from NumPy-style docstrings
in the Zensical docs; Dart comments use native Dart `///` documentation.

Playback holds at most 41 frames for interpolation and 600 history frames per
spacecraft. All spacecraft share one bounded committed clock. The view freezes
when disconnected or when no advancing commit arrives for 1.5 seconds. Pause and
stop drain to the acknowledged snapshot. Reconnection refreshes a snapshot before
resuming the stream; session expiry requires explicit reconnect.

`web/globe.js` only owns Cesium lifecycle, Hermite interpolation of supplied
positions and velocities, camera controls and picking. Extrapolation is disabled.
Prediction polylines are explicitly labelled and contain orbit-only backend data.

Browser smoke tests use Playwright and the built Flutter semantics tree. Run
`npm run test:e2e` after building. Native mobile/desktop renderers are not provided.
