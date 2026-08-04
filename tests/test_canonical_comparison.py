from datetime import datetime

from services.canonical.comparison import (
    compare_live_option_legacy_to_canonical,
)
from services.canonical.comparison_models import (
    CanonicalLegacyComparison,
    ComparisonDifference,
)


def test_live_option_comparison_is_diagnostic_and_side_effect_free_for_supplied_data():
    comparison = compare_live_option_legacy_to_canonical(
        {"decision": "NO_TRADE"},
        symbol="NIFTY",
        exchange="NSE",
        market_timestamp=datetime.fromisoformat("2026-07-10T10:00:00+05:30"),
        ltp=25000,
        timeframes={},
        reference_time="2026-07-10T10:00:00+05:30",
    )

    assert comparison.source == "live_option"
    assert comparison.canonical_decision is not None
    assert comparison.canonical_decision.execution_status == "NOT_REQUESTED"
    assert comparison.canonical_decision.authorization_status == "BLOCKED"


def test_comparison_serialization_is_deterministic():
    comparison = CanonicalLegacyComparison(
        source="test",
        differences=(
            ComparisonDifference(
                category="action",
                legacy_value="BUY",
                canonical_value="WAIT",
            ),
        ),
    )

    assert comparison.to_json() == comparison.to_json()
