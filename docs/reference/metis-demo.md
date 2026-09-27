---
title: Metis Wildfire Demo
description: Run the Metis demo, in which a wildfire image is lost with Metis off and delivered with Metis on.
content-type: guide
audience: presenters and developers
---

# Metis Wildfire Demo

The **Overview** tells one wildfire story twice, with a **Metis OFF | ON** switch above the globe.
- **The request:** a thermal capture at +90 and a downlink from +100 to +103, needed before a +120 briefing.
- **The risk:** a routine 16-minute compute batch at +70 drains the battery the downlink needs.
- **The rule:** the spacecraft starts a task only when its battery is above the protected reserve (50% charge). Otherwise it skips the task to keep its essential systems alive.

**Metis off:** the mission flies its original schedule. The battery enters the reserve at +99.5, so the spacecraft skips the +100 downlink. The image stays on board and misses the briefing.

**Metis on:** the run starts at T0 and Metis watches it quietly. At +60, ten minutes before the batch, the run pauses by itself and Metis raises an alert: its forecast (solar supply and essential load for 195 minutes, from models trained on BUPT-1 satellite telemetry, made at −15) says the batch will push the battery into the reserve during the downlink, so it proposes moving the batch to +122. The run holds at +60 until the operator decides.
- **Approve and uplink:** the mission continues from +60 on the Metis plan; the downlink runs and the wildfire image arrives at +103.
- **Dismiss:** the mission continues on the original schedule and the image is lost.

Metis does not re-forecast at +60; the alert uses the forecast made at −15.

Metis lives in `backend/src/metis_agent`, which never imports the simulator.
- **Before a run**, every Metis number on the Overview comes from Metis's saved decision.
- **During and after a run**, every number comes from the simulator's public telemetry and events.

## Run it

Use the local database. The remote Render database commits too slowly for demo playback: about 3.5× instead of 120×.

```sh
METIS_USE_REMOTE=0 uv run metis-sim migrate
METIS_USE_REMOTE=0 uv run metis-sim demo
```

Open `http://127.0.0.1:8000/`. The Metis bar is on the **Overview**, above the globe; the results (energy chart, wildfire image, verdicts and timeline) are below it. The Metis bar and, during a demo run, the data-source line name the simulated conditions: "BUPT-1 solar harvest, 21 June 2023 (scaled)". At start-up the server precomputes both plans' runs in the background (two `engine_warmed` log events), so each launch takes under 2 seconds.

## Present it (about 3 minutes)

| Time | On screen |
|---|---|
| 0:00 | **Metis OFF.** The request and the simulated conditions. Explain the rule: a task starts only above the protected reserve. Press **Fly mission**. The run starts at T0 and plays at 120× (one mission minute every half second), and the Overview scrolls to the results; the globe shows SAT-1 moving along its orbit. |
| 0:35 | **Energy chart.** The batch starts at +70 and drains the battery; it enters the reserve at +99.5, inside the eclipse. |
| 0:50 | **Image panel.** "Image not delivered": the downlink was due at +100 at 49.6% charge, below the 50% limit, so the spacecraft skipped it. The timeline crosses out the downlink. |
| 1:05 | **Metis ON.** Press **Fly mission**. The run starts at T0 with "Metis watching". |
| 1:35 | **Metis alert.** At +60 the run pauses by itself: "Move the routine compute batch from +70 to +122?" Unfold **Metis forecast** to show the solar and load charts with their shaded low-to-high band. Press **Approve and uplink**. |
| 1:55 | **Energy chart.** The Metis plan stays above the reserve, lowest +0.74 Wh at +115; the Metis-off run stays on the chart in faded amber. |
| 2:00 | **Image panel.** The wildfire image sweeps in during the downlink: "Delivered at +103, 17 minutes before the +120 briefing." The batch then runs from +122 to +138. |

To show the other ending, fly again with Metis on and press **Dismiss**. To rehearse from scratch, press **Reset rehearsal**; it clears the approval and both modes' runs.

Approvals and runs are kept per demo operator, so two browsers signed in as the same operator share them. Press **Reset rehearsal** before presenting.

## The image

