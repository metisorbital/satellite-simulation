# Research and Review Record

The [main specification](../specification.md), [physics appendix](../physics-model.md), and [contracts appendix](../contracts.md) define the implementation baseline.
Research notes preserve alternatives and preliminary proposals; they are not additional requirements.
This is a preparation-time record from 2026-09-21. For current delivered behavior and measurements, read [implementation validation](../validation/README.md).

| Document | Purpose |
|---|---|
| [Physics research](physics-research.md) | Orbit-engine, frame, eclipse, power, Cesium, and OrbitSmith investigation. |
| [Contract research](contracts-research.md) | Database alternatives, sizing, producer identity, replay, and transport tradeoffs. |
| [Product research](product-research.md) | Scope, dataset evidence, market-reference limits, and predictive-claim distinctions. |
| [Specification review](spec-review.md) | Independent scope and implementation-handoff review with resolution record. |
| [Physics review](physics-review.md) | Independent review of equations, timestamps, examples, and validation gates. |
| [Contracts review](contracts-review.md) | Independent review of delivery, persistence, control, lifecycle, and temporal semantics. |

Important synthesis decisions supersede broader research proposals:

- P0 has one solar-derating scenario instance, an energy-only battery model, and no voltage/current/thermal/ground-station model.
- Synthetic central-plus-J2 propagation is the mandatory orbit path; TLE/SGP4 and Basilisk are extensions.
- Frame identity is `(source_id, stream_id, sequence)`; there is no additional required event UUID on telemetry frames.
- Replay is durable consumer retrieval. The P0 viewer uses current committed data and pause/resume, with recorded-run seeking deferred.
- Public measurement frames include `sample_window_s`, endpoint `mode`, and `interval_mode` so interval power is not assigned to the wrong operating mode.
- The six-hour example was an uncalibrated design fixture at research time; [configs/demo.yaml](../../configs/demo.yaml) is the later executable demo.

## Document Validation

Checks performed during preparation on 2026-09-21:

- Parsed the normative YAML and JSON examples successfully.
- Checked satellite IDs/profile/constellation references, fixed timing settings, scenario point ordering, and run-duration limits in the YAML example.
- Checked the JSON example's battery energy/SOC relationship and bus power balance.
- Checked Markdown fence balance, local-link destinations, and trailing whitespace across the document set.
- Confirmed the stated 550 km reference period is approximately 95.64988 minutes and the 100 W / 60 s / 95% discharge fixture is approximately 1.754386 Wh.

These are documentation consistency checks, not application or schema-conformance tests.
At the time of this preparation record, no generated Pydantic schema, production orbit implementation, database, browser application, performance benchmark, or calibrated fault experiment existed. The later [validation record](../validation/README.md) documents those delivered components and their limits.
An independent approximate physics sanity calculation informed review, but it does not establish the final example's outcome under the specified Astropy/IERS implementation.

The PRD skill's referenced external template files were unavailable locally; its embedded requirements structure and the documentation skill's available metadata/style guidance were used instead.
The user's scope and preparation context determine the document, not an assumed fixed build deadline.
