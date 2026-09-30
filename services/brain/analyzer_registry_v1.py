"""Analyzer Registry V1 for the isolated Brain architecture.

The registry describes analyzer families discovered during B1.

It intentionally stores metadata only:
- no provider calls;
- no broker calls;
- no trade decisions;
- no risk overrides;
- no position management;
- no certification mutation.

Registration is not authority.
"""

from __future__ import annotations

from dataclasses import dataclass


SUPPORTED_MARKETS = frozenset(
    {
        "NIFTY",
        "SENSEX",
        "CRUDEOILM",
        "GOLDM",
        "NATGASMINI",
    }
)


ANALYZER_CATEGORIES = frozenset(
    {
        "PREMARKET",
        "EXTERNAL",
        "VOLATILITY",
        "FLOW",
        "NEWS",
        "EVENT",
        "BREADTH",
        "TECHNICAL",
        "REGIME",
        "OPTIONS",
        "STRUCTURE",
        "POSITIONING",
    }
)


RUNTIME_ROLES = frozenset(
    {
        "PRODUCTION_INPUT",
        "SHADOW_AVAILABLE",
    }
)


SOURCE_FAMILIES = frozenset(
    {
        "INDEX_LEGACY",
        "MCX_NATIVE",
        "CANONICAL_TECHNICAL",
    }
)


def _require_text(
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value.strip()
        or value != value.strip()
    ):
        raise ValueError(
            f"{name} must be a non-empty trimmed string."
        )

    return value


def _require_string_tuple(
    name: str,
    values: object,
) -> tuple[str, ...]:
    if not isinstance(
        values,
        tuple,
    ):
        raise ValueError(
            f"{name} must be a tuple."
        )

    if not values:
        raise ValueError(
            f"{name} must not be empty."
        )

    if any(
        not isinstance(
            value,
            str,
        )
        or not value.strip()
        or value != value.strip()
        for value in values
    ):
        raise ValueError(
            f"{name} entries must be non-empty trimmed strings."
        )

    if len(
        set(
            values
        )
    ) != len(
        values
    ):
        raise ValueError(
            f"{name} must not contain duplicates."
        )

    return values


@dataclass(
    frozen=True,
    slots=True,
)
class AnalyzerDescriptorV1:
    """Metadata for one analyzer family.

    ``currently_consumed_by_production`` records B1 discovery only.  It does
    not grant this registry authority over the production decision.

    All authority fields are permanently false in V1.
    """

    analyzer_id: str
    analyzer_version: str

    category: str
    markets: tuple[str, ...]

    source_family: str
    runtime_role: str

    currently_consumed_by_production: bool

    requires_adapter: bool = True

    output_contract: str = "AnalyzerResultV1"

    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False

    notes: tuple[str, ...] = ()

    schema_version: str = "BRAIN_ANALYZER_DESCRIPTOR_V1"

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "analyzer_id",
            "analyzer_version",
            "source_family",
            "runtime_role",
            "output_contract",
            "schema_version",
        ):
            _require_text(
                name,
                getattr(
                    self,
                    name,
                ),
            )

        if self.category not in ANALYZER_CATEGORIES:
            raise ValueError(
                f"unsupported analyzer category: {self.category}"
            )

        _require_string_tuple(
            "markets",
            self.markets,
        )

        unsupported = set(
            self.markets
        ) - SUPPORTED_MARKETS

        if unsupported:
            raise ValueError(
                f"unsupported markets: {sorted(unsupported)}"
            )

        if self.source_family not in SOURCE_FAMILIES:
            raise ValueError(
                f"unsupported source family: {self.source_family}"
            )

        if self.runtime_role not in RUNTIME_ROLES:
            raise ValueError(
                f"unsupported runtime role: {self.runtime_role}"
            )

        if not isinstance(
            self.currently_consumed_by_production,
            bool,
        ):
            raise ValueError(
                "currently_consumed_by_production must be bool."
            )

        if not isinstance(
            self.requires_adapter,
            bool,
        ):
            raise ValueError(
                "requires_adapter must be bool."
            )

        if self.output_contract != "AnalyzerResultV1":
            raise ValueError(
                "AnalyzerDescriptorV1 output_contract must be AnalyzerResultV1."
            )

        for name in (
            "execution_authority",
            "risk_authority",
            "position_authority",
            "certification_authority",
        ):
            if getattr(
                self,
                name,
            ) is not False:
                raise ValueError(
                    f"{name} is permanently False in AnalyzerDescriptorV1."
                )

        if (
            self.runtime_role == "SHADOW_AVAILABLE"
            and self.currently_consumed_by_production
        ):
            raise ValueError(
                "SHADOW_AVAILABLE analyzers cannot be marked as "
                "currently consumed by production."
            )

        if not isinstance(
            self.notes,
            tuple,
        ):
            raise ValueError(
                "notes must be a tuple."
            )

        if any(
            not isinstance(
                note,
                str,
            )
            or not note.strip()
            or note != note.strip()
            for note in self.notes
        ):
            raise ValueError(
                "notes entries must be non-empty trimmed strings."
            )

    def to_dict(
        self,
    ) -> dict[str, object]:
        return {
            "schema_version":
                self.schema_version,

            "analyzer_id":
                self.analyzer_id,

            "analyzer_version":
                self.analyzer_version,

            "category":
                self.category,

            "markets":
                list(
                    self.markets
                ),

            "source_family":
                self.source_family,

            "runtime_role":
                self.runtime_role,

            "currently_consumed_by_production":
                self.currently_consumed_by_production,

            "requires_adapter":
                self.requires_adapter,

            "output_contract":
                self.output_contract,

            "execution_authority":
                False,

            "risk_authority":
                False,

            "position_authority":
                False,

            "certification_authority":
                False,

            "notes":
                list(
                    self.notes
                ),
        }


