# F15 — Five-Market PAPER Baseline Freeze

Date: 2026-09-28
Branch: five-market-offline-readiness

## Source

    BASE_HEAD        (pre-F15)   8cc879a06fe179c13a680d5c35bdb587c0e8ca82
    OPTION_D_COMMIT              a1cf32ea943291c55b6b11bd2ceb76cd847e780f
    WRITER_COMMIT                b4156808a63bf0aa093cc9a7e9c3876d15908fe2
    PREFLIGHT_BOOTSTRAP_COMMIT   bdff3589d91f9e2bf287ea24a9de3d9aaecd7ee9
    SUPERVISOR_BOOTSTRAP_COMMIT  af901214217efbfb632d551d7985839c881a6bce
    SUPERVISOR_RUFF_COMMIT       10852673e510a58902665ee7850fb4d0b1aa5f12

Branch pushed to origin and matching locally at the time of freeze.

## Environment

    Python               3.12.10
    Runtime lockfile     requirements-runtime-lock.txt
      fyers-apiv3==3.1.17
      python-dotenv==1.2.3
      pandas==3.0.5
      numpy==2.5.3
      requests==2.31.0
      yfinance==1.7.0
      websocket-client==1.6.1
      websockets==17.1
      smartapi-python==1.5.5
      PyOTP==2.10.0
      logzero==1.7.0

## Provider authority

    Data provider           FYERS (data-only)
    Angel fallback          False
    Broker submission       False
    Live execution          False
    Live eligibility        False
    Order capability        False

## Strategy (frozen, unchanged in F15)

    ENTRY_THRESHOLD         70
    INDEX SL                5%
    MCX SL                  -8%
    T1 / T2 / T3            +15% / +30% / +50%
    STRATEGY_VERSION        NS_DESIGN_B_BID_AUTH_V3
    CERTIFICATION_EPOCH     NS_CERT_20260916_V3

No strategy, threshold, stop, target, indicator, scoring, or epoch
change was made during F15.

## Starting certification counters

    NIFTY                   3 / 100
    SENSEX                  3 / 100   (was 2 at F15 open; +1 by legitimate
                                      PAPER trade TRD_20260928_095648)
    CRUDEOILM               0 / 100
    GOLDM                   0 / 100
    NATGASMINI              0 / 100

The SENSEX increment was produced by the strategy itself; no engineering
action touched any counter. `certification_counter == len(counted_trade_ids)`
holds for both INDEX markets.

## MCX execution calibration (Option D)

Authoritative config: `data/execution_evidence/mcx/exec_config.json`
schema_version: 2

For each of CRUDEOILM, GOLDM, NATGASMINI the written record contains:

    calibration_provider              "FYERS"
    depth_quantity_semantics_verified True
    depth_quantity_unit               "PROVIDER_QUANTITY"
    execution_freshness_calibrated    True
    execution_quote_max_age_seconds   15
    depth_freshness_basis             "SYNCHRONOUS_FYERS_DEPTH_RESPONSE"
    depth_provider_timestamp_available False
    last_trade_timestamp_source       ["DEPTH:ltt"]
    evidence_kind                     "LIVE_MARKET_DEPTH"
    evidence_ref                      data/execution_evidence/mcx/fyers/<product>_<utc>.jsonl

Interpretation:

  * Execution-depth freshness is a synchronous FYERS depth response
    observed locally. FYERS does not publish a per-snapshot depth-update
    timestamp; this is reported honestly.
  * FYERS depth payload `ltt` is last-trade time for the contract and is
    preserved as informational liquidity evidence. It is not a freshness
    clock.
  * Depth quantity is not proven to be exchange lots by the FYERS SDK
    surface used here. It is recorded as PROVIDER_QUANTITY and consumed
    only for relative liquidity and two-sided book presence. Position
    sizing uses contract lot size, not this field.

Live evidence collected 2026-09-28 with MCX session OPEN:

    product      samples  distinct hashes  rtt_p95  snapshot max age  verdict
    CRUDEOILM    20       20               66.9 ms  0.001 s          PASS
    GOLDM        20       20               59.1 ms  0.000 s          PASS
    NATGASMINI   20       20               79.4 ms  0.000 s          PASS

## Preflight

Command:

    python tools/preflight_and_start_five_market_paper.py --dry-run

Reported before live launch:

    PREFLIGHT=NOMINAL
    READY_MARKETS=NIFTY,SENSEX,CRUDEOILM,GOLDM,NATGASMINI
    HELD_MARKETS=-
    SUPERVISOR_STARTED=False

Infrastructure: REPO OK, AUTH OK, PAPER OK, SUPLOCK OK, LIMITER OK.
Per-market: all five OK (cert, state, calendar, calibration where
applicable, provider health).

## Five-worker canary

Launched via the canonical preflight (no manual worker start, no
--allow-partial). Supervisor command:

    python -m services.paper_orchestration.automated_paper_supervisor_v2 \
        --markets NIFTY,SENSEX,CRUDEOILM,GOLDM,NATGASMINI

Supervisor log proof at 2026-09-28 10:02:37 IST:

    [NIFTY]      started
    [SENSEX]     started
    [CRUDEOILM]  started
    [GOLDM]      started
    [NATGASMINI] started

Process tree at 10:03:52 IST: five market workers, each a single logical
process family, all holding their worker lock. Supervisor holding its
singleton lock and ticking every 30s.

MCX worker stdout at 10:03 shows real cycle output:

    CRUDEOILM    LONG_CONFIDENCE=76  ACTION=BUY_CALL  persistence 1/3
    GOLDM        SHORT_CONFIDENCE=69 blocked by STABLE_PCR_PCR_INCOMPLETE
    NATGASMINI   SHORT_CONFIDENCE=55 ACTION=WAIT

The CRUDEOILM BUY_CALL is a live strategy signal that has not yet met
the 3/3 persistence gate. It has not entered. This is correct behavior
and is not a call to action.

## Invariants verified at freeze

    PAPER only
    Broker submission false
    Live execution false
    Live eligibility false
    Automatic fallback false
    Order capability false
    No strategy change
    No threshold change
    No SL/T1/T2/T3 change
    No epoch change
    No manual counter change
    No duplicate workers
    No crash loop
    No rate-limit storm

## CI

Offline stability workflow ran at prior commit(s); all focused Option D
tests, writer tests, verifier tests, preflight tests, supervisor tests,
state authority tests, and lock tests are green at freeze.

## What happens next

The supervisor continues to run unattended until market close
(NIFTY/SENSEX stop at 15:30 IST, MCX at 23:30 IST), at which point the
supervisor runs the daily audit and idles.

Certification target remains 100 per market. No parameter will change
mid-epoch. The counterfactual capture continues to accumulate threshold-
only rejections for later expectancy review. The Brain/FIA/Screener
roadmap does not begin inside this campaign.
