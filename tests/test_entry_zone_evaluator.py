from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.contracts import EntryZoneEvaluationInputV1
from services.trade_planning.entry_zone_evaluator import evaluate_entry_zone
from tests.test_trade_planning_policy_v1 import _p


EVALUATED_AT = datetime(2026, 1, 2, 9, 15, tzinfo=timezone.utc)
QUOTE_AT = datetime(2026, 1, 2, 9, 14, tzinfo=timezone.utc)
SOURCE_AT = datetime(2026, 1, 2, 9, 13, tzinfo=timezone.utc)


def _input(**overrides: object) -> EntryZoneEvaluationInputV1:
    values: dict[str, object] = {
        "evaluation_id": "entry-evaluation-1",
        "evaluation_result_id": "entry-result-1",
        "evaluated_at": EVALUATED_AT,
        "underlying_symbol": "NIFTY",
        "exchange": "NSE",
        "trade_plan_input_id": "trade-plan-input-1",
        "policy_id": "P",
        "direction": "BULLISH",
        "option_right": "CALL",
        "entry_reference_method": "OPTION_MID",
        "last_traded_price": 100.0,
        "bid_price": 99.0,
        "ask_price": 101.0,
        "signal_reference_price": 100.0,
        "option_mid_price": 100.0,
        "option_quote_timestamp": QUOTE_AT,
        "maximum_entry_premium": None,
        "maximum_spread_fraction": None,
        "planning_allowed": True,
        "blockers": (),
        "warnings": (),
        "source_timestamps": {},
        "metadata": {},
        "execution_mode": "PAPER",
        "live_execution_eligible": False,
        "schema_version": "1.0",
    }
    values.update(overrides)
    return EntryZoneEvaluationInputV1(**values)


def _policy(**overrides: object):
    return _p(**overrides)


def test_rejects_wrong_exact_types() -> None:
    with pytest.raises(TypeError):
        evaluate_entry_zone({}, _policy())
    with pytest.raises(TypeError):
        evaluate_entry_zone(_input(), {})


def test_policy_id_and_method_mismatch_block_without_geometry() -> None:
    policy_id_mismatch = evaluate_entry_zone(_input(policy_id="other"), _policy())
    method_mismatch = evaluate_entry_zone(_input(entry_reference_method="OPTION_ASK"), _policy())

    for result in (policy_id_mismatch, method_mismatch):
        assert result.status == "BLOCKED"
        assert result.blockers == ("ENTRY_POLICY_MISMATCH",)
        assert result.selected_reference_source is None
        assert result.entry_reference_price is None
        assert result.effective_spread_fraction is None
        assert result.maximum_entry_premium is None


def test_early_planning_blocks_preserve_order_and_skip_geometry() -> None:
    result = evaluate_entry_zone(
        _input(
            planning_allowed=False,
            blockers=("INPUT_ONE", "INPUT_TWO", "INPUT_ONE"),
            policy_id="other",
        ),
        _policy(),
    )

    assert result.status == "BLOCKED"
    assert result.blockers == (
        "INPUT_ONE",
        "INPUT_TWO",
        "ENTRY_PLANNING_NOT_ALLOWED",
        "ENTRY_POLICY_MISMATCH",
    )
    assert result.selected_reference_source is None
    assert result.entry_reference_price is None
    assert result.entry_zone_lower is None
    assert result.effective_spread_fraction is None
    assert result.effective_spread_limit is None


@pytest.mark.parametrize(
    ("entry_method", "selected_source"),
    (
        ("OPTION_MID", "OPTION_MID"),
        ("OPTION_ASK", "OPTION_ASK"),
        ("LAST_TRADED_PRICE", "LAST_TRADED_PRICE"),
        ("SIGNAL_REFERENCE", "SIGNAL_REFERENCE"),
    ),
)
def test_non_hybrid_reference_methods_select_their_exact_source(
    entry_method: str,
    selected_source: str,
) -> None:
    result = evaluate_entry_zone(
        _input(entry_reference_method=entry_method),
        _policy(entry_reference_method=entry_method),
    )

    assert result.status == "READY"
    assert result.entry_method == entry_method
    assert result.selected_reference_source == selected_source
    expected_reference_price = 101.0 if selected_source == "OPTION_ASK" else 100.0
    assert result.entry_reference_price == expected_reference_price


