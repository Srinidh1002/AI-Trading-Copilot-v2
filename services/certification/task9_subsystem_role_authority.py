from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Task9SubsystemRole(str, Enum):
    REQUIRED_AND_AVAILABLE = "REQUIRED_AND_AVAILABLE"
    REQUIRED_BUT_UNAVAILABLE = "REQUIRED_BUT_UNAVAILABLE"
    OPTIONAL_AUGMENTATION = "OPTIONAL_AUGMENTATION"
    EXPLICITLY_DISABLED_WITH_REASON = (
        "EXPLICITLY_DISABLED_WITH_REASON"
    )


class Task9SubsystemId(str, Enum):
    DATA_QUALITY = "DATA_QUALITY"
    MARKET_SESSION = "MARKET_SESSION"
    TECHNICAL = "TECHNICAL"
    MULTI_TIMEFRAME = "MULTI_TIMEFRAME"
    REGIME = "REGIME"

    OPTION_CHAIN = "OPTION_CHAIN"
    OPTION_OI = "OPTION_OI"
    OPTION_OI_CHANGE = "OPTION_OI_CHANGE"
    OPTION_PCR = "OPTION_PCR"
    OPTION_SUPPORT_RESISTANCE = "OPTION_SUPPORT_RESISTANCE"
    OPTION_MAX_PAIN = "OPTION_MAX_PAIN"
    OPTION_IV = "OPTION_IV"
    OPTION_GREEKS = "OPTION_GREEKS"
    OPTION_PREMIUM = "OPTION_PREMIUM"
    OPTION_LIQUIDITY = "OPTION_LIQUIDITY"
    OPTION_CONTRACT_ELIGIBILITY = (
        "OPTION_CONTRACT_ELIGIBILITY"
    )

    CROSS_MARKET_NIFTY_SENSEX = (
        "CROSS_MARKET_NIFTY_SENSEX"
    )
    INDIA_VIX = "INDIA_VIX"

    MARKET_BREADTH = "MARKET_BREADTH"
    GLOBAL_MARKETS = "GLOBAL_MARKETS"
    INSTITUTIONAL_FLOWS = "INSTITUTIONAL_FLOWS"
    SCHEDULED_EVENTS = "SCHEDULED_EVENTS"
    NEWS_SENTIMENT = "NEWS_SENTIMENT"


@dataclass(frozen=True, slots=True)
class Task9SubsystemRoleStateV1:
    subsystem_id: Task9SubsystemId
    role: Task9SubsystemRole
    decision_blocking: bool
    source_authority: str
    reason_code: str | None = None

    def __post_init__(self) -> None:
        try:
            object.__setattr__(
                self,
                "subsystem_id",
                Task9SubsystemId(self.subsystem_id),
            )
            object.__setattr__(
                self,
                "role",
                Task9SubsystemRole(self.role),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Task 9 subsystem role state"
            ) from exc

        if type(self.decision_blocking) is not bool:
            raise TypeError("decision_blocking")

        if (
            not isinstance(self.source_authority, str)
            or not self.source_authority.strip()
        ):
            raise ValueError("source_authority")

        object.__setattr__(
            self,
            "source_authority",
            self.source_authority.strip(),
        )

        if self.reason_code is not None:
            if (
                not isinstance(self.reason_code, str)
                or not self.reason_code.strip()
            ):
                raise ValueError("reason_code")

            object.__setattr__(
                self,
                "reason_code",
                self.reason_code.strip().upper(),
            )

        if (
            self.role
            is Task9SubsystemRole.REQUIRED_BUT_UNAVAILABLE
            and self.decision_blocking is not True
        ):
            raise ValueError(
                "required unavailable subsystem must block"
            )

        if (
            self.role
            is Task9SubsystemRole.REQUIRED_AND_AVAILABLE
            and self.decision_blocking is not True
        ):
            raise ValueError(
                "required subsystem must be decision blocking"
            )

        if self.role in {
            Task9SubsystemRole.OPTIONAL_AUGMENTATION,
            Task9SubsystemRole.EXPLICITLY_DISABLED_WITH_REASON,
        } and self.decision_blocking is not False:
            raise ValueError(
                "optional or disabled subsystem cannot block"
            )

        if (
            self.role
            is Task9SubsystemRole.EXPLICITLY_DISABLED_WITH_REASON
            and self.reason_code is None
        ):
            raise ValueError(
                "disabled subsystem requires reason"
            )


def _required(
    subsystem_id: Task9SubsystemId,
    source_authority: str,
) -> Task9SubsystemRoleStateV1:
    return Task9SubsystemRoleStateV1(
        subsystem_id=subsystem_id,
        role=Task9SubsystemRole.REQUIRED_AND_AVAILABLE,
        decision_blocking=True,
        source_authority=source_authority,
    )


