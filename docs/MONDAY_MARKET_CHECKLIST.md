# Monday PAPER Checklist

1. Confirm the checkout is on the intended branch and `git status` is expected.
2. Confirm PAPER-only configuration; never enable live trading or broker order
   submission.
3. Run the one-cycle command from `PAPER_RUNTIME_RUNBOOK.md`.
4. Review runtime JSONL inner opportunity and monitoring results, not exit code
   alone.
5. Treat `NO_ACTION` as valid. Treat no-active-P7 monitoring failure as the
   expected fail-closed no-position state only when no position exists.
6. If provider rate limits occur, stop competing launches and allow cooldown.
7. Run five cycles only after the one-cycle evidence is understood.
8. Generate the JSON and text summary; preserve logs and journals for review.

Do not claim NIFTY/SENSEX ranking, do not force a trade, and do not enable live
execution.
