import ast
import inspect
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(
        0,
        str(SRC),
    )

from prediction_ledger import PredictionLedger


BOT_PATH = ROOT / "src" / "target_focused_bot.py"
LEDGER_PATH = ROOT / "src" / "prediction_ledger.py"


def _bot_source():
    return BOT_PATH.read_text(
        encoding="utf-8",
    )


def _method_source(name):
    text = _bot_source()
    tree = ast.parse(text)
    lines = text.splitlines()

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == name
        ):
            return "\n".join(
                lines[
                    node.lineno - 1:
                    node.end_lineno
                ]
            )

    raise AssertionError(
        f"method not found: {name}"
    )


def _ledger_kwargs():
    return {
        "market": "NIFTY",
        "bias": "NEUTRAL",
        "bias_confidence": "WEAK",
        "readiness": "WAIT",
        "action": "WAIT",
        "blockers": [],
        "bull_score": 1.0,
        "bear_score": 1.0,
        "bull_pillars": 2,
        "bear_pillars": 2,
        "evidence_coverage_pct": 80.0,
        "spot": 23500.0,
        "spot_freshness": "FRESH",
        "regime": "RANGE_BOUND",
        "selected_trade": None,
        "config_version": "v3-phase-g",
    }


def test_runtime_imports_canonical_builder():
    assert (
        "premarket_state_builder_v2 "
        "import build_premarket_state_v2"
        in _bot_source()
    )


def test_runtime_builds_canonical_premarket_state():
    src = _method_source(
        "get_enhanced_sentiment"
    )

    required = (
        "build_premarket_state_v2(",
        "previous_day_payload=prev_ctx",
        "session_open=_session_open_for_v2",
        "external_payload=ext",
        "vix_payload=evix",
        "fii_dii_payload=efii",
        "event_payload=high_impact",
        "event_source_authoritative=False",
    )

    assert [
        marker
        for marker in required
        if marker not in src
    ] == []


def test_runtime_uses_canonical_gap_context():
    src = _method_source(
        "get_enhanced_sentiment"
    )

    assert (
        "_gap_pct = _pm.gap.gap_pct"
        in src
    )

    assert (
        'self._session_open_price - _pd["close"]'
        not in src
    )


def test_decision_event_gate_uses_canonical_authority():
    src = _method_source(
        "get_enhanced_sentiment"
    )

    assert (
        "event_block = bool(_pm.event_risk.hard_block_eligible)"
        in src
    )

    tail = src[
        src.index(
            "# Rule 2: Need 2+ independent pillars agreeing"
        ):
    ]

    assert (
        "minutes_to_next_high_impact(10)"
        not in tail
    )


def test_run_single_session_no_longer_queries_legacy_calendar():
    src = _method_source(
        "run_single_session"
    )

    assert (
        "_pm.event_risk.hard_block_eligible"
        in src
    )

    assert (
        "minutes_to_next_high_impact(10)"
        not in src
    )


def test_legacy_calendar_is_explicitly_non_authoritative():
    src = _method_source(
        "get_enhanced_sentiment"
    )

    assert (
        "event_source_authoritative=False"
        in src
    )

    assert (
        "LEGACY UNVERIFIED ADVISORY"
        in src
    )


def test_prediction_ledger_signature_preserves_config_version_position():
    signature = inspect.signature(
        PredictionLedger.build_record
    )

    params = list(
        signature.parameters
    )

    assert params[-2:] == [
        "config_version",
        "premarket_state",
    ]


def test_prediction_record_contains_premarket_state(tmp_path):
    ledger = PredictionLedger(
        "NIFTY",
        base_dir=str(
            tmp_path
        ),
    )

    premarket = {
        "schema_version":
        "pre_market_state.v2",
        "market_symbol":
        "NIFTY",
        "execution_mode":
        "PAPER",
    }

    record = ledger.build_record(
        **_ledger_kwargs(),
        premarket_state=premarket,
    )

    assert (
        record["premarket_state"]
        == premarket
    )


def test_premarket_does_not_change_prediction_fingerprint(tmp_path):
    ledger = PredictionLedger(
        "NIFTY",
        base_dir=str(
            tmp_path
        ),
    )

    kwargs = _ledger_kwargs()

    without_pm = ledger.build_record(
        **kwargs,
        premarket_state=None,
    )

    with_pm = ledger.build_record(
        **kwargs,
        premarket_state={
            "schema_version":
            "pre_market_state.v2",
        },
    )

    assert (
        without_pm["fingerprint"]
        == with_pm["fingerprint"]
    )


def test_runtime_serializes_premarket_state_before_persistence():
    src = _method_source(
        "_persist_prediction"
    )

    assert (
        "asdict(_premarket_state)"
        in src
    )

    assert (
        "premarket_state=_premarket_payload"
        in src
    )


def test_ledger_has_exactly_one_premarket_field():
    text = LEDGER_PATH.read_text(
        encoding="utf-8",
    )

    assert (
        text.count(
            '"premarket_state": premarket_state,'
        )
        == 1
    )
