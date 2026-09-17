import pytest

from services.certification.task9_subsystem_role_authority import (
    Task9SubsystemId,
    Task9SubsystemRole,
    Task9SubsystemRoleStateV1,
    default_task9_subsystem_role_registry,
)


def _registry():
    return {
        row.subsystem_id: row
        for row in default_task9_subsystem_role_registry()
    }


def test_task9_subsystem_registry_is_complete_and_unique():
    rows = default_task9_subsystem_role_registry()

    assert len(rows) == len(Task9SubsystemId)
    assert len({row.subsystem_id for row in rows}) == len(rows)


@pytest.mark.parametrize(
    "subsystem",
    (
        Task9SubsystemId.DATA_QUALITY,
        Task9SubsystemId.MARKET_SESSION,
        Task9SubsystemId.TECHNICAL,
        Task9SubsystemId.MULTI_TIMEFRAME,
        Task9SubsystemId.REGIME,
        Task9SubsystemId.OPTION_CHAIN,
        Task9SubsystemId.OPTION_OI,
        Task9SubsystemId.OPTION_OI_CHANGE,
        Task9SubsystemId.OPTION_PCR,
        Task9SubsystemId.OPTION_SUPPORT_RESISTANCE,
        Task9SubsystemId.OPTION_MAX_PAIN,
        Task9SubsystemId.OPTION_IV,
        Task9SubsystemId.OPTION_GREEKS,
        Task9SubsystemId.OPTION_PREMIUM,
        Task9SubsystemId.OPTION_LIQUIDITY,
        Task9SubsystemId.OPTION_CONTRACT_ELIGIBILITY,
        Task9SubsystemId.CROSS_MARKET_NIFTY_SENSEX,
        Task9SubsystemId.INDIA_VIX,
    ),
)
def test_required_task9_subsystems_are_explicitly_blocking(
    subsystem,
):
    state = _registry()[subsystem]

    assert (
        state.role
        is Task9SubsystemRole.REQUIRED_AND_AVAILABLE
    )
    assert state.decision_blocking is True


@pytest.mark.parametrize(
    "subsystem",
    (
        Task9SubsystemId.GLOBAL_MARKETS,
        Task9SubsystemId.INSTITUTIONAL_FLOWS,
        Task9SubsystemId.NEWS_SENTIMENT,
    ),
)
def test_optional_augmentation_is_non_blocking_and_explicit(
    subsystem,
):
    state = _registry()[subsystem]

    assert (
        state.role
        is Task9SubsystemRole.OPTIONAL_AUGMENTATION
    )
    assert state.decision_blocking is False
    assert state.reason_code is not None


@pytest.mark.parametrize(
    "subsystem",
    (
        Task9SubsystemId.MARKET_BREADTH,
        Task9SubsystemId.SCHEDULED_EVENTS,
    ),
)
def test_disabled_subsystems_have_explicit_reason(
    subsystem,
):
    state = _registry()[subsystem]

    assert (
        state.role
        is Task9SubsystemRole.EXPLICITLY_DISABLED_WITH_REASON
    )
    assert state.decision_blocking is False
    assert state.reason_code


def test_required_but_unavailable_must_block():
    with pytest.raises(
        ValueError,
        match="required unavailable subsystem must block",
    ):
        Task9SubsystemRoleStateV1(
            subsystem_id=Task9SubsystemId.INDIA_VIX,
            role=(
                Task9SubsystemRole.REQUIRED_BUT_UNAVAILABLE
            ),
            decision_blocking=False,
            source_authority="IndiaVixLiveReader",
            reason_code="PROVIDER_UNAVAILABLE",
        )


def test_disabled_subsystem_requires_reason():
    with pytest.raises(
        ValueError,
        match="disabled subsystem requires reason",
    ):
        Task9SubsystemRoleStateV1(
            subsystem_id=Task9SubsystemId.MARKET_BREADTH,
            role=(
                Task9SubsystemRole
                .EXPLICITLY_DISABLED_WITH_REASON
            ),
            decision_blocking=False,
            source_authority="NONE",
        )