@dataclass(
    frozen=True,
    slots=True,
)
class AnalyzerRegistryV1:
    """Immutable analyzer metadata registry."""

    descriptors: tuple[
        AnalyzerDescriptorV1,
        ...,
    ]

    schema_version: str = "BRAIN_ANALYZER_REGISTRY_V1"

    def __post_init__(
        self,
    ) -> None:
        _require_text(
            "schema_version",
            self.schema_version,
        )

        if not isinstance(
            self.descriptors,
            tuple,
        ):
            raise ValueError(
                "descriptors must be a tuple."
            )

        if not self.descriptors:
            raise ValueError(
                "registry must contain at least one descriptor."
            )

        seen: set[str] = set()

        for descriptor in self.descriptors:
            if not isinstance(
                descriptor,
                AnalyzerDescriptorV1,
            ):
                raise ValueError(
                    "registry entries must be AnalyzerDescriptorV1."
                )

            if descriptor.analyzer_id in seen:
                raise ValueError(
                    f"duplicate analyzer_id: {descriptor.analyzer_id}"
                )

            seen.add(
                descriptor.analyzer_id
            )

    def get(
        self,
        analyzer_id: str,
    ) -> AnalyzerDescriptorV1:
        _require_text(
            "analyzer_id",
            analyzer_id,
        )

        for descriptor in self.descriptors:
            if descriptor.analyzer_id == analyzer_id:
                return descriptor

        raise KeyError(
            analyzer_id
        )

    def for_market(
        self,
        market: str,
    ) -> tuple[
        AnalyzerDescriptorV1,
        ...,
    ]:
        _require_text(
            "market",
            market,
        )

        if market not in SUPPORTED_MARKETS:
            raise ValueError(
                f"unsupported market: {market}"
            )

        return tuple(
            descriptor
            for descriptor in self.descriptors
            if market in descriptor.markets
        )

    def by_category(
        self,
        category: str,
    ) -> tuple[
        AnalyzerDescriptorV1,
        ...,
    ]:
        if category not in ANALYZER_CATEGORIES:
            raise ValueError(
                f"unsupported analyzer category: {category}"
            )

        return tuple(
            descriptor
            for descriptor in self.descriptors
            if descriptor.category == category
        )

    def production_inputs(
        self,
        market: str | None = None,
    ) -> tuple[
        AnalyzerDescriptorV1,
        ...,
    ]:
        if market is None:
            values = self.descriptors

        else:
            values = self.for_market(
                market
            )

        return tuple(
            descriptor
            for descriptor in values
            if descriptor.currently_consumed_by_production
        )

    def shadow_available(
        self,
        market: str | None = None,
    ) -> tuple[
        AnalyzerDescriptorV1,
        ...,
    ]:
        if market is None:
            values = self.descriptors

        else:
            values = self.for_market(
                market
            )

        return tuple(
            descriptor
            for descriptor in values
            if descriptor.runtime_role == "SHADOW_AVAILABLE"
        )

    def to_dict(
        self,
    ) -> dict[str, object]:
        return {
            "schema_version":
                self.schema_version,

            "descriptors":
                [
                    descriptor.to_dict()
                    for descriptor in self.descriptors
                ],
        }


