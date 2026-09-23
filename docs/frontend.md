---
title: Flutter Mission Viewer
description: Build and maintain the Flutter web interface and its Cesium rendering adapter.
content-type: guide
audience: frontend contributors
---

# Flutter Mission Viewer

The mission viewer uses Flutter for layout, controls, selection, telemetry panels,
and browser session state. It targets the web and is served by FastAPI together
with the API. CesiumJS remains the globe renderer, embedded in a Flutter HTML
platform view through a small JavaScript bridge.

## Build and Run

Install Flutter 3.47.5, Node 22.23.0, and the Python prerequisites in
[Getting Started](getting-started.md). From the repository root:

```bash
npm ci --prefix frontend
npm --prefix frontend run prepare:cesium
cd frontend
flutter pub get --enforce-lockfile
flutter build web --release --no-web-resources-cdn
cd ..
uv run metis-sim demo --at 10
```

Open `http://127.0.0.1:8000`. FastAPI serves `frontend/build/web`.
Create local credentials and migrate PostgreSQL first if this is a new checkout.
Build before starting the backend: the static mount is added at application startup.
Rebuild after editing Dart or the globe bridge, then reload the browser.
The build packages Flutter's renderer and Cesium assets locally.
No Cesium Ion token is required.

The supported demo uses one browser origin for the static viewer, HTTP API, and
WebSocket. Opening an independent Flutter development server requires a suitable
same-origin reverse proxy; changing CORS alone does not reproduce the scoped
session-cookie behavior. Do not put operator bearer tokens in the frontend.

## Mission Dashboard Design

The dashboard follows a compact aerospace operations layout: constellation
selection at the left, Earth and orbit context in the center, and the selected
spacecraft's measured state at the right. Power history stays next to the globe
so users can connect an orbital position with its recent energy behavior.

Use dark navy surfaces, fine panel borders, compact typography, and restrained
mint, blue, and gold accents. Color reinforces labels; it must never be the only
way to identify a spacecraft, a control state, or an illumination condition.
Keep controls and status readable without competing with the Earth view.
The original Metis mark is bundled locally, along with fonts and globe assets.

Present battery energy, state of charge, power allocation, illumination, and
position directly from committed backend samples. Mark the mission as synthetic
and distinguish orbit previews from measured telemetry. A flight-operations
appearance does not imply flight certification or additional simulated systems.
Do not add invented communications, attitude, thermal, or propulsion readings.

## Component Responsibilities

| Layer | Responsibility |
|---|---|
| `frontend/lib/` | Flutter widgets, API client, mission state, committed-time playback |
| `frontend/lib/api/generated.dart` | Public wire types generated from Python models |
| `frontend/web/` | Browser entry point, local assets, and Cesium rendering bridge |
| `frontend/test/` | Dart behavior and widget tests |
| `frontend/tests/browser/` | Browser integration checks |

Python computes positions, power, eclipse, and orbit previews. The viewer may
interpolate committed position samples for display; it must not propagate an
orbit or extrapolate public telemetry beyond committed time. Predicted orbit
paths remain explicitly separate from measured state.

The API client obtains an HttpOnly run-scoped cookie through viewer bootstrap.
Control requests carry the returned CSRF token and an idempotency key. Mission
replacement must clear prior samples and reject late responses for the old run.
See [the contracts](contracts.md) for freshness, reconnect, and privacy rules.

Flutter's [HTML platform views](https://docs.flutter.dev/platform-integration/web/web-content-in-flutter)
embed the Cesium surface. JavaScript is limited to rendering and camera behavior;
Flutter owns application state. This browser adapter makes the shipped target
web-specific: native mobile and desktop builds need another globe adapter.

Flutter controls placed over the globe use
[`PointerInterceptor`](https://pub.dev/documentation/pointer_interceptor/latest/)
so camera buttons, dialogs, and selection menus receive clicks without passing
them to the underlying HTML platform view. Keep interception limited to overlays;
the unobstructed globe must still support dragging and zooming.

## Generate Contracts and Check Changes

```bash
uv run python scripts/generate_contracts.py
npm --prefix frontend test
cd frontend
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
flutter build web --release --no-web-resources-cdn
npx playwright install chromium
npm run test:e2e
cd ..
uv run zensical build --strict
```

Review generated contract changes with the Pydantic source changes. Dart uses
idiomatic `///` comments. Python uses NumPy-style docstrings, which Zensical renders
in the [Python API reference](python-api.md) on every build.

The earlier [browser measurements](validation/browser.md) describe the React
viewer before migration. They are historical evidence, not Flutter performance
results. See [Flutter migration validation](validation/flutter-migration.md) for
checks performed on the replacement.
