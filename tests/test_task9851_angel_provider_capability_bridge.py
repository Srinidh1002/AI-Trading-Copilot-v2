from dataclasses import replace

import pytest

from services.certification.task9_angel_capability_session_builder import (
    build_task9_angel_capability_session,
)
from services.certification.task9_angel_provider_capability_bridge import (
    validate_task9_angel_generic_capability_alignment,
)
from services.certification.task9_provider_capability_report_builder import (
    build_task9_provider_capability_report,
)
from services.certification.task9_runtime_config_builder import (
    build_task9_runtime_config,
)
from services.contracts.task9_angel_capability_session_v1 import (
    Task9AngelCapability,
)
from services.contracts.task9_provider_capability_report_v1 import (
    Task9LiveProofStatus,
    Task9ProviderCapabilityReportV1,
    Task9ProviderReadinessStatus,
)


def _runtime_config():
    from datetime import date

    return build_task9_runtime_config(
        runtime_config_id="task9851-runtime-config",
        runtime_config_version="1",
        campaign_registry_location="task9851/campaign-registry.json",
        campaign_id="task9851-campaign",
        market_date=date(2026, 8, 17),
        official_run_id="task9851-official-run",
        official_root="task9851/official",
        certification_registry_root="task9851/certification-registry",
        authoritative_persistence_root="task9851/persistence",
        dashboard_publication_location="task9851/dashboard-publication.json",
        available_capital=100000.0,
        risk_fraction=0.02,
        maximum_quantity=100,
        policy_references={
            "canonical_directional": "task9851-canonical-directional.v1",
            "session": "task9851-session.v1",
            "risk": "task9851-risk.v1",
            "contract_selection": "task9851-contract-selection.v1",
            "lifecycle": "task9851-lifecycle.v1",
            "counting": "task9851-counting.v1",
            "failure_disposition": "task9851-failure-disposition.v1",
            "contract_spread": "task9851-contract-spread.v1",
            "liquidity": "task9851-liquidity.v1",
            "minimum_risk_reward": "task9851-minimum-risk-reward.v1",
            "stop_target": "task9851-stop-target.v1",
            "portfolio_concurrency": "task9851-portfolio-concurrency.v1",
        },
    )


def _generic():
    return build_task9_provider_capability_report(
        _runtime_config()
    )


def _angel():
    return build_task9_angel_capability_session()


def test_default_angel_authority_aligns_with_generic_report():
    validate_task9_angel_generic_capability_alignment(
        angel=_angel(),
        generic=_generic(),
    )


def test_bfo_greeks_alignment_is_explicitly_unsupported():
    angel = _angel()
    generic = _generic()

    angel_state = angel.capability(
        Task9AngelCapability.BFO_OPTION_GREEKS
    )

    generic_state = next(
        state
        for state in generic.capability_states
        if (
            state.provider_family.value
            == "ANGEL_OPTION_GREEKS"
            and state.market == "SENSEX"
            and state.exchange == "BFO"
        )
    )

    assert (
        angel_state.readiness_status
        is Task9ProviderReadinessStatus.UNSUPPORTED
    )
    assert (
        generic_state.readiness_status
        is Task9ProviderReadinessStatus.UNSUPPORTED
    )


def test_nfo_greeks_alignment_is_pending_live_proof():
    angel = _angel()
    generic = _generic()

    angel_state = angel.capability(
        Task9AngelCapability.NFO_OPTION_GREEKS
    )

    generic_state = next(
        state
        for state in generic.capability_states
        if (
            state.provider_family.value
            == "ANGEL_OPTION_GREEKS"
            and state.market == "NIFTY"
            and state.exchange == "NFO"
        )
    )

    assert (
        angel_state.live_proof_status
        is Task9LiveProofStatus.PENDING
    )
    assert (
        generic_state.live_proof_status
        is Task9LiveProofStatus.PENDING
    )


def test_missing_generic_capability_fails_closed():
    generic = _generic()

    trimmed = Task9ProviderCapabilityReportV1(
        runtime_config_id=generic.runtime_config_id,
        runtime_config_version=(
            generic.runtime_config_version
        ),
        capability_states=tuple(
            state
            for state in generic.capability_states
            if not (
                state.provider_family.value
                == "ANGEL_SPOT"
                and state.market == "NIFTY"
            )
        ),
    )

    with pytest.raises(
        ValueError,
        match="TASK9_ANGEL_GENERIC_CAPABILITY_MISSING",
    ):
        validate_task9_angel_generic_capability_alignment(
            angel=_angel(),
            generic=trimmed,
        )


def test_live_proof_mismatch_fails_closed():
    generic = _generic()

    changed = []
    modified = False

    for state in generic.capability_states:
        if (
            not modified
            and state.provider_family.value
            == "ANGEL_SPOT"
            and state.market == "NIFTY"
            and state.exchange == "NSE"
        ):
            changed.append(
                replace(
                    state,
                    live_proof_status=(
                        Task9LiveProofStatus.PROVEN
                    ),
                    readiness_status=(
                        Task9ProviderReadinessStatus.READY
                    ),
                    startup_semantic=None,
                )
            )
            modified = True
        else:
            changed.append(state)

    changed_report = (
        Task9ProviderCapabilityReportV1(
            runtime_config_id=(
                generic.runtime_config_id
            ),
            runtime_config_version=(
                generic.runtime_config_version
            ),
            capability_states=tuple(changed),
        )
    )

    with pytest.raises(
        ValueError,
        match="TASK9_ANGEL_GENERIC_LIVE_PROOF_MISMATCH",
    ):
        validate_task9_angel_generic_capability_alignment(
            angel=_angel(),
            generic=changed_report,
        )


def test_wrong_input_types_are_rejected():
    with pytest.raises(TypeError):
        validate_task9_angel_generic_capability_alignment(
            angel=object(),
            generic=_generic(),
        )

    with pytest.raises(TypeError):
        validate_task9_angel_generic_capability_alignment(
            angel=_angel(),
            generic=object(),
        )
