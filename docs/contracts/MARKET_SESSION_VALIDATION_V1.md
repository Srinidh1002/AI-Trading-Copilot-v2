# Market Session Validation v1

`MarketSessionValidationV1` is a deterministic Asia/Kolkata validation result for certified NIFTY/NSE and SENSEX/BSE identities. It classifies regular, pre-open, closed, weekend, holiday, and explicit special sessions, with stale/future timestamp blockers and semantic serialization excluding generated validation identity/time.

`LENIENT_ANALYSIS` warns when an empty holiday calendar is used. `STRICT_EXECUTION` requires an explicitly trusted injected calendar. No exchange calendar is scraped or downloaded.

Canonical gating is opt-in through `CanonicalPipelineDependencies.session_validation_enabled`; disabled callers retain their existing behavior. Paper preparation and execution accept an explicit validation or calendar/policy inputs and reject a strict blocked session before executor import.
