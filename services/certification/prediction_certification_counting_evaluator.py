"""Pure deterministic prediction certification-counting authority."""
from __future__ import annotations

import hashlib
import json

from services.contracts.paper_certification_counting_policy_v1 import (
    PaperCertificationCountingPolicyV1,
)
from services.contracts.prediction_certification_counting_decision_v1 import (
    PredictionCertificationCountingDecisionV1,
)
from services.contracts.prediction_certification_counting_input_v1 import (
    PredictionCertificationCountingInputV1,
)


_SOURCE_EXCLUSIONS = {
    "REPLAY": "EXCLUDED_REPLAY",
    "BACKTEST": "EXCLUDED_BACKTEST",
    "DIAGNOSTIC": "EXCLUDED_DIAGNOSTIC",
    "FIXTURE": "EXCLUDED_FIXTURE",
    "DEVELOPMENT": "EXCLUDED_DEVELOPMENT",
}


def _counting_key(
    *,
    value: PredictionCertificationCountingInputV1,
    policy: PaperCertificationCountingPolicyV1,
) -> str:
    payload = {
        "official_run_id": value.official_run_id,
        "prediction_id": value.prediction.prediction_id,
        "underlying_symbol": (
            value.prediction.underlying_symbol
        ),
        "exchange": value.prediction.exchange,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "system_version": (
            policy.accepted_system_version
        ),
        "provider_version": (
            policy.accepted_provider_version
        ),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _decision(
    *,
    value: PredictionCertificationCountingInputV1,
    policy: PaperCertificationCountingPolicyV1,
    status: str,
    reasons: tuple[str, ...],
) -> PredictionCertificationCountingDecisionV1:
    key = _counting_key(
        value=value,
        policy=policy,
    )
    included = status == "INCLUDED"
    pending = status == "PENDING_OUTCOME"

    return PredictionCertificationCountingDecisionV1(
        decision_id=f"counting-decision:{key}",
        counting_key=key,
        prediction_id=value.prediction.prediction_id,
        outcome_id=(
            value.outcome.outcome_id
            if value.outcome is not None
            else None
        ),
        official_run_id=value.official_run_id,
        underlying_symbol=(
            value.prediction.underlying_symbol
        ),
        exchange=value.prediction.exchange,
        predicted_action=(
            value.prediction.predicted_action
        ),
        parent_decision=(
            value.prediction.parent_decision
        ),
        status=status,
        countable=included,
        pending=pending,
        reason_codes=reasons,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        system_version=(
            policy.accepted_system_version
        ),
        provider_version=(
            policy.accepted_provider_version
        ),
        evaluated_at=value.evaluated_at,
    )


def evaluate_prediction_certification_counting(
    *,
    value: PredictionCertificationCountingInputV1,
    policy: PaperCertificationCountingPolicyV1,
) -> PredictionCertificationCountingDecisionV1:
    """Classify one immutable prediction without mutating counters."""

    if (
        type(value)
        is not PredictionCertificationCountingInputV1
    ):
        raise TypeError("value")
    if (
        type(policy)
        is not PaperCertificationCountingPolicyV1
    ):
        raise TypeError("policy")

    source_exclusion = _SOURCE_EXCLUSIONS.get(
        value.record_source
    )
    if source_exclusion is not None:
        return _decision(
            value=value,
            policy=policy,
            status=source_exclusion,
            reasons=(
                f"RECORD_SOURCE_{value.record_source}",
            ),
        )

    if value.record_source != "LIVE_REAL_TIME":
        raise ValueError(
            "unsupported record source"
        )

    if value.record_run_id != value.official_run_id:
        return _decision(
            value=value,
            policy=policy,
            status="EXCLUDED_RUN_MISMATCH",
            reasons=("OFFICIAL_RUN_ID_MISMATCH",),
        )

    if (
        value.prediction.completed_at
        < value.official_start_at
    ):
        return _decision(
            value=value,
            policy=policy,
            status="EXCLUDED_PRE_START",
            reasons=("PREDICTION_PRECEDES_OFFICIAL_START",),
        )

    if (
        value.observed_system_version
        != policy.accepted_system_version
        or value.observed_policy_version
        != policy.policy_version
        or value.observed_provider_version
        != policy.accepted_provider_version
    ):
        reasons: list[str] = []
        if (
            value.observed_system_version
            != policy.accepted_system_version
        ):
            reasons.append("SYSTEM_VERSION_MISMATCH")
        if (
            value.observed_policy_version
            != policy.policy_version
        ):
            reasons.append("POLICY_VERSION_MISMATCH")
        if (
            value.observed_provider_version
            != policy.accepted_provider_version
        ):
            reasons.append("PROVIDER_VERSION_MISMATCH")
        return _decision(
            value=value,
            policy=policy,
            status="EXCLUDED_VERSION_MISMATCH",
            reasons=tuple(reasons),
        )

    if (
        value.session_status
        != "REAL_TIME_MARKET_SESSION"
    ):
        return _decision(
            value=value,
            policy=policy,
            status="EXCLUDED_OUT_OF_SESSION",
            reasons=(
                f"SESSION_STATUS_{value.session_status}",
            ),
        )

    if value.evidence_status == "INVALID":
        return _decision(
            value=value,
            policy=policy,
            status="EXCLUDED_INVALID_EVIDENCE",
            reasons=("EVIDENCE_INVALID",),
        )

    if value.evidence_status == "DATA_INCIDENT":
        return _decision(
            value=value,
            policy=policy,
            status="EXCLUDED_DATA_INCIDENT",
            reasons=value.data_incident_codes,
        )

    if value.prediction.terminal_status != "COMPLETED":
        return _decision(
            value=value,
            policy=policy,
            status="EXCLUDED_TERMINAL_PREDICTION",
            reasons=(
                "PREDICTION_TERMINAL_STATUS_"
                f"{value.prediction.terminal_status}",
            ),
        )

    if value.outcome is None:
        return _decision(
            value=value,
            policy=policy,
            status="PENDING_OUTCOME",
            reasons=("OUTCOME_NOT_COMPLETED",),
        )

    if (
        value.outcome.evaluation_status
        == "UNEVALUABLE"
        or value.outcome.outcome == "UNEVALUABLE"
    ):
        return _decision(
            value=value,
            policy=policy,
            status="EXCLUDED_UNEVALUABLE_OUTCOME",
            reasons=tuple(
                dict.fromkeys(
                    (
                        "OUTCOME_UNEVALUABLE",
                        *value.outcome.blockers,
                    )
                )
            ),
        )

    return _decision(
        value=value,
        policy=policy,
        status="INCLUDED",
        reasons=(),
    )
