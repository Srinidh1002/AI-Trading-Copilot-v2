# Task 6 — Real-Time PAPER Certification Rules

Task 6 is one long-running certification task, not a collection of new
roadmap tasks. Every defect or retest discovered during the 100+100 session
remains Task 6 work until its exit gate is satisfied.

## Countable recommendation

Each eligible analysis cycle creates one NIFTY record and one SENSEX record.
A record counts only with real live-market acquisition, exchange-market
timestamp, session identifier, cycle ID, prediction ID, one market identity,
complete typed evidence or explicit unavailable evidence, one action (CALL,
PUT, WAIT, or NO_TRADE), validity/evaluation window, later observed outcome,
final marked result, journal persistence, and report inclusion.

The parent winner does not erase the losing market record. CALL/PUT/WAIT/
NO_TRADE may count; HOLD/EXIT are lifecycle actions and never increment a
recommendation counter. A trade is not required. WAIT and NO_TRADE must be
objectively evaluated later.

Dashboard refreshes and duplicate cycle IDs create no additional record.
Replay, fixtures, backtests, manually fabricated records, pre-start records,
and weekend/closed-market stale captures never count. Provider-unavailable
cycles may be journaled, but count only if policy explicitly makes a
DATA_UNAVAILABLE recommendation valid and it later receives a final status.
Pending outcomes do not count. Deleting a loser invalidates certification;
manual edits require an audit event.

## Counters

- `nifty_recommendations_generated`
- `nifty_recommendations_completed`
- `sensex_recommendations_generated`
- `sensex_recommendations_completed`
- `pending_outcomes`
- `invalid_records`
- `duplicate_records`
- `excluded_replay_records`

## Completion gate

Task 6 completes only when each completed counter is at least 100, no replay is
counted, all PAPER trades reconcile, no critical safety incident remains
unresolved, daily and weekly reports exist, a monthly report exists when the
calendar duration permits, the final full suite is green, and a final PAPER
certification report is accepted.
