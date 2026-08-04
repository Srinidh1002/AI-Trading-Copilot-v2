"""Deterministic PAPER monitoring lifecycle state machine."""
from __future__ import annotations

from services.contracts.active_paper_position_v1 import ActivePaperPositionV1
from services.contracts.paper_monitoring_lifecycle_v1 import (
    PaperLifecycleTransitionV1,
    PaperMonitoringEvidenceV1,
)


def evaluate_paper_position_lifecycle(
    *,
    transition_id: str,
    position: ActivePaperPositionV1,
    evidence: PaperMonitoringEvidenceV1,
    caution_confidence_threshold: float = 0.55,
) -> PaperLifecycleTransitionV1:
    if type(position) is not ActivePaperPositionV1:
        raise TypeError("position")
    if type(evidence) is not PaperMonitoringEvidenceV1:
        raise TypeError("evidence")
    if evidence.position_id != position.position_id:
        raise ValueError("position/evidence mismatch")
    if evidence.observed_at < position.updated_at:
        raise ValueError("evidence precedes position")
    if type(caution_confidence_threshold) not in (int, float) or isinstance(caution_confidence_threshold, bool):
        raise TypeError("caution_confidence_threshold")
    if not 0.0 <= float(caution_confidence_threshold) <= 1.0:
        raise ValueError("caution_confidence_threshold")

    warnings = list(evidence.warnings)
    if evidence.is_stale:
        return _transition(
            transition_id, position, evidence,
            action="HOLD_WITH_CAUTION",
            next_state=position.lifecycle_state,
            reasons=("MONITORING_EVIDENCE_STALE",),
            warnings=tuple(warnings),
        )

    if position.lifecycle_state == "CLOSED":
        return _transition(
            transition_id, position, evidence,
            action="TRADE_CLOSED",
            next_state="CLOSED",
            exit_quantity=position.initial_quantity,
            remaining_quantity=0,
            reasons=("POSITION_ALREADY_CLOSED",),
            warnings=tuple(warnings),
        )

    premium = evidence.current_bid

    if premium <= position.current_stop_loss:
        return _transition(
            transition_id, position, evidence,
            action="STOP_HIT",
            next_state="CLOSED",
            exit_quantity=position.remaining_quantity,
            remaining_quantity=0,
            reasons=("CURRENT_BID_AT_OR_BELOW_STOP",),
            warnings=tuple(warnings),
        )

    if evidence.safety_exit_required or not evidence.setup_valid:
        return _transition(
            transition_id, position, evidence,
            action="EXIT_NOW",
            next_state="CLOSED",
            exit_quantity=position.remaining_quantity,
            remaining_quantity=0,
            reasons=(
                "SAFETY_EXIT_REQUIRED"
                if evidence.safety_exit_required
                else "SETUP_INVALIDATED",
            ),
            warnings=tuple(warnings),
        )

    if premium >= position.target_3 and not position.target_3_hit:
        return _transition(
            transition_id, position, evidence,
            action="TARGET_3_HIT",
            next_state="CLOSED",
            exit_quantity=position.remaining_quantity,
            remaining_quantity=0,
            reasons=("TARGET_3_REACHED",),
            warnings=tuple(warnings),
        )

    partial_exit_quantity = position.lot_size
    if premium >= position.target_2 and not position.target_2_hit:
        remaining = max(0, position.remaining_quantity - partial_exit_quantity)
        return _transition(
            transition_id, position, evidence,
            action="TARGET_2_HIT",
            next_state="CLOSED" if remaining == 0 else "PARTIALLY_EXITED",
            exit_quantity=min(partial_exit_quantity, position.remaining_quantity),
            remaining_quantity=remaining,
            reasons=("TARGET_2_REACHED",),
            warnings=tuple(warnings),
        )

    if premium >= position.target_1 and not position.target_1_hit:
        remaining = max(0, position.remaining_quantity - partial_exit_quantity)
        return _transition(
            transition_id, position, evidence,
            action="TARGET_1_HIT",
            next_state="CLOSED" if remaining == 0 else "PARTIALLY_EXITED",
            exit_quantity=min(partial_exit_quantity, position.remaining_quantity),
            remaining_quantity=remaining,
            reasons=("TARGET_1_REACHED",),
            warnings=tuple(warnings),
        )

    if evidence.contradictions or evidence.confidence < float(caution_confidence_threshold):
        reasons = []
        if evidence.contradictions:
            reasons.append("MONITORING_CONTRADICTIONS_PRESENT")
        if evidence.confidence < float(caution_confidence_threshold):
            reasons.append("CONFIDENCE_DETERIORATED")
        return _transition(
            transition_id, position, evidence,
            action="HOLD_WITH_CAUTION",
            next_state=position.lifecycle_state,
            reasons=tuple(reasons),
            warnings=tuple(warnings),
        )

    return _transition(
        transition_id, position, evidence,
        action="HOLD",
        next_state=position.lifecycle_state,
        reasons=("SETUP_REMAINS_VALID",),
        warnings=tuple(warnings),
    )


def _transition(
    transition_id,
    position,
    evidence,
    *,
    action,
    next_state,
    reasons,
    exit_quantity=0,
    remaining_quantity=None,
    warnings=(),
):
    return PaperLifecycleTransitionV1(
        transition_id=transition_id,
        position_id=position.position_id,
        evidence_id=evidence.evidence_id,
        evaluated_at=evidence.observed_at,
        action=action,
        previous_state=position.lifecycle_state,
        next_state=next_state,
        exit_quantity=exit_quantity,
        remaining_quantity=(
            position.remaining_quantity
            if remaining_quantity is None
            else remaining_quantity
        ),
        effective_stop_loss=position.current_stop_loss,
        reasons=reasons,
        warnings=warnings,
    )
