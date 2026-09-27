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
Warnings normally use committed measurement quality and present operating state.
A source-aligned saved model prediction is explicitly labeled as a prediction,
linked to its private operator case, and shown as critical only while its replay
is paused awaiting a decision.
Investigations preserve public evidence and operator-authored or server-recorded
recommendations, decisions, and outcomes.
Planning reads configured operation windows and reuses the constellation editor.
See [Operator cases](reference/operator-cases.md) and the
[recorded-mission review](reference/metis-demo.md) for workflow limits.

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

When the server has the recorded-mission review installed, the **Overview**
(`lib/metis/metis_panels.dart`) shows a compact summary of the saved BUPT-1
prediction for a source-aligned recorded replay. Selecting it opens the mission
details in **Missions**.
The standard **Start** control begins that replay.
The mission's persisted **Metis OFF / ON** control is available before Start or
while paused before the alert. Its timing hint shows the configured source UTC
and mission minute. OFF keeps the original schedule without a model review pause.
When replay is positioned outside the saved mission origin, the switches remain
visible but disabled. **Load wildfire mission** positions an idle BUPT-1 recording
at the saved T0; the operator then chooses OFF/ON and presses Start as usual.
Below the globe, the energy chart, task timeline, and split OFF/ON illustrative
delivery panels show the demo scenario. Missions shows preventive analysis and the proposed
shift only after the linked alert exists. The original plan misses ground image
delivery because its modeled admission gate blocks an unsustainable downlink
before transmission. Approving the saved shift preserves the T+90 capture and
T+100 downlink, with progressive image reception through T+103.
At its committed review tick, a critical model-prediction banner links directly
to the existing investigation workspace.

The banner has a concise saved-prediction label, a critical visual treatment,
and accessible **Review** and **Approve** actions. Direct approval reads the
latest case revision and submits the same durable case decision with the saved
proposal identity. A changed recommendation requires investigation review;
duplicate clicks are disabled and failed confirmation keeps the banner visible.
The proposed ON lane never claims execution before approval. The OFF comparison
and active ON lane share one committed replay clock and are labeled as demo projections.
Its sound is armed after the user starts or resumes the run, or selects the
banner's sound-enable control after restoring a page. Each displayed notification
version plays `assets/sound_effects/soundreality-code-red-185448.mp3` once at
50% gain. Dismissing or reviewing the banner, resolving the alert, or closing
the page stops playback. Closing the banner only hides that display; marking
the warning viewed records its per-operator receipt. Neither action approves
or changes the linked case.

`MetisController` reads `/v1/metis/briefing` and the recorded projection endpoint.
It persists the watch setting through `/v1/metis/preference`.
It does not launch replacement runs, calculate physics, alter telemetry, or call
Metis-specific approval endpoints.
The case workspace remains the only surface for recommendation revision and
approval, rejection, or revision decisions.

The saved prediction is unavailable for another source or replay origin.
The viewer then keeps ordinary recorded telemetry visible and explains the
source-alignment requirement.
See the [recorded-mission review](reference/metis-demo.md).

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
