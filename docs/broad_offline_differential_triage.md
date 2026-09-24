# Broad Offline Differential Triage (R2-5)

Date: 2026-09-24
BASE_HEAD: 3eafbe6d536dbec987c5cec9b35e9463faf55b7f
FINAL_HEAD: 3fca7ae05032087b4220b734f3e11cc49eccf133

## Method

Two isolated git worktrees of the same repository were created:

    _r2_worktrees/BASE    @ 3eafbe6d
    _r2_worktrees/FINAL   @ 3fca7ae0

The identical pytest invocation was used in each:

    python -m pytest tests \
        -p no:cacheprovider \
        --continue-on-collection-errors \
        --tb=no -rfE -q

Same Python 3.12.10, same installed dependency set, same environment:

    PYTHONPATH=<worktree>/src;<worktree>
    FYERS_APP_ID=""              (fail-closed on any test that reads it)
    FYERS_ACCESS_TOKEN=""
    FYERS_RATE_LIMIT_STATE_PATH=<isolated temp file>   (R2-3 belt)

`-rfE` produces a final list of FAILED and ERROR node IDs. A small
parser reduced each run to a set of node IDs and computed:

    FAILURES_ONLY_IN_BASE    = BASE_SET - FINAL_SET
    FAILURES_ONLY_IN_FINAL   = FINAL_SET - BASE_SET
    FAILURES_IN_BOTH         = BASE_SET & FINAL_SET

## Result

    BASE_FAILED_COUNT        = 657
    BASE_ERRORS_COUNT        = 54
    BASE_TOTAL_ISSUES        = 711

    FINAL_FAILED_COUNT       = 656
    FINAL_ERRORS_COUNT       = 54
    FINAL_TOTAL_ISSUES       = 710

    FAILURES_ONLY_IN_BASE    = 1
    FAILURES_ONLY_IN_FINAL   = 0
    FAILURES_IN_BOTH         = 710

## Interpretation

### REGRESSION_FROM_CURRENT_CHANGES = 0

No test that passed at BASE fails at FINAL. The mission's acceptance
condition — "FINAL introduces zero new offline regressions relative to
BASE" — is satisfied.

### Fixed by current changes

The single FAILURES_ONLY_IN_BASE is:

    tests/test_mcx_provider_scoped_execution_calibration_v2.py::
        test_defaults_are_exact_three_and_uncalibrated

This test asserted the pre-Phase-6 MCX universe
("CRUDEOILM", "GOLDM", "SILVERM"). The active universe per
mcx_version.PRODUCT_EPOCHS is (CRUDEOILM, GOLDM, NATGASMINI).
Classified STALE_ACTIVE_UNIVERSE_ASSUMPTION and corrected in commit
1b89384.

### Pre-existing failures (710 in both)

The 710 issues present in both runs are pre-existing. They fall into
two broad classes:

  * Legacy tests for the Angel provider and its call shapes. The
    five-market runtime replaced Angel with a data-only FYERS layer;
    these tests reference APIs and fixtures that no longer exist.
  * Legacy CLI / dashboard / research-runner tests that require
    interactive input or live credentials. They raise collection
    errors (ValueError: ANGEL_API_KEY is missing, OSError: reading from
    stdin, HTTPError: 404 from a live endpoint, etc.).

These tests were not modified during the five-market remediation and
their failure is not caused by it.

## Conclusion

R2-5 PASS.

    FAILURES_ONLY_IN_FINAL = 0
    NEW_REGRESSIONS        = 0

The FINAL worktree is strictly better than BASE on the offline suite:
one stale test repaired, zero regressions introduced.
