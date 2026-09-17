# Runtime shadow contract adapters

`services.contracts.runtime_adapters` provides optional, side-effect-free diagnostics for the unchanged dashboard and live-option paths. It is not imported by `app.py`, dashboard rendering, paper orchestration, broker code, or the live CLI.

`build_dashboard_shadow_contracts` composes the dashboard MarketSnapshot and trade-response adapters. `build_live_option_shadow_contracts` adapts explicitly supplied live-analysis evidence and the legacy pipeline response; it never fetches that evidence. Individual snapshot/decision builders are available for controlled callers. All builders copy legacy mappings, contain exceptions, and return a supplemental `{snapshot_v1, decision_v1, valid, warnings, errors}` result.

`compare_shadow_contracts` is deterministic and reports legacy status, v1 action/authorization/execution, warnings/errors, blocks, score availability, plan mapping, and data-health status. It reports differences rather than asserting semantic equivalence. `serialize_shadow_contracts` supplies deterministic JSON for one result.

The only paper helper remains `to_paper_execution_candidate`. It returns no candidate for WAIT, HOLD, BLOCKED, ANALYSIS_ONLY, or manual approval. PAPER_READY/AUTHORIZED directional decisions need a valid plan and remain unsubmitted data only.

Known gaps are intentional: legacy dashboard and live outputs often lack snapshot IDs, complete identity, source health, or clear lifecycle semantics. The shadow layer adds the v1 snapshot ID to a copied legacy decision payload, blocks ambiguous direction/invalid plans, and records warnings instead of inventing evidence. No default response body, decision, threshold, paper state, database state, or network behavior changes.