@pytest.mark.parametrize(
    ("entry_method", "missing_field"),
    (
        ("OPTION_MID", "option_mid_price"),
        ("OPTION_ASK", "ask_price"),
        ("LAST_TRADED_PRICE", "last_traded_price"),
        ("SIGNAL_REFERENCE", "signal_reference_price"),
    ),
)
def test_non_hybrid_missing_required_reference_blocks(
    entry_method: str,
    missing_field: str,
) -> None:
    result = evaluate_entry_zone(
        _input(entry_reference_method=entry_method, **{missing_field: None}),
        _policy(entry_reference_method=entry_method),
    )

    assert result.status == "BLOCKED"
    assert result.blockers == ("ENTRY_REFERENCE_UNAVAILABLE",)
    assert result.selected_reference_source is None
    assert result.entry_reference_price is None


@pytest.mark.parametrize(
    ("overrides", "selected_source", "reference_price", "expected_warnings"),
    (
        ({}, "OPTION_MID", 100.0, ()),
        ({"option_mid_price": None}, "OPTION_ASK", 101.0, ("ENTRY_HYBRID_FALLBACK_USED",)),
        (
            {"option_mid_price": None, "ask_price": None},
            "LAST_TRADED_PRICE",
            100.0,
            ("ENTRY_HYBRID_FALLBACK_USED",),
        ),
        (
            {"option_mid_price": None, "ask_price": None, "last_traded_price": None},
            "SIGNAL_REFERENCE",
            100.0,
            ("ENTRY_HYBRID_FALLBACK_USED",),
        ),
    ),
)
def test_hybrid_priority_and_fallback_warning(
    overrides: dict[str, object],
    selected_source: str,
    reference_price: float,
    expected_warnings: tuple[str, ...],
) -> None:
    result = evaluate_entry_zone(
        _input(entry_reference_method="HYBRID", **overrides),
        _policy(entry_reference_method="HYBRID"),
    )

    assert result.status == "READY"
    assert result.selected_reference_source == selected_source
    assert result.entry_reference_price == reference_price
    assert result.warnings == expected_warnings


def test_hybrid_retains_input_warning_before_single_fallback_and_never_averages() -> None:
    result = evaluate_entry_zone(
        _input(
            entry_reference_method="HYBRID",
            option_mid_price=None,
            ask_price=110.0,
            warnings=("INPUT_WARNING", "ENTRY_HYBRID_FALLBACK_USED"),
        ),
        _policy(entry_reference_method="HYBRID"),
    )

    assert result.entry_reference_price == 110.0
    assert result.warnings == ("INPUT_WARNING", "ENTRY_HYBRID_FALLBACK_USED")


def test_hybrid_without_any_source_blocks() -> None:
    result = evaluate_entry_zone(
        _input(
            entry_reference_method="HYBRID",
            option_mid_price=None,
            ask_price=None,
            last_traded_price=None,
            signal_reference_price=None,
        ),
        _policy(entry_reference_method="HYBRID"),
    )

    assert result.status == "BLOCKED"
    assert result.blockers == ("ENTRY_REFERENCE_UNAVAILABLE",)
    assert result.selected_reference_source is None


def test_symmetric_and_asymmetric_geometry_formulas_and_properties() -> None:
    symmetric = evaluate_entry_zone(_input(), _policy())
    asymmetric = evaluate_entry_zone(
        _input(),
        _policy(
            entry_tolerance_below_fraction=0.02,
            entry_tolerance_above_fraction=0.03,
            maximum_chase_fraction=0.04,
        ),
    )

    assert (symmetric.entry_zone_lower, symmetric.entry_zone_upper, symmetric.maximum_chase_price) == (99.0, 101.0, 102.0)
    assert (asymmetric.entry_zone_lower, asymmetric.entry_zone_upper, asymmetric.maximum_chase_price) == (98.0, 103.0, 104.0)
    assert asymmetric.entry_tolerance_fraction == 0.03
    assert asymmetric.zone_width == 5.0
    assert asymmetric.lower_distance_fraction == 0.02
    assert asymmetric.upper_distance_fraction == 0.03


def test_zero_tolerances_and_chase_follow_policy_formulas() -> None:
    zero_lower = evaluate_entry_zone(
        _input(),
        _policy(entry_tolerance_below_fraction=0.0, entry_tolerance_above_fraction=0.01),
    )
    zero_upper = evaluate_entry_zone(
        _input(),
        _policy(entry_tolerance_below_fraction=0.01, entry_tolerance_above_fraction=0.0),
    )
    zero_chase = evaluate_entry_zone(
        _input(),
        _policy(
            entry_tolerance_below_fraction=0.01,
            entry_tolerance_above_fraction=0.0,
            maximum_chase_fraction=0.0,
        ),
    )

    assert zero_lower.entry_zone_lower == 100.0
    assert zero_upper.entry_zone_upper == 100.0
    assert zero_chase.maximum_chase_price == 100.0


