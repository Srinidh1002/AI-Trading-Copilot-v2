# Canonical paper execution pipeline

`run_canonical_paper_execution` is explicit only. It consumes existing canonical
risk evidence, prepares a candidate only if absent, builds a request only if
absent, validates supplied manual authorization once, then executes once at
most. It maps FILLED to `EXECUTED`, DUPLICATE to `DUPLICATE`, and non-authorized
or execution-blocked outcomes to bounded non-live statuses.

It never reruns analysis, decision, selection, planning, sizing, risk, or
session validation. Session evidence is supplied to authorization validation.
Four-index long-premium support is preserved. No legacy executor, broker,
persistence, automation, or live execution is used; P4-5 owns order state.
