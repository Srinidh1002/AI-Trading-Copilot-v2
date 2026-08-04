"""Canonical deterministic option-chain intelligence pipeline.

This pipeline consumes an already-normalized option-chain snapshot and its
linked P5-5A quality result.

It calculates each P5-5B metric exactly once and aggregates them into one
OptionChainIntelligenceResultV1.

It does not:

- fetch provider data
- normalize provider records
- cache responses
- select option contracts
- rank opportunities
- produce BUY, SELL, HOLD, or WAIT
- calculate trade risk
- execute orders
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from services.contracts.option_chain_intelligence_policy_v1 import (
    DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY,
    OptionChainIntelligencePolicyV1,
)
from services.contracts.option_chain_intelligence_result_v1 import (
    OptionChainIntelligenceResultV1,
)
from services.contracts.option_chain_quality_result_v1 import (
    OptionChainQualityResultV1,
)
from services.contracts.option_chain_snapshot_v1 import (
    OptionChainSnapshotV1,
)
from services.option_chain_intelligence.aggregation import (
    aggregate_option_chain_intelligence,
)
from services.option_chain_intelligence.iv_skew import (
    calculate_iv_skew,
)
from services.option_chain_intelligence.max_pain import (
    calculate_max_pain,
)
from services.option_chain_intelligence.oi_buildup import (
    calculate_oi_buildup,
)
from services.option_chain_intelligence.oi_concentration import (
    calculate_oi_concentration,
)
from services.option_chain_intelligence.pcr import (
    calculate_pcr_metrics,
)
from services.option_chain_intelligence.support_resistance import (
    analyze_support_resistance,
)


def build_unavailable_option_chain_intelligence(
    *,
    underlying_symbol: str,
    exchange: str,
    option_exchange: str,
    evaluated_at: datetime,
    blockers: tuple[str, ...],
    warnings: tuple[str, ...] = (),
    reasons: tuple[str, ...] = (),
    source_status: str = "UNAVAILABLE",
    option_chain_intelligence_result_id_factory: Callable[[], str] | None = None,
) -> OptionChainIntelligenceResultV1:
    """Produce truthful canonical evidence when no option snapshot exists."""
    identity = (str(underlying_symbol).upper(), str(exchange).upper(), str(option_exchange).upper())
    if identity not in {("NIFTY", "NSE", "NFO"), ("SENSEX", "BSE", "BFO")}:
        raise ValueError("unsupported certified option identity")
    if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise ValueError("evaluated_at")
    if not blockers:
        raise ValueError("unavailable option intelligence requires blockers")
    result_id = (option_chain_intelligence_result_id_factory or (lambda: f"unavailable-option-intelligence:{identity[0]}:{evaluated_at.isoformat()}"))()
    return OptionChainIntelligenceResultV1(
        option_chain_intelligence_result_id=result_id, created_at=evaluated_at,
        option_chain_snapshot_id=None, option_chain_quality_result_id=None,
        underlying_symbol=identity[0], exchange=identity[1], expiry=None,
        metrics=(), intelligence_status="UNAVAILABLE", aggregate_bias="UNAVAILABLE",
        aggregate_strength=0.0, bullish_metrics=(), bearish_metrics=(), neutral_metrics=(),
        unavailable_metrics=(), valid_metric_count=0, unavailable_metric_count=0,
        blockers=tuple(blockers), warnings=tuple(warnings), reasons=tuple(reasons),
        source_status=source_status,
    )


def build_canonical_option_chain_intelligence(
    *,
    snapshot: OptionChainSnapshotV1,
    quality_result: OptionChainQualityResultV1,
    policy: OptionChainIntelligencePolicyV1 = (
        DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY
    ),
    clock: Callable[[], datetime] | None = None,
    option_chain_intelligence_result_id_factory: (
        Callable[[], str] | None
    ) = None,
) -> OptionChainIntelligenceResultV1:
    """Build canonical P5-5B option-chain intelligence.

    Metric order is fixed and must remain:

    1. PCR_OPEN_INTEREST
    2. PCR_VOLUME
    3. OI_CONCENTRATION
    4. OI_BUILDUP
    5. MAX_PAIN
    6. IV_SKEW
    7. SUPPORT_RESISTANCE
    """

    if not isinstance(snapshot, OptionChainSnapshotV1):
        raise TypeError(
            "snapshot must be an OptionChainSnapshotV1"
        )

    if not isinstance(
        quality_result,
        OptionChainQualityResultV1,
    ):
        raise TypeError(
            "quality_result must be an "
            "OptionChainQualityResultV1"
        )

    if not isinstance(
        policy,
        OptionChainIntelligencePolicyV1,
    ):
        raise TypeError(
            "policy must be an "
            "OptionChainIntelligencePolicyV1"
        )

    if (
        quality_result.option_chain_snapshot_id
        != snapshot.option_chain_snapshot_id
    ):
        raise ValueError(
            "quality result must reference the supplied snapshot"
        )

    if (
        quality_result.underlying_symbol
        != snapshot.underlying_symbol
        or quality_result.exchange != snapshot.exchange
        or quality_result.expiry != snapshot.expiry
    ):
        raise ValueError(
            "snapshot and quality-result identities must match"
        )

    open_interest_pcr, volume_pcr = calculate_pcr_metrics(
        snapshot=snapshot,
        policy=policy,
    )

    oi_concentration = calculate_oi_concentration(
        snapshot=snapshot,
        policy=policy,
    )

    oi_buildup = calculate_oi_buildup(
        snapshot=snapshot,
        policy=policy,
    )

    max_pain = calculate_max_pain(
        snapshot=snapshot,
        policy=policy,
    )

    iv_skew = calculate_iv_skew(
        snapshot=snapshot,
        policy=policy,
    )

    support_resistance = analyze_support_resistance(
        snapshot=snapshot,
        policy=policy,
    )

    metrics = (
        open_interest_pcr,
        volume_pcr,
        oi_concentration,
        oi_buildup,
        max_pain,
        iv_skew,
        support_resistance.metric,
    )

    max_pain_strike = (
        max_pain.value
        if max_pain.status
        in {"VALID", "VALID_WITH_WARNINGS"}
        else None
    )

    return aggregate_option_chain_intelligence(
        snapshot=snapshot,
        quality_result=quality_result,
        metrics=metrics,
        support_strikes=support_resistance.support_strikes,
        resistance_strikes=(
            support_resistance.resistance_strikes
        ),
        max_pain_strike=max_pain_strike,
        policy=policy,
        clock=clock,
        option_chain_intelligence_result_id_factory=(
            option_chain_intelligence_result_id_factory
        ),
    )


__all__ = [
    "build_canonical_option_chain_intelligence",
    "build_unavailable_option_chain_intelligence",
]