INDEX_MARKETS = (
    "NIFTY",
    "SENSEX",
)

MCX_MARKETS = (
    "CRUDEOILM",
    "GOLDM",
    "NATGASMINI",
)

ALL_MARKETS = (
    "NIFTY",
    "SENSEX",
    "CRUDEOILM",
    "GOLDM",
    "NATGASMINI",
)


DEFAULT_ANALYZER_REGISTRY_V1 = AnalyzerRegistryV1(
    descriptors=(
        AnalyzerDescriptorV1(
            analyzer_id="index.previous_session.legacy_v1",
            analyzer_version="1.0",
            category="PREMARKET",
            markets=INDEX_MARKETS,
            source_family="INDEX_LEGACY",
            runtime_role="PRODUCTION_INPUT",
            currently_consumed_by_production=True,
            notes=(
                "B1 live-proven previous-session evidence.",
            ),
        ),

        AnalyzerDescriptorV1(
            analyzer_id="index.gap.legacy_v1",
            analyzer_version="1.0",
            category="PREMARKET",
            markets=INDEX_MARKETS,
            source_family="INDEX_LEGACY",
            runtime_role="PRODUCTION_INPUT",
            currently_consumed_by_production=True,
            notes=(
                "Gap evidence derived from current session open and prior close.",
            ),
        ),

        AnalyzerDescriptorV1(
            analyzer_id="index.global_risk.legacy_v1",
            analyzer_version="1.0",
            category="EXTERNAL",
            markets=INDEX_MARKETS,
            source_family="INDEX_LEGACY",
            runtime_role="PRODUCTION_INPUT",
            currently_consumed_by_production=True,
            notes=(
                "B1 observed live global-risk evidence.",
                "Freshness authority remains a future hardening item.",
            ),
        ),

        AnalyzerDescriptorV1(
            analyzer_id="index.india_vix.legacy_v1",
            analyzer_version="1.0",
            category="VOLATILITY",
            markets=INDEX_MARKETS,
            source_family="INDEX_LEGACY",
            runtime_role="PRODUCTION_INPUT",
            currently_consumed_by_production=True,
            notes=(
                "B1 live-proven India VIX context.",
            ),
        ),

        AnalyzerDescriptorV1(
            analyzer_id="index.institutional_flow.legacy_v1",
            analyzer_version="1.0",
            category="FLOW",
            markets=INDEX_MARKETS,
            source_family="INDEX_LEGACY",
            runtime_role="PRODUCTION_INPUT",
            currently_consumed_by_production=True,
            notes=(
                "Previous-session FII/DII cash-flow evidence.",
            ),
        ),

        AnalyzerDescriptorV1(
            analyzer_id="index.news.legacy_v1",
            analyzer_version="1.0",
            category="NEWS",
            markets=INDEX_MARKETS,
            source_family="INDEX_LEGACY",
            runtime_role="PRODUCTION_INPUT",
            currently_consumed_by_production=True,
            notes=(
                "Current keyword/RSS sentiment engine.",
                "B1 observed partial 2-of-3 feed coverage.",
            ),
        ),

        AnalyzerDescriptorV1(
            analyzer_id="index.event_calendar.legacy_v1",
            analyzer_version="1.0",
            category="EVENT",
            markets=INDEX_MARKETS,
            source_family="INDEX_LEGACY",
            runtime_role="PRODUCTION_INPUT",
            currently_consumed_by_production=True,
            notes=(
                "Current production path consumes this context.",
                "B1 observed event evidence as UNVERIFIED.",
                "This descriptor does not grant hard-block authority.",
            ),
        ),

        AnalyzerDescriptorV1(
            analyzer_id="index.breadth.legacy_v1",
            analyzer_version="1.0",
            category="BREADTH",
            markets=INDEX_MARKETS,
            source_family="INDEX_LEGACY",
            runtime_role="PRODUCTION_INPUT",
            currently_consumed_by_production=True,
            notes=(
                "Index constituent/breadth evidence family.",
            ),
        ),

        AnalyzerDescriptorV1(
            analyzer_id="index.mtf.legacy_v1",
            analyzer_version="1.0",
            category="TECHNICAL",
            markets=INDEX_MARKETS,
            source_family="INDEX_LEGACY",
            runtime_role="PRODUCTION_INPUT",
            currently_consumed_by_production=True,
            notes=(
                "B1 proved production reaches src/mtf_enhanced.py.",
                "Contains EMA/RSI/MACD/ADX/Bollinger-related logic.",
            ),
        ),

        AnalyzerDescriptorV1(
            analyzer_id="index.regime.legacy_v1",
            analyzer_version="1.0",
            category="REGIME",
            markets=INDEX_MARKETS,
            source_family="INDEX_LEGACY",
            runtime_role="PRODUCTION_INPUT",
            currently_consumed_by_production=True,
            notes=(
                "B1 live-proven CHOPPY/TRENDING regime evidence.",
            ),
        ),

        AnalyzerDescriptorV1(
            analyzer_id="index.option_chain.legacy_v1",
            analyzer_version="1.0",
            category="OPTIONS",
            markets=INDEX_MARKETS,
            source_family="INDEX_LEGACY",
            runtime_role="PRODUCTION_INPUT",
            currently_consumed_by_production=True,
            notes=(
                "Current index PCR/OI/support/resistance/max-pain family.",
                "PCR semantics must be normalized before Brain comparison.",
            ),
        ),

        AnalyzerDescriptorV1(
            analyzer_id="mcx.mtf.native_v1",
            analyzer_version="1.0",
            category="TECHNICAL",
            markets=MCX_MARKETS,
            source_family="MCX_NATIVE",
            runtime_role="PRODUCTION_INPUT",
            currently_consumed_by_production=True,
            notes=(
                "B1 proved production reaches src/mcx/mcx_mtf.py.",
            ),
        ),

        AnalyzerDescriptorV1(
            analyzer_id="mcx.regime.native_v1",
            analyzer_version="1.0",
            category="REGIME",
            markets=MCX_MARKETS,
            source_family="MCX_NATIVE",
            runtime_role="PRODUCTION_INPUT",
            currently_consumed_by_production=True,
            notes=(
                "B1 live-proven RANGE/TREND regime evidence.",
            ),
        ),

        AnalyzerDescriptorV1(
            analyzer_id="mcx.structure.native_v1",
            analyzer_version="1.0",
            category="STRUCTURE",
            markets=MCX_MARKETS,
            source_family="MCX_NATIVE",
            runtime_role="PRODUCTION_INPUT",
            currently_consumed_by_production=True,
            notes=(
                "Current MCX structure and VWAP evidence.",
            ),
        ),

        AnalyzerDescriptorV1(
            analyzer_id="mcx.price_oi.native_v1",
            analyzer_version="1.0",
            category="POSITIONING",
            markets=MCX_MARKETS,
            source_family="MCX_NATIVE",
            runtime_role="PRODUCTION_INPUT",
            currently_consumed_by_production=True,
            notes=(
                "Current futures Price/OI classification evidence.",
            ),
        ),

        AnalyzerDescriptorV1(
            analyzer_id="mcx.pcr.native_v1",
            analyzer_version="1.0",
            category="OPTIONS",
            markets=MCX_MARKETS,
            source_family="MCX_NATIVE",
            runtime_role="PRODUCTION_INPUT",
            currently_consumed_by_production=True,
            notes=(
                "Current raw/stable PCR and max-pain evidence.",
            ),
        ),

        AnalyzerDescriptorV1(
            analyzer_id="mcx.event_risk.native_v1",
            analyzer_version="1.0",
            category="EVENT",
            markets=MCX_MARKETS,
            source_family="MCX_NATIVE",
            runtime_role="PRODUCTION_INPUT",
            currently_consumed_by_production=True,
            notes=(
                "Current commodity-specific event-state evidence.",
                "Registration grants no blocking authority.",
            ),
        ),

        AnalyzerDescriptorV1(
            analyzer_id="canonical.technical_intelligence.v1",
            analyzer_version="1.0",
            category="TECHNICAL",
            markets=ALL_MARKETS,
            source_family="CANONICAL_TECHNICAL",
            runtime_role="SHADOW_AVAILABLE",
            currently_consumed_by_production=False,
            notes=(
                "B1 independently verified EMA/RSI/MACD/ADX/ATR/Bollinger numerics.",
                "B1 proved this package is not production-authoritative today.",
                "Eligible for later Shadow Brain comparison only.",
            ),
        ),
    )
)


__all__ = [
    "ANALYZER_CATEGORIES",
    "RUNTIME_ROLES",
    "SOURCE_FAMILIES",
    "SUPPORTED_MARKETS",
    "AnalyzerDescriptorV1",
    "AnalyzerRegistryV1",
    "DEFAULT_ANALYZER_REGISTRY_V1",
]