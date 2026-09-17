"""Provider-neutral canonical option-chain intelligence APIs."""

from __future__ import annotations

from .aggregation import aggregate_option_chain_intelligence
from .intelligence_pipeline import (
    build_canonical_option_chain_intelligence,
)
from .iv_skew import (
    IV_SKEW_METRIC_NAME,
    calculate_iv_skew,
)
from .max_pain import (
    MAX_PAIN_METRIC_NAME,
    calculate_max_pain,
)
from .normalization import (
    CANONICAL_OPTION_CHAIN_RECORD_KEYS,
    normalize_option_chain_records,
)
from .oi_buildup import (
    OI_BUILDUP_METRIC_NAME,
    calculate_oi_buildup,
)
from .oi_concentration import (
    OI_CONCENTRATION_METRIC_NAME,
    calculate_oi_concentration,
)
from .pcr import (
    PCR_OPEN_INTEREST_METRIC_NAME,
    PCR_VOLUME_METRIC_NAME,
    calculate_open_interest_pcr,
    calculate_pcr_metrics,
    calculate_volume_pcr,
)
from .pipeline import build_canonical_option_chain_foundation
from .quality import evaluate_option_chain_quality
from .support_resistance import (
    SUPPORT_RESISTANCE_METRIC_NAME,
    SupportResistanceAnalysis,
    analyze_support_resistance,
    calculate_support_resistance,
)


__all__ = (
    # P5-5A foundation
    "CANONICAL_OPTION_CHAIN_RECORD_KEYS",
    "DEFAULT_OPTION_CHAIN_POLICY",
    "normalize_option_chain_records",
    "evaluate_option_chain_quality",
    "build_canonical_option_chain_foundation",

    # P5-5B policy and contracts
    "DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY",

    # PCR
    "PCR_OPEN_INTEREST_METRIC_NAME",
    "PCR_VOLUME_METRIC_NAME",
    "calculate_open_interest_pcr",
    "calculate_volume_pcr",
    "calculate_pcr_metrics",

    # Open interest
    "OI_CONCENTRATION_METRIC_NAME",
    "calculate_oi_concentration",
    "OI_BUILDUP_METRIC_NAME",
    "calculate_oi_buildup",

    # Max pain and IV skew
    "MAX_PAIN_METRIC_NAME",
    "calculate_max_pain",
    "IV_SKEW_METRIC_NAME",
    "calculate_iv_skew",

    # Support and resistance
    "SUPPORT_RESISTANCE_METRIC_NAME",
    "SupportResistanceAnalysis",
    "analyze_support_resistance",
    "calculate_support_resistance",

    # Aggregation and canonical pipeline
    "aggregate_option_chain_intelligence",
    "build_canonical_option_chain_intelligence",
)


def __getattr__(name: str):
    """Resolve policy constants lazily."""

    if name == "DEFAULT_OPTION_CHAIN_POLICY":
        from services.contracts.option_chain_policy_v1 import (
            DEFAULT_OPTION_CHAIN_POLICY,
        )

        globals()[name] = DEFAULT_OPTION_CHAIN_POLICY
        return DEFAULT_OPTION_CHAIN_POLICY

    if name == "DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY":
        from services.contracts.option_chain_intelligence_policy_v1 import (
            DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY,
        )

        globals()[name] = DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY
        return DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY

    raise AttributeError(name)