def test_require_limit_entry_and_repeated_outputs_are_deterministic() -> None:
    evaluation_input = _input(source_timestamps={"quote": QUOTE_AT}, metadata={"source": "fixture"})
    policy = _policy(require_limit_entry=False)
    first = evaluate_entry_zone(evaluation_input, policy)
    second = evaluate_entry_zone(evaluation_input, policy)

    assert first.require_limit_entry is False
    assert first == second
    assert first.to_json() == second.to_json()


def test_effective_premium_limit_selection_and_exact_boundary_acceptance() -> None:
    no_cap = evaluate_entry_zone(_input(), _policy(maximum_entry_premium=None))
    input_only = evaluate_entry_zone(_input(maximum_entry_premium=110.0), _policy(maximum_entry_premium=None))
    policy_only = evaluate_entry_zone(_input(), _policy(maximum_entry_premium=110.0))
    input_stricter = evaluate_entry_zone(_input(maximum_entry_premium=110.0), _policy(maximum_entry_premium=120.0))
    policy_stricter = evaluate_entry_zone(_input(maximum_entry_premium=120.0), _policy(maximum_entry_premium=110.0))
    equal = evaluate_entry_zone(_input(maximum_entry_premium=110.0), _policy(maximum_entry_premium=110.0))
    exact_reference = evaluate_entry_zone(
        _input(maximum_entry_premium=100.0),
        _policy(
            maximum_entry_premium=None,
            entry_tolerance_below_fraction=0.01,
            entry_tolerance_above_fraction=0.0,
            maximum_chase_fraction=0.0,
        ),
    )
    exact_upper = evaluate_entry_zone(
        _input(maximum_entry_premium=101.0),
        _policy(
            maximum_entry_premium=None,
            entry_tolerance_below_fraction=0.01,
            entry_tolerance_above_fraction=0.01,
            maximum_chase_fraction=0.01,
        ),
    )
    exact_chase = evaluate_entry_zone(
        _input(maximum_entry_premium=102.0),
        _policy(
            maximum_entry_premium=None,
            entry_tolerance_below_fraction=0.01,
            entry_tolerance_above_fraction=0.0,
            maximum_chase_fraction=0.02,
        ),
    )

    assert no_cap.maximum_entry_premium is None
    assert [item.maximum_entry_premium for item in (input_only, policy_only, input_stricter, policy_stricter, equal)] == [110.0] * 5
    assert all(item.status == "READY" for item in (exact_reference, exact_upper, exact_chase))


@pytest.mark.parametrize(
    ("policy_overrides", "input_cap"),
    (
        (
            {
                "entry_tolerance_below_fraction": 0.01,
                "entry_tolerance_above_fraction": 0.0,
                "maximum_chase_fraction": 0.0,
                "maximum_entry_premium": None,
            },
            99.0,
        ),
        (
            {
                "entry_tolerance_below_fraction": 0.01,
                "entry_tolerance_above_fraction": 0.01,
                "maximum_chase_fraction": 0.01,
                "maximum_entry_premium": None,
            },
            100.0,
        ),
        (
            {
                "entry_tolerance_below_fraction": 0.01,
                "entry_tolerance_above_fraction": 0.0,
                "maximum_chase_fraction": 0.02,
                "maximum_entry_premium": None,
            },
            100.0,
        ),
    ),
)
def test_reference_upper_and_chase_premium_breaches_preserve_geometry(
    policy_overrides: dict[str, object],
    input_cap: float,
) -> None:
    result = evaluate_entry_zone(_input(maximum_entry_premium=input_cap), _policy(**policy_overrides))

    assert result.status == "BLOCKED"
    assert result.blockers == ("ENTRY_PREMIUM_LIMIT_EXCEEDED",)
    assert result.entry_reference_price == 100.0
    assert result.entry_zone_lower is not None
    assert result.maximum_chase_price is not None