def default_task9_subsystem_role_registry(
) -> tuple[Task9SubsystemRoleStateV1, ...]:
    rows = (
        _required(
            Task9SubsystemId.DATA_QUALITY,
            "market_analysis_candidate_composer",
        ),
        _required(
            Task9SubsystemId.MARKET_SESSION,
            "market_session.validator",
        ),
        _required(
            Task9SubsystemId.TECHNICAL,
            "canonical_technical_intelligence",
        ),
        _required(
            Task9SubsystemId.MULTI_TIMEFRAME,
            "task9_precomposed_timeframe_provider",
        ),
        _required(
            Task9SubsystemId.REGIME,
            "canonical_market_regime",
        ),
        _required(
            Task9SubsystemId.OPTION_CHAIN,
            "canonical_option_chain_intelligence",
        ),
        _required(
            Task9SubsystemId.OPTION_OI,
            "canonical_option_chain_intelligence",
        ),
        _required(
            Task9SubsystemId.OPTION_OI_CHANGE,
            "task9_option_oi_change_authority",
        ),
        _required(
            Task9SubsystemId.OPTION_PCR,
            "canonical_option_chain_intelligence",
        ),
        _required(
            Task9SubsystemId.OPTION_SUPPORT_RESISTANCE,
            "canonical_option_chain_intelligence",
        ),
        _required(
            Task9SubsystemId.OPTION_MAX_PAIN,
            "canonical_option_chain_intelligence",
        ),

        # IV/Greeks are required evidence pillars when the provider
        # documents/certifies support. SENSEX/BFO capability absence is
        # explicitly handled by the provider-capability exception path.
        _required(
            Task9SubsystemId.OPTION_IV,
            "provider_capability_aware_option_evidence",
        ),
        _required(
            Task9SubsystemId.OPTION_GREEKS,
            "provider_capability_aware_option_evidence",
        ),

        _required(
            Task9SubsystemId.OPTION_PREMIUM,
            "canonical_option_contract_ranking",
        ),
        _required(
            Task9SubsystemId.OPTION_LIQUIDITY,
            "canonical_option_contract_ranking",
        ),
        _required(
            Task9SubsystemId.OPTION_CONTRACT_ELIGIBILITY,
            "canonical_option_contract_ranking",
        ),
        _required(
            Task9SubsystemId.CROSS_MARKET_NIFTY_SENSEX,
            "shared_broader_market_context",
        ),
        _required(
            Task9SubsystemId.INDIA_VIX,
            "IndiaVixLiveReader",
        ),

        Task9SubsystemRoleStateV1(
            subsystem_id=Task9SubsystemId.GLOBAL_MARKETS,
            role=Task9SubsystemRole.OPTIONAL_AUGMENTATION,
            decision_blocking=False,
            source_authority=(
                "ExternalContextSourceAuthority"
            ),
            reason_code=(
                "CERTIFIED_PROVIDER_NOT_SELECTED"
            ),
        ),
        Task9SubsystemRoleStateV1(
            subsystem_id=Task9SubsystemId.INSTITUTIONAL_FLOWS,
            role=Task9SubsystemRole.OPTIONAL_AUGMENTATION,
            decision_blocking=False,
            source_authority=(
                "ExternalContextSourceAuthority"
            ),
            reason_code=(
                "CERTIFIED_PROVIDER_NOT_SELECTED"
            ),
        ),
        Task9SubsystemRoleStateV1(
            subsystem_id=Task9SubsystemId.NEWS_SENTIMENT,
            role=Task9SubsystemRole.OPTIONAL_AUGMENTATION,
            decision_blocking=False,
            source_authority="NONE",
            reason_code=(
                "NOT_IN_OFFICIAL_TASK9_GRAPH"
            ),
        ),

        Task9SubsystemRoleStateV1(
            subsystem_id=Task9SubsystemId.MARKET_BREADTH,
            role=(
                Task9SubsystemRole
                .EXPLICITLY_DISABLED_WITH_REASON
            ),
            decision_blocking=False,
            source_authority="NONE",
            reason_code=(
                "CERTIFIED_SOURCE_NOT_AVAILABLE"
            ),
        ),
        Task9SubsystemRoleStateV1(
            subsystem_id=Task9SubsystemId.SCHEDULED_EVENTS,
            role=(
                Task9SubsystemRole
                .EXPLICITLY_DISABLED_WITH_REASON
            ),
            decision_blocking=False,
            source_authority=(
                "UnavailableScheduledEventReader"
            ),
            reason_code=(
                "CERTIFIED_EVENT_PROVIDER_NOT_SELECTED"
            ),
        ),
    )

    if len(rows) != len(Task9SubsystemId):
        raise RuntimeError(
            "Task 9 subsystem registry incomplete"
        )

    ids = tuple(row.subsystem_id for row in rows)

    if len(ids) != len(set(ids)):
        raise RuntimeError(
            "Task 9 subsystem registry duplicate"
        )

    return tuple(
        sorted(
            rows,
            key=lambda row: row.subsystem_id.value,
        )
    )


__all__ = (
    "Task9SubsystemId",
    "Task9SubsystemRole",
    "Task9SubsystemRoleStateV1",
    "default_task9_subsystem_role_registry",
)
