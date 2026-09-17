# Risk validation pipeline

The P3-5C pipeline validates canonical trade-plan and session prerequisites, calls position sizing once only for an eligible ready plan, and maps the typed sizing result. It never rebuilds analysis, decisions, selection, or plans, and has no execution integration.

P3-5D may consume an approved result to prepare a sized paper candidate without
altering risk validation or enabling execution.

P3-5E supports optional fail-open audit hooks. Risk validation emits started
after input validation and exactly one terminal event. No-action and all
deterministic gates emit blocked; only represented failed results emit failed.
Audit payloads are bounded primitives and do not cause sizing for gated inputs.
