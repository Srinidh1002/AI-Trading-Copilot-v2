# PAPER Runtime Troubleshooting

## Read the right layer

| Symptom | Meaning | Action |
| --- | --- | --- |
| Process exits normally / outer cycle `COMPLETED` | Scheduling operation completed | Inspect the inner result before declaring success |
| Inner `COMPLETED_NO_ACTION` / opportunity `NO_ACTION` | Valid analytical no-trade | Record it; do not force a trade |
| Inner monitoring `FAILED`, `P7_MONITORING_FAILURE`, no active P7 position | Accepted no-position fail-closed path | Confirm no active position was expected; do not fabricate state |
| `RUNTIME_FAILED` or outer cycle error | Runtime or provider failure | Preserve JSONL/journals, then diagnose before retrying |
| `IDEMPOTENCY_PAYLOAD_CONFLICT` | Duplicate key with changed semantic payload | Stop and investigate journal/state integrity |

## SmartAPI rate limiting and cooldown

`AngelMarketDataClient` detects genuine rate-limit responses separately from
authentication failures. `MarketDataRequestController.record_rate_limit()`
applies a shared exponential cooldown; retries are bounded by
`max_rate_limit_retries`. A repeated limit ends as a structured
`rate_limited` failure rather than an unbounded retry.

Operational response:

1. Do not launch a second process or manually hammer the provider.
2. Preserve the JSONL and journal evidence.
3. Let the configured cooldown expire, then run one controlled cycle.
4. Escalate repeated exhaustion as a provider availability incident.

## Provider/data failures

- Empty candles, empty option chains, malformed responses, and timeouts must
  result in no action or a fail-closed failure; they never justify a live order.
- NIFTY and SENSEX provider identities are supported separately, but the
  current runtime is one configured primary market at a time.
- Do not claim a cross-market winner from two separate launches.

## Recovery and persisted state

The certified composition currently uses an empty successful startup recovery
stub and a no-active-position monitoring factory. It does not discover active
P7 positions. A corrupt or missing journal/persistence document is a stop-and-
investigate condition, not a reason to recreate state manually.

## Evidence commands

Use the summarizer command in `PAPER_RUNTIME_RUNBOOK.md`. Its `assessment`
reports inner failures/fail-closed states separately from outer completion and
keeps malformed JSONL lines as warnings rather than aborting the report.