The delivered image is `frontend/assets/images/wildfire-camp-fire-landsat8.jpg`. It is a resized copy of the NASA Earth Observatory image by Joshua Stevens, using Landsat 8 data from the U.S. Geological Survey: the Camp Fire in California on 8 November 2018 ([source](https://science.nasa.gov/earth/earth-observatory/camp-fire-rages-in-california-144225/)). NASA Earth Observatory images are free to reuse with credit.

It is an illustrative product. The simulator models energy and timing, not imaging. The simulated capture happens in eclipse, while this is a daytime scene of a different fire. The view shows the image only when telemetry shows both the capture and the downlink done, and it says so in the caption.

## How it fits together

1. `GET /v1/metis/briefing` returns:
   - the mission;
   - the forecast in mission watts: p10, p50 and p90, plus the cautious series Metis plans with and the nominal series;
   - the proposal, with margins forecast one minute apart;
   - the approval window, restarted each time a watched mission launches;
   - the operator's latest run with Metis off and with Metis on.

   The forecast comes from `metis_agent/data/decision-bupt1-20230621T1250.json`. That is an allowlisted extract with no realized values, and the planner recomputes the +122 slot at start-up.
2. `POST /v1/viewer/mission-run {plan, proposal_id?, watch?}` flies a plan. It does five things:
   - stops the viewer's current run;
   - moves the task windows in `configs/metis-wildfire.yaml` to the plan, keeping each task's start guard;
   - creates the run with its private scenario;
   - for `watch: true`, sets a hold at `METIS_ALERT_S` (+60), where the runner pauses the run in the same transaction as that tick; for the Metis plan, commits ticks up to the hold instead;
   - rebinds the session cookie.

   Metis records the run and the viewer starts it at T0. With `watch: true` (Metis on), Metis records a pending alert at +60; the outcome reports it only once the run has reached +60 and paused, and dismissing earlier returns 409 `alert_not_pending`.
3. The operator decides on the alert:
   - `POST /v1/metis/proposals/{id}/approve` records the approval (409 `uplink_closed` if the window elapsed), then `POST /v1/viewer/mission-run {plan: metis, proposal_id}` continues the mission on the Metis plan from +60. Both plans are identical up to the batch at +70, so the new run's committed history matches the held one.
   - `POST /v1/metis/runs/{run_id}/dismiss` records the dismissal, and the viewer resumes the held run on the original schedule.
4. `GET /v1/metis/runs/{run_id}/outcome` reports the run from public data, reading only frames not yet seen:
   - the margin: `eps.battery_energy_wh − public limit × capacity`;
   - each task's state: `skipped` when an `operation_skipped` event names it, otherwise `pending`, `running` or `done` by committed time;
   - the downlink progress and, once the capture and downlink are done, the delivery time;
   - whether Metis watched the mission, and its alert: `pending`, `approved` or `dismissed`, with who decided.

## The scenario and its limits

`configs/metis-wildfire.yaml` is generated by `scripts/build_metis_scenario.py`. It holds one spacecraft, `SAT-1`, with the original schedule.

- **Orbit:** circular, 97.6° inclination, about 95 minutes, calibrated so the simulator's own eclipses fall at mission 0–15, 75–110 and 170 onward.
- **Array:** a healthy ideal array of 68 W.
- **Battery:** 19 Wh with a public limit at 50% charge, the top of the protected reserve. That leaves a 9.5 Wh margin above the reserve.
- **Start guard:** every task has `min_start_soc: 0.5`.
- **Essential load:** a constant 8.1 W, BUPT-1's realized mean after scaling.
- **Hidden truth:** a private solar-derating scenario reproduces BUPT-1's realized harvest on 21 June 2023, per 5-minute bin. Its values never reach the viewer or consumers; only its source's name does, through `run.environment_source`.
- **Task loads:** set per operation with `added_load_w`: batch 16 W, capture 20 W, downlink 30 W.

What this does not establish:
- **The decision time:** 21 June 12:50 was picked after testing as a clear case where the plan works. Across 501 test decision times, repeating the last orbit made the better plan. See the Metis_Data walk-forward experiment.
- **Metis off:** it stands for flying the schedule unchanged. The other planner inputs on the proposal card would have chosen +102 to +106 instead.
- **Downlink:** it is judged by energy only. Ground contacts, link budget and data volume are not modeled.
- **The guard:** it checks only at a task's start and never ends a running task.
- **Approval:** approving creates a new run that continues from the alert; no command is uploaded into the held run.
- **Alert timing:** the alert fires at a fixed +60 hold, not from a live re-forecast.
- **Decision state:** approvals and the run registry are held in memory and are lost when the server restarts.
- **One active run:** the simulator drives one run at a time. A demo launch stops the session's own run and any other active viewer run, for example a Metis-held run left open in a second browser.

To regenerate after changing the forecast:

```sh
uv run python scripts/extract_metis_decision.py <demo_origin.json> <mission_scenario.json>
uv run python scripts/build_metis_scenario.py <demo_origin.json>
uv run python scripts/metis_demo_evidence.py <demo_origin.json>
```

Both inputs come from `Metis_Data/BUPT-1`:
- `experiments/mission-budget-walkforward/demo_origin.json`
- `scripts/mission_scenario.json`

The evidence script exits non-zero if the story no longer holds in simulator physics.

**Settings:**

| Variable | Default | Meaning |
|---|---|---|
| `METIS_MISSION_CONFIG` | `configs/metis-wildfire.yaml` | Demo template; Metis is hidden from the Overview when the file is missing |
| `METIS_MISSION_SPEED` | 120 | Playback speed of a demo run |
| `METIS_ALERT_S` | 3600 | Mission second where a Metis-on run pauses with its alert; the Metis plan continues from it |
| `METIS_DECISION_WINDOW_S` | 900 | Approval window, in wall-clock seconds |
