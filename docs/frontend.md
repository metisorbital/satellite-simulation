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
uv run metis-sim demo --at 0
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

The viewer uses one sidebar and a 48-pixel status header.
Overview keeps the Earth view, spacecraft selection, and start/pause/speed
controls together, with a concise measured-state panel on wide screens.
Power history stays beneath the globe.
The operator menu and Settings live at the bottom of the sidebar.

Telemetry uses large two-column panels on wide screens and one column on
narrow screens. Dashboard focus hides the shell; individual panel expansion
uses the full content area without freezing measurements.
Constellation editing and spacecraft visibility belong to Settings.
Hiding spacecraft changes presentation only, including their orbit paths;
the backend keeps simulating every configured spacecraft.

The sidebar also opens Early warnings, Investigations, Mission planning, Case
history, and the full-page Shift Log. Private records require a named operator.
Submitted Shift Logs are shared with all named operators from the application's
database; unsubmitted drafts remain private to their current-run owner.
The unread badge calls `GET /v1/viewer/notifications` and acknowledges a visible
version through `POST /v1/viewer/notifications/read`.
Acknowledging an item only records that operator's view; it does not resolve a
warning or alter a case.
Warnings use committed measurement quality and present operating state;
investigations preserve public evidence and operator-authored recommendations,
decisions, and outcomes. Planning reads the configured operation windows and
reuses the constellation editor. See [Operator cases](reference/operator-cases.md)
for the complete workflow and its limits.

Use dark navy surfaces, fine panel borders, readable typography, and restrained
mint, blue, and gold accents. Color reinforces labels; it must never be the only
way to identify a spacecraft, a control state, or an illumination condition.
Keep controls and status readable without competing with the Earth view.
The original Metis mark is bundled locally, along with fonts and globe assets.

Present battery energy, state of charge, power allocation, illumination, and
position directly from committed backend samples. Mark the mission as synthetic
and distinguish orbit previews from measured telemetry. A flight-operations
appearance does not imply flight certification or additional simulated systems.
Do not add invented communications, attitude, thermal, or propulsion readings.

### Schedule Payload Operations

Stop the active run before changing the configuration. Open **Settings → Edit
constellation**, select an existing satellite or add one, then open **Payload
Tasks** and enable **Schedule payload operations**. Add one or more tasks and
set each task's whole simulated **Start time(s)** and **Duration(s)**; duration
defaults to 300 seconds. Enable **Repeat every orbit** for a recurring task.
Use the task controls to add or remove individual payload windows.

Disabling **Schedule payload operations** removes payload tasks only; nominal
and safe operations remain unchanged. The mode configured outside scheduled
windows applies between them. If that mode is `payload_active`, payload power
stays active continuously between windows. The satellite's **Power System**
payload-active load is the total spacecraft load for that mode and remains
editable per satellite.

Choose **Save as new run** to validate and create a new immutable run from the
edited constellation. If server validation rejects the configuration, the
editor keeps the draft so it can be corrected. The backend resolves orbit
recurrence and rejects overlapping windows, including overlaps created by later
cycles; the first declared window must fit within the run. The viewer does not
predict recurrence or replace backend schedule validation.

## Metis in the Overview

When the server has the Metis demo installed, the **Overview** (`lib/metis/metis_panels.dart`) shows it around the globe; there is no separate Metis tab. `MetisBar`, above the globe, shows the wildfire request, the simulated conditions and a **Metis OFF | ON** switch.
- **Off:** **Fly mission** flies the original schedule.
- **On:** **Fly mission** starts the run at T0 with "Metis watching". At +60 the run pauses by itself and the **Metis alert** appears: the proposal with **Approve and uplink** and **Dismiss**, and one folded **Metis forecast** section that opens both the solar supply and essential load charts (p10–p90 band) together. Nothing about the proposal shows before the alert.

Both Metis sections render text 15% larger than the rest of the Overview.

`MetisResults`, below the globe, shows the energy-margin chart (the active run, plus the other plan's latest run for comparison), the wildfire image panel, verdict cards and a task timeline that crosses out skipped tasks. The globe keeps a fixed height, and the whole Overview, including its run toolbar, scrolls. Metis is hidden for recorded replays and when `/v1/metis/briefing` returns 404.
The image panel reveals `assets/images/wildfire-camp-fire-landsat8.jpg` (NASA Earth Observatory, Landsat 8) as the downlink progresses, and only once telemetry shows the capture and the downlink done. It is credited as an illustrative product.

`MetisController`, owned by the mission shell, loads `/v1/metis/briefing` and calls `Mission.launchMissionRun`, which launches the plan's run and resumes it unless Metis holds it for its alert. Approving launches the Metis plan from the alert; dismissing resumes the held run. It then polls `/v1/metis/runs/{run_id}/outcome` once a second until the run completes. All values come from the Metis API; the view computes no physics.

The Overview's data-source line also shows `Conditions: …` when the run status carries `environment_source`.
See the [Metis demo guide](reference/metis-demo.md).

## Component Responsibilities

| Layer | Responsibility |
|---|---|
| `frontend/lib/` | Flutter widgets, API client, mission state, committed-time playback |
| `frontend/lib/api/generated.dart` | Public wire types generated from Python models |
| `frontend/lib/workflows/` | Private case forms, committed-signal review, and history |
| `frontend/lib/shift_log/` | Shared durable handover state and page/dialog presentations |
| `frontend/web/` | Browser entry point, local assets, and Cesium rendering bridge |
| `frontend/test/` | Dart behavior and widget tests |
| `frontend/tests/browser/` | Browser integration checks |

Python computes positions, power, eclipse, and orbit previews. The viewer may
interpolate committed position samples for display; it must not propagate an
orbit or extrapolate public telemetry beyond committed time. Predicted orbit
paths remain explicitly separate from measured state.

On opening the viewer, `GET /v1/viewer/session` restores the operator session.
If there is no session, the client selects `operator1` within the enabled
interactive demo and creates its run.
The sidebar switches among the three JSON-backed demo identities, `operator1`,
`operator2`, and `operator3`. Internally, `POST /v1/viewer/login` selects an
identity and obtains an HttpOnly run-scoped cookie. Its required nonempty demo
placeholder is neither verified nor stored.
Control requests carry the returned CSRF token and an idempotency key. Mission
replacement must clear prior samples and reject late responses for the old run.
Switching stops the current operator's active demo run, clears the cookie,
disposes mission streams and state, and creates a separate run for the selected operator.
The signed session restores the same operator and run on browser reload until expiry.
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
The [mock operator login validation](validation/operator-login.md) records the
subsequent identity, session-lifecycle, and private ownership checks.
