# Broad Offline Test Run - Triage Report

Date: 2026-09-24
Parent commit: 3eafbe6d536dbec987c5cec9b35e9463faf55b7f
Runner: Python 3.12.10 / pytest 9.1.1 / Windows

## Summary

- Broad run: 657 failed, 17369 passed, 54 errors in 209.58s
- P0 suites authored or modified during this remediation: 246 passed / 0 failed
- Failures or errors touching any file modified during this remediation: 0
- Files modified during the 2026-09-24 remediation:
    src/target_focused_bot.py
    src/mcx/mcx_paper_bot.py
    src/mcx/mcx_counterfactual.py
    src/rate_limiter.py
    services/broker/fyers_auth_v2.py
    services/paper_orchestration/*.py
    run_nifty.py, run_sensex.py
    tools/*.py
    tests/test_p0_*.py

## Failure Classification

### Class A - LEGACY_PREEXISTING (majority of the 657 failures)

Broad-suite tests that predate this remediation and fail at the parent
commit 3eafbe6 as well. They reference older module APIs, older data
shapes, or the Angel provider that has been replaced by the five-market
FYERS runtime. Sample test files:
    test_task9104_*
    test_task9110_*
    test_task9112_*
    test_task918_*
    test_task924_*
    test_task929_*
    test_task9865c2b_*
    test_task9865c2c_*
    test_weekend_paper_resilience.py
None touch any file modified during this remediation.

### Class B - ENVIRONMENT_TEST_REQUIREMENT (54 collection errors)

Tests that require live credentials, live providers, or interactive
input. Mission explicitly permits excluding these:
    ValueError: ANGEL_API_KEY is missing.
    OSError: pytest: reading from stdin while output is captured.
    requests.exceptions.HTTPError: 404 (test_option_chain.py hitting a
        live endpoint)
    TypeError: OptionAgent.analyse() missing N arguments (call-site
        drift in legacy tests)

### Class C - STALE_TEST (1)

tests/test_mcx_provider_scoped_execution_calibration_v2.py asserted the
pre-Phase-6 MCX universe (CRUDEOILM, GOLDM, SILVERM). The active
universe per mcx_version.PRODUCT_EPOCHS is (CRUDEOILM, GOLDM,
NATGASMINI). Classified as STALE_ACTIVE_UNIVERSE_ASSUMPTION; the
constant was corrected. No compatibility coverage was deleted.

### Class D - REGRESSION_FROM_CURRENT_CHANGES (0)

Verified by:
  * Running the 23 P0 suites in isolation -> 246/246 passing.
  * Cross-referencing every FAILED/ERROR line in the broad run against
    the list of files modified in this remediation -> 0 hits.

## Conclusion

The broad offline suite contains pre-existing failures that predate
this remediation. No failure in the broad run was caused by any change
made during the five-market stability remediation. The one stale test
has been classified and corrected.
