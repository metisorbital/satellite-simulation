# Engineering team agreement

The source of truth is `docs/specification.md`, `docs/physics-model.md`, and
`docs/contracts.md`. Requirements are gates to verify, not claims of completion.

## Responsibilities and handoffs

- Integration lead/PM owns acceptance scope, interface decisions, service composition,
  and the evidence report. Record omissions honestly.
- Physics engineer owns pure orbit/environment/EPS/scenario modules and numerical evidence.
- Contract engineer owns validation, immutable configuration, public schemas and generated types.
- Viewer engineer owns presentation and browser behavior. Never calculate orbital physics in the UI.
- Independent QA/reviewers inspect one module or one concern at a time. A module's
  implementer addresses findings; integration owns final cross-module verification.

Assign explicit file ownership before parallel work. Agents share a workspace:
never reset, revert, delete, or overwrite another contributor's changes. Communicate
interface changes before changing callers. Use smaller models for bounded scaffolding,
fixtures, documentation, and logging tasks; reserve broad integration and physics for senior review.

## Implementation principles

Use KISS, DRY, SRP and composition. Keep numerical functions independent of HTTP and
database code. Prefer a small explicit interface over plugin frameworks or extra services.
Use typed Python and NumPy-style docstrings for all public classes and functions.
Use one clock, fixed simulated steps, stable satellite ordering, and explicit units/frames.
Generated schemas/types must come from Python models. Public outputs are allowlisted;
private scenarios, seeds, outcome thresholds and future health never enter viewer/consumer data.

## Definition of done

1. Focused invariant/contract tests pass, including meaningful failure paths.
2. Another reviewer checks the module's interfaces, correctness and applicable trust boundaries.
3. Findings are fixed and the affected tests rerun.
4. Integration, lint, type checks and browser checks pass.
5. Evidence states commands, measured outcomes, hardware, model limits and remaining gates.

Preserve existing work. Do not deploy, publish, or push without authorization. Do not
weaken a numerical tolerance to make a failing implementation appear correct.

