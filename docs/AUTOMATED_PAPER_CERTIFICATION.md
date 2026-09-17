# Automated PAPER Certification

## Certified checkpoint

- Branch: `p9-real-time-paper-orchestration`
- Commit: `c686f45e92121a988622111a934092d833134f75`
- Tag: `automated-paper-certified`
- Focused certification checkpoint: 15 passed (historical checkpoint supplied
  with this certification record)
- Local runtime evidence: successful five-cycle live-data PAPER soak records
  with `cycles_completed=5`, `cycles_with_errors=0`, and graceful shutdown.

The certified composition remains `execution_mode=PAPER`,
`live_execution_eligible=false`, and `broker_order_submission=false`. These
are enforced by `services/paper_orchestration/certified_runtime_safety.py` and
the launcher composition; no broker order submission is certified.

## What is certified

- PAPER-only launcher, controls, JSONL logging, graceful stop, journals, and
  live-data reads.
- A configured single NIFTY/NSE or SENSEX/BSE provider path, with NFO/BFO
  option-chain routing respectively.
- Automated-PAPER P6/P7/P8 boundaries only when the required typed upstream
  evidence is available.
- A no-trade result as a valid analytical result. `NO_ACTION`, `NO_TRADE`,
  blocked, unavailable, and conflicting outcomes are not execution failures.

## Important qualification

The five-cycle evidence has clean **outer** runtime counters, while the last
monitoring result is internally `FAILED` with `P7_MONITORING_FAILURE` because
no active certified P7 position is available. This is accepted fail-closed
behavior for a no-position soak: it prevents invented monitoring actions. It
does not certify active-position monitoring or restart recovery.

Likewise, this checkpoint does **not** certify NIFTY-vs-SENSEX selection. The
current launcher schedules one configured primary market per cycle; it does
not evaluate both, rank both, select a winner, or retain a losing-market
rationale. See `TWO_MARKET_RUNTIME_STATUS.md`.

## Evidence review standard

Do not call a run successful from process exit code or `cycles_with_errors=0`
alone. Review the JSONL `stats.last_cycle.opportunity.result` and
`stats.last_cycle.monitoring.result` inner lifecycle statuses, stage failures,
and PAPER actions. Use `scripts/summarize_paper_runtime.py` for a stable report.

## Certification status

This is a PAPER operational checkpoint, not a live-trading authorization.
Small-capital live prerequisites are documented separately and cannot override
the code-level PAPER-only guards.
