# Mission dashboard visual QA

Source visual truth: `frontend/artifacts/demo-ready.png` (original React dashboard).
Implementation: `http://127.0.0.1:8008/` (Flutter web).

## Comparison history

1. Original and pre-polish Flutter captures were opened together at 1400 × 950.
   The original is paused at 05:00:00, METIS-02 selected; the current local run is
   stopped at 00:25:09. Telemetry values and orbit geometry therefore differ and
   are not judged as visual defects. Baseline capture:
   `frontend/artifacts/flutter-before-polish.png`.
   - P1: Generic application header and cards lost the mission workspace hierarchy.
   - P1: Telemetry had no battery segmentation or power comparison bars.
   - P2: Globe skybox and large renderer branding competed with mission information.
   - P2: History lacked a current measurement, time labels, and a visual grid.
   These findings are addressed in the new Flutter layout and local globe styling.


## Final comparison and fixes

2. The rebuilt desktop was compared with the original in the same image input.
   The four baseline findings are resolved: the mission rail/sidebar and hierarchy
   are restored, battery and power have compact visual scales, the globe uses the
   original quiet star asset, and history includes its value, grid, and UTC range.
   A first rendered pass found the position values below the desktop fold and
   Unicode arrows displaying as boxed emoji. Reduced telemetry spacing and
   removed those text arrows; the final desktop capture shows position and sample
   provenance within the panel.
3. At 390 × 844 the initial fixed telemetry viewport showed only spacecraft
   identity. Replaced it with a vertically scrolling dashboard and a usable globe
   region. Scrolling now reaches battery, power, illumination, and position.
   A dark scrim under narrow-view metrics keeps moving globe labels from obscuring
   measurements. The final compact capture verifies the fix.
4. Physical dialog-close clicks exposed a Cesium click-through problem. Added
   bounded PointerInterceptor widgets for overlays and a route-sized interceptor
   only while the dialog is open. Repeated physical close and zoom clicks work;
   closing the dialog no longer opens Cesium attribution.

## Evidence and fidelity surfaces

- Desktop: `frontend/artifacts/flutter-polished-desktop.png`, 1400 × 950 pixels,
  CSS viewport 1400 × 950. Original: 1400 × 950 pixels. Browser viewport captures
  were compared without image rescaling; full-page captures were excluded because
  the in-app browser produced incorrect framing. The in-app capture softens fine
  text, so this is a composition/readability comparison, not pixel-identical
  antialiasing acceptance.
- Compact: `frontend/artifacts/flutter-polished-compact.png` and
  `frontend/artifacts/flutter-polished-compact-telemetry.png`, 390 × 844 pixels,
  CSS viewport 390 × 844. Also inspected the 1050 × 800 desktop breakpoint.
- Final state: local stopped run at 00:25:09, METIS-02 selected on desktop;
  compact final overview uses METIS-01. METIS-03 selection was checked separately
  and showed eclipse, zero solar generation, and battery discharge. Reference
  state differs as described above; no artificial telemetry was used to match it.
- Full-view comparison: source and final desktop images opened together.
- Focused comparison: `frontend/artifacts/reference-telemetry-crop.png` and
  `frontend/artifacts/flutter-telemetry-crop.png` opened together, both 286 × 750,
  cropped at x=1114, y=170 from the corresponding desktop captures.
- Typography: locally bundled MetisSans, distinct title/value/label hierarchy,
  readable units and compact labels. Flutter Material icons and typography are
  intentional adaptations rather than an exact React font/icon clone.
- Spacing: 66px rail, 238px mission sidebar, 286px telemetry panel, fine dividers,
  compact control bar and history; all desktop measurements fit at 950px height.
- Colors: navy surface layers, muted secondary labels, mint battery/history,
  gold solar power, spacecraft colors retained from backend descriptors.
- Assets: original Metis logo, Earth texture, and stars retained locally. The logo
  uses a 128px raster export of its existing SVG. Renderer attribution preserved.
- Content: synthetic mission, measured values, committed-state status, orbit
  preview labeling, approximation notice, and sample timestamp retained.

## Interaction and engineering checks

- Desktop and compact spacecraft selection; sunlit and eclipse readings.
- Battery/solar chart switching, physical zoom and reset, dialog open/close,
  compact dashboard scrolling, and reachable complete telemetry.
- Current run is stopped; disabled simulation controls are expected. This polish
  pass did not create or restart a run. The earlier migration evidence covers
  active controls, stale data, and replacement scenarios.
- Browser console: no errors observed. Network observation of a rebuilt reload
  and interactions: zero external HTTP(S) asset requests.
- Independent code review closed navigation, semantics, responsive spacing, and
  overlay-interception findings; backend physics/lifecycle boundaries preserved.
- Flutter analysis and release web build pass. Flutter playback tests: 10 pass.
  Cesium interpolation tests: 2 pass. Strict Zensical build and diff check pass.
- Browser integration selector updated to the unique page heading. The automated
  Playwright suite was not rerun in this visual-polish pass; browser interaction
  checks used the in-app browser instead.

## Remaining polish

No actionable P0/P1/P2 findings remain. P3: optional future optical tuning of
icons/number typography could bring Flutter even closer to the original; native
font rendering and current telemetry state are expected differences.

## Implementation checklist

- [x] Restore mission hierarchy and full telemetry presentation.
- [x] Retain actual backend data and functional controls.
- [x] Fix compact layout and overlay interaction findings.
- [x] Compare final desktop and focused telemetry views with the reference.
- [x] Record validation and remaining evidence limits.

final result: passed
