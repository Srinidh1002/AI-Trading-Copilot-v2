"""Deterministic all-or-none PAPER entry fill simulator."""
from __future__ import annotations

from services.contracts.paper_fill_simulation_v1 import (
    PaperEntryOrderV1,
    PaperFillQuoteEvidenceV1,
    PaperFillResultV1,
)


def simulate_paper_entry_fill(
    *,
    fill_result_id: str,
    order: PaperEntryOrderV1,
    quote: PaperFillQuoteEvidenceV1,
) -> PaperFillResultV1:
    if type(order) is not PaperEntryOrderV1:
        raise TypeError("order")
    if type(quote) is not PaperFillQuoteEvidenceV1:
        raise TypeError("quote")
    if quote.contract != order.contract:
        raise ValueError("quote/order contract mismatch")
    if quote.observed_at < order.submitted_at:
        raise ValueError("quote precedes order submission")

    blockers: list[str] = []
    warnings = list(quote.warnings)

    if quote.is_stale:
        blockers.append("STALE_FILL_QUOTE")
    if quote.available_ask_quantity < order.quantity:
        blockers.append("INSUFFICIENT_ASK_QUANTITY")

    reference_price = quote.ask_price
    if order.order_type == "LIMIT":
        if quote.ask_price > order.limit_price:
            blockers.append("LIMIT_PRICE_NOT_MARKETABLE")
        reference_price = order.limit_price

    simulated_fill_price = quote.ask_price
    slippage_amount = max(0.0, simulated_fill_price - reference_price)
    slippage_fraction = (
        slippage_amount / reference_price
        if reference_price > 0.0
        else 0.0
    )
    if slippage_fraction > order.maximum_slippage_fraction:
        blockers.append("SLIPPAGE_EXCEEDS_ALLOWANCE")

    gross_outlay = simulated_fill_price * order.quantity
    if gross_outlay > order.maximum_capital + 1e-9:
        blockers.append("FILL_EXCEEDS_MAXIMUM_CAPITAL")

    blockers = list(dict.fromkeys(blockers))
    warnings = list(dict.fromkeys(warnings))

    if blockers:
        not_filled_only = set(blockers) <= {
            "INSUFFICIENT_ASK_QUANTITY",
            "LIMIT_PRICE_NOT_MARKETABLE",
        }
        return PaperFillResultV1(
            fill_result_id=fill_result_id,
            order_id=order.order_id,
            quote_id=quote.quote_id,
            evaluated_at=quote.observed_at,
            status="NOT_FILLED" if not_filled_only else "REJECTED",
            filled_quantity=0,
            filled_lots=0,
            fill_price=None,
            gross_premium_outlay=0.0,
            slippage_amount_per_unit=0.0,
            slippage_fraction=0.0,
            remaining_quantity=order.quantity,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
        )

    return PaperFillResultV1(
        fill_result_id=fill_result_id,
        order_id=order.order_id,
        quote_id=quote.quote_id,
        evaluated_at=quote.observed_at,
        status="FILLED",
        filled_quantity=order.quantity,
        filled_lots=order.lots,
        fill_price=simulated_fill_price,
        gross_premium_outlay=gross_outlay,
        slippage_amount_per_unit=slippage_amount,
        slippage_fraction=slippage_fraction,
        remaining_quantity=0,
        warnings=tuple(warnings),
    )
