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

Playback holds at most 41 frames for interpolation. Telemetry retains the selected
spacecraft’s window plus 41 samples for playback lag; other spacecraft retain
600 history frames each. All spacecraft share one bounded committed clock. The view freezes
when disconnected or when no advancing commit arrives for 1.5 seconds. Pause and
stop drain to the acknowledged snapshot. Reconnection refreshes a snapshot before
resuming the stream; session expiry requires explicit reconnect.

`web/globe.js` only owns Cesium lifecycle, Hermite interpolation of supplied
positions and velocities, camera controls and picking. Extrapolation is disabled.
Prediction polylines are explicitly labelled and contain orbit-only backend data.

Browser smoke tests use Playwright and the built Flutter semantics tree. Run
`npm run test:e2e` after building. Native mobile/desktop renderers are not provided.

## Open the Telemetry Dashboard

After building the viewer and preparing PostgreSQL, launch the optional spacecraft
models from the repository root:

```sh
uv run metis-sim demo --config configs/telemetry-demo.yaml --at 0 --port 8002
```

Open `http://127.0.0.1:8002` as the default `operator1`, start the run, and
choose **Telemetry** in the sidebar (the chart icon on narrow screens).
Spacecraft selection and the committed simulation clock remain shared with
**Overview**. Start, pause/resume, speed, stop, and reset controls stay beside the
Earth view on Overview. The single sidebar places the operator switcher, Settings,
and Help at its bottom; **Shift log** opens the saved operator handover workflow.

Open **Settings** to hide spacecraft from both the Earth view and telemetry
selector, or to edit the constellation in a replacement run. Hidden spacecraft
continue simulating; at least one remains visible. Saving a new configuration
still requires stopping the active run.

Choose **Focus dashboard** to hide the app shell, or use a chart's expand icon
to fill the view with that live panel. **Close panel** restores the prior focus
state. Panels retain channel quality, committed sample times, units, and gaps.
The default `power-leo.v1` configuration also works, with only its available
catalog channels.

The fl_chart dashboard defaults to the last hour, with quick ranges from one
minute to 24 hours. The range picker accepts custom relative minutes or absolute
UTC start/end times, bounded by committed run history. Following live advances
the window with displayed telemetry; zooming, panning, or dragging across a chart
pins a historical range shared by all panels. Use zoom buttons, previous/next
half-window controls, Reset, or Follow live to navigate. Historical selection
does not seek or change simulation playback.

Selecting a spacecraft or range loads stored committed samples in bounded pages.
A 60-minute window includes 3601 samples at 1 Hz once that much history exists.
Loading and retry messages distinguish pending or failed history reads from real
gaps. Dense chart paths retain per-bucket extrema; hover inspection uses original
samples, showing UTC, value, unit, quality, and window min/max. Click legend
entries to toggle individual series. Invalid/missing readings remain gaps;
saturated samples use diamonds.

Use **Edit panels** to reorder or hide panels and select one, two, or three
columns. A panel's layout menu toggles full-row width and tall height. The grid
adapts to narrow screens. Layout preferences persist in this browser; they contain
no telemetry values or identity. **Reset defaults** and **Apply** restore the
current tab's default panel arrangement.

The first operator session or a switch may prepare a complete simulation. Session
creation allows up to three minutes for this preparation; ordinary API requests
retain their 20-second timeout.

The dashboard groups committed measurements into Overview, EPS, Flight computer,
Payload, ADCS, and Space weather. Channel search and the shared time range filter
committed history. Initial/reconnect snapshots contain up to 41 samples for
playback; telemetry separately refills the selected window from public replay.
The displayed sample UTC and actual coverage identify the data on screen.

Units, frames, sampling semantics, and availability come from the authenticated
public catalog. Missing and invalid readings are gaps; saturated readings retain
their quality label. Unsupported channels remain explicitly unavailable. The
41 modeled and 12 unavailable `spacecraft.v1` channels are synthetic model output,
not a replay or calibrated mapping of the 210 source-export fields. ADCS's ideal
attitude and the three thermal nodes retain their documented model limits.
See [spacecraft telemetry](../docs/reference/spacecraft-telemetry.md) and
[sample evidence](../docs/reference/sample-telemetry.md) for the source boundaries.
