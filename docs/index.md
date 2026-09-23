---
icon: lucide/rocket
---

# Metis Satellite Simulation

Deterministic synthetic orbit-to-power telemetry for a prepared run, with an Earth-orbit viewer. This project provides data to a separate monitoring product; it is not a health-analysis or command system.

## Start here

- [Getting started](getting-started.md) — prerequisites, local demo setup, and the authentication boundary.
- [API consumer guide](api.md) — authenticate, discover a stream, and resume durable telemetry reads.
- [Python class reference](python-api.md) — understand the main objects and how their methods fit together.
- [First-change guide](contributing.md) — find a module and run its focused checks.
- [Project README](https://github.com/metisorbital/satellite-simulation#readme) — quick local demo commands and a summary of measured capacity.

## Design and implementation

- [Product specification](specification.md) — scope, requirements, and acceptance gates.
- [Physics model](physics-model.md) — normative orbit, environment, and power model.
- [Configuration and data contracts](contracts.md) — validated configuration and public data shapes.
- [Implementation map](implementation.md) — how the specified system is organized in code.

The specification and its appendices are the source of truth. Research and review documents provide supporting context in the [research index](research/README.md).

## Validation evidence

- [Validation and review index](validation/README.md) — executed checks and module reviews.
- [Numerical validation](validation/physics.md) — physics implementation results and limits.
- [Browser validation](validation/browser.md) — viewer checks and measured browser performance.
- [Capacity report](validation/throughput.md) — throughput results, timing limits, hardware, and measurement method.

The model is a validated synthetic demonstration within its stated approximations, not a flight-validated digital twin.
