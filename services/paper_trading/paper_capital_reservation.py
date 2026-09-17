"""Deterministic PAPER fees, capital reservation, and duplicate prevention."""
from __future__ import annotations

from services.contracts.paper_entry_admission_v1 import (
    PaperCapitalReservationInputV1,
    PaperCapitalReservationResultV1,
    PaperFeeBreakdownV1,
)


def calculate_paper_entry_fees(
    reservation_input: PaperCapitalReservationInputV1,
) -> PaperFeeBreakdownV1:
    if type(reservation_input) is not PaperCapitalReservationInputV1:
        raise TypeError("reservation_input")

    gross = reservation_input.fill_gross_premium_outlay
    policy = reservation_input.fee_policy
    brokerage = policy.brokerage_per_order
    exchange = gross * policy.exchange_transaction_fraction
    sebi = gross * policy.sebi_fraction
    stamp = gross * policy.stamp_duty_fraction
    stt = gross * policy.stt_fraction
    gst_base = brokerage + exchange + sebi
    gst = gst_base * policy.gst_fraction_on_charges
    total_fees = brokerage + exchange + sebi + stamp + stt + gst

    return PaperFeeBreakdownV1(
        policy_id=policy.policy_id,
        gross_premium_outlay=gross,
        brokerage=brokerage,
        exchange_transaction_charges=exchange,
        sebi_charges=sebi,
        stamp_duty=stamp,
        stt=stt,
        gst=gst,
        total_fees=total_fees,
        total_capital_required=gross + total_fees,
    )


def reserve_paper_entry_capital(
    *,
    reservation_result_id: str,
    reservation_input: PaperCapitalReservationInputV1,
) -> PaperCapitalReservationResultV1:
    if type(reservation_input) is not PaperCapitalReservationInputV1:
        raise TypeError("reservation_input")

    fees = calculate_paper_entry_fees(reservation_input)
    active = tuple(
        item for item in reservation_input.existing_reservations
        if item.active
    )
    existing_reserved = sum(item.reserved_capital for item in active)
    blockers: list[str] = []

    if any(
        item.recommendation_id == reservation_input.recommendation_id
        for item in active
    ):
        blockers.append("DUPLICATE_RECOMMENDATION")
    if any(
        item.contract == reservation_input.contract
        for item in active
    ):
        blockers.append("DUPLICATE_ACTIVE_CONTRACT")

    remaining_before = max(
        0.0,
        reservation_input.available_capital - existing_reserved,
    )
    if fees.total_capital_required > remaining_before + 1e-9:
        blockers.append("INSUFFICIENT_UNRESERVED_CAPITAL")
    if reservation_input.maximum_loss > remaining_before + 1e-9:
        blockers.append("MAXIMUM_LOSS_EXCEEDS_REMAINING_CAPITAL")

    blockers = tuple(dict.fromkeys(blockers))
    newly_reserved = 0.0 if blockers else fees.total_capital_required
    total_reserved = existing_reserved + newly_reserved
    remaining = max(
        0.0,
        reservation_input.available_capital - total_reserved,
    )

    return PaperCapitalReservationResultV1(
        reservation_result_id=reservation_result_id,
        reservation_request_id=reservation_input.reservation_request_id,
        recommendation_id=reservation_input.recommendation_id,
        contract=reservation_input.contract,
        evaluated_at=reservation_input.evaluated_at,
        status="REJECTED" if blockers else "RESERVED",
        fee_breakdown=fees,
        existing_reserved_capital=existing_reserved,
        newly_reserved_capital=newly_reserved,
        total_reserved_capital=total_reserved,
        remaining_capital=remaining,
        maximum_loss=reservation_input.maximum_loss,
        blockers=blockers,
    )

