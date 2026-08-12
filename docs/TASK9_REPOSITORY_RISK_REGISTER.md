# Task 9 repository risk register

| Severity | Finding | Evidence / containment | Required follow-up |
|---|---|---|---|
| RESOLVED | Legacy completed-candle fallback bypassed the durable historical gate. | R2 structurally excluded it from certified capture and root CLI rollback; R3 added the shared cooldown and durable-gate checks before its one compatibility provider request. | Keep compatibility behavior under focused tests. |
| HIGH | Repository has multiple historical/provider-era paths. | `market_data.py`, diagnostics capture, recovery probe, completed-candle service, and certified multi-timeframe service. | Keep a provider-call registry and prohibit uncertified paths from Task 9. |
| HIGH | Frozen-mapping compatibility was a live defect. | Captured evidence uses `MappingProxyType`; Task 8 retention now accepts `Mapping`. | Audit all concrete `dict` checks before accepting immutable contract values. |
| MEDIUM | Generic persistence implementations vary in atomicity and schema discipline. | New Task 9 stores use fsync/replace; older services vary. | Consolidate persistence helper after schema-by-schema review. |
| MEDIUM | Root-level scripts and day-one engines remain callable outside Task 9. | Numerous legacy runners and test scripts. | Mark/document active versus compatibility CLIs. |
| MEDIUM | Colon-delimited IDs are used in several contracts. | Provider incident IDs have fixed suffix parsing requirements. | Use prefix plus suffix-aware parsing, not unconstrained `split(':')`. |
| LOW | Naive `datetime.now()` remains in legacy code. | Static audit; certified Task 9 validates aware timestamps at boundaries. | Normalize legacy services as they are consolidated. |

| RESOLVED | yfinance ownership was ambiguous. | R4 proved `app.py` enters `dashboard.dashboard_v2.home`; legacy `dashboard/home.py` alone imports `services.market_data`. Task 9 surfaces exclude both. | Keep as explicit research compatibility only. |

No critical Task 9 PAPER-safety or counting-authority bypass was proven by this
static audit. No destructive cleanup was performed.
