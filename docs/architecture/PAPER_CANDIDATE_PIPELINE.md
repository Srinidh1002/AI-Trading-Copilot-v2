# Paper candidate pipeline

The optional canonical-risk preparation path maps an approved risk result to a
validated paper candidate using bounded linkage metadata. It does not submit an
order or change paper-execution authorization.

For the canonical-risk branch only, P3-5E adds optional fail-open audit hooks.
Preparation emits started after canonical-risk type validation and one terminal
event; completed means exactly one candidate was created. Legacy preparation
calls are unchanged, and audit emission never invokes an executor.