def test_effective_spread_limit_and_basis_behavior() -> None:
    absent = evaluate_entry_zone(_input(bid_price=None, ask_price=None), _policy(maximum_spread_fraction=0.1))
    valid = evaluate_entry_zone(_input(), _policy(maximum_spread_fraction=0.1))
    exact = evaluate_entry_zone(_input(maximum_spread_fraction=0.02), _policy(maximum_spread_fraction=0.1))
    input_stricter = evaluate_entry_zone(_input(maximum_spread_fraction=0.03), _policy(maximum_spread_fraction=0.1))
    policy_stricter = evaluate_entry_zone(_input(maximum_spread_fraction=0.1), _policy(maximum_spread_fraction=0.03))
    equal = evaluate_entry_zone(_input(maximum_spread_fraction=0.05), _policy(maximum_spread_fraction=0.05))
    mid_basis = evaluate_entry_zone(
        _input(entry_reference_method="OPTION_ASK", bid_price=99.0, ask_price=110.0, option_mid_price=100.0),
        _policy(entry_reference_method="OPTION_ASK", maximum_spread_fraction=0.12),
    )
    selected_reference_basis = evaluate_entry_zone(
        _input(entry_reference_method="OPTION_ASK", bid_price=99.0, ask_price=101.0, option_mid_price=None),
        _policy(entry_reference_method="OPTION_ASK", maximum_spread_fraction=0.1),
    )

    assert (absent.effective_spread_fraction, absent.effective_spread_limit) == (None, 0.1)
    assert valid.effective_spread_fraction == 0.02
    assert exact.status == "READY"
    assert [item.effective_spread_limit for item in (input_stricter, policy_stricter, equal)] == [0.03, 0.03, 0.05]
    assert mid_basis.effective_spread_fraction == 0.11
    assert selected_reference_basis.effective_spread_fraction == pytest.approx(2 / 101)


def test_spread_breach_and_multiple_breach_order_preserve_geometry() -> None:
    spread_only = evaluate_entry_zone(
        _input(maximum_spread_fraction=0.01),
        _policy(maximum_spread_fraction=0.1),
    )
    both = evaluate_entry_zone(
        _input(maximum_entry_premium=100.0, maximum_spread_fraction=0.01),
        _policy(maximum_entry_premium=None, maximum_spread_fraction=0.1),
    )

    assert spread_only.status == "BLOCKED"
    assert spread_only.blockers == ("ENTRY_SPREAD_LIMIT_EXCEEDED",)
    assert spread_only.entry_zone_upper == 101.0
    assert both.blockers == ("ENTRY_PREMIUM_LIMIT_EXCEEDED", "ENTRY_SPREAD_LIMIT_EXCEEDED")


def test_duplicate_input_blocker_is_preserved_once_on_early_block() -> None:
    result = evaluate_entry_zone(
        _input(blockers=("ENTRY_PREMIUM_LIMIT_EXCEEDED", "ENTRY_PREMIUM_LIMIT_EXCEEDED")),
        _policy(maximum_entry_premium=99.0),
    )

    assert result.status == "BLOCKED"
    assert result.blockers == ("ENTRY_PREMIUM_LIMIT_EXCEEDED",)
    assert result.entry_reference_price is None


def test_result_fields_provenance_and_paper_values_are_populated() -> None:
    evaluation_input = _input(
        source_timestamps={"quote": QUOTE_AT, "analysis": SOURCE_AT},
        metadata={"fixture": {"name": "entry"}},
    )
    result = evaluate_entry_zone(evaluation_input, _policy())

    assert (result.evaluation_result_id, result.evaluation_id, result.evaluated_at) == (
        evaluation_input.evaluation_result_id,
        evaluation_input.evaluation_id,
        evaluation_input.evaluated_at,
    )
    assert (result.underlying_symbol, result.exchange, result.direction, result.option_right) == (
        "NIFTY",
        "NSE",
        "BULLISH",
        "CALL",
    )
    assert dict(result.source_timestamps) == dict(evaluation_input.source_timestamps)
    assert result.metadata["input_metadata"] == {"fixture": {"name": "entry"}}
    assert result.metadata["selected_reference_source"] == "OPTION_MID"
    assert result.metadata["quote_timestamp"] == QUOTE_AT.isoformat()
    assert result.metadata["trade_plan_input_id"] == "trade-plan-input-1"
    assert result.metadata["policy_id"] == "P"
    assert (result.execution_mode, result.live_execution_eligible, result.schema_version) == ("PAPER", False, "1.0")


def test_evaluator_emits_only_ready_or_blocked_for_current_policy() -> None:
    ready = evaluate_entry_zone(_input(), _policy())
    blocked = evaluate_entry_zone(_input(option_mid_price=None), _policy())

    assert (ready.status, blocked.status) == ("READY", "BLOCKED")
    assert "NO_ENTRY" not in {ready.status, blocked.status}
