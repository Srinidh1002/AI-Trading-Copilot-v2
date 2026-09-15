"""Task 9 option FULL and Greeks proofs from retained certified capture.

No provider acquisition occurs here.

The live option-chain builder remains the sole FULL/Greeks transport
owner. This module converts its sanitized retained facts into Task 9
startup proof contracts.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from services.contracts.live_option_capture_result_v1 import (
    LiveOptionCaptureResultV1,
)
from services.contracts.task9_angel_greeks_proof_v1 import (
    Task9AngelGreeksProbeStatus,
    Task9AngelGreeksProofV1,
)
from services.contracts.task9_angel_option_full_proof_v1 import (
    Task9AngelOptionFullProbeStatus,
    Task9AngelOptionFullProofV1,
)


_IDENTITIES = {
    ("NIFTY", "NFO"),
    ("SENSEX", "BFO"),
}

_GREEK_FIELDS = (
    "delta",
    "gamma",
    "theta",
    "vega",
    "iv",
)


def _identity(
    capture: LiveOptionCaptureResultV1,
) -> tuple[str, str]:
    if type(capture) is not LiveOptionCaptureResultV1:
        raise TypeError("capture")

    identity = (
        capture.underlying_symbol,
        capture.option_exchange,
    )

    if identity not in _IDENTITIES:
        raise ValueError(
            "TASK9_OPTION_CAPTURE_IDENTITY_INVALID"
        )

    return identity


def _aware(
    value: object,
    name: str,
) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)

    return value


def produce_task9_angel_option_full_proof(
    capture: LiveOptionCaptureResultV1,
) -> Task9AngelOptionFullProofV1:
    market, exchange = _identity(capture)

    raw = capture.option_chain.get(
        "full_capture"
    )

    if not isinstance(raw, Mapping):
        raise ValueError(
            "TASK9_OPTION_FULL_CAPTURE_FACTS_MISSING"
        )

    requested = raw.get(
        "requested_contract_count"
    )
    fetched = raw.get(
        "fetched_contract_count"
    )
    unfetched = raw.get(
        "unfetched_contract_count"
    )
    malformed = raw.get(
        "malformed_contract_count"
    )

    for name, value in (
        ("requested_contract_count", requested),
        ("fetched_contract_count", fetched),
        ("unfetched_contract_count", unfetched),
        ("malformed_contract_count", malformed),
    ):
        if (
            type(value) is not int
            or isinstance(value, bool)
            or value < 0
        ):
            raise ValueError(name)

    if requested <= 0:
        raise ValueError(
            "requested_contract_count"
        )

    oldest_raw = raw.get(
        "oldest_provider_timestamp"
    )
    newest_raw = raw.get(
        "newest_provider_timestamp"
    )

    if fetched > 0:
        oldest = _aware(
            oldest_raw,
            "oldest_provider_timestamp",
        )
        newest = _aware(
            newest_raw,
            "newest_provider_timestamp",
        )
    else:
        if (
            oldest_raw is not None
            or newest_raw is not None
        ):
            raise ValueError(
                "zero fetched contracts cannot retain "
                "provider timestamps"
            )

        oldest = None
        newest = None

    identity_verified = raw.get(
        "exchange_identity_verified"
    )

    if type(identity_verified) is not bool:
        raise TypeError(
            "exchange_identity_verified"
        )

    if (
        fetched == requested
        and unfetched == 0
        and malformed == 0
    ):
        status = (
            Task9AngelOptionFullProbeStatus.AVAILABLE
        )
        reason = None
    elif fetched > 0:
        status = (
            Task9AngelOptionFullProbeStatus.PARTIAL
        )
        reason = (
            "OPTION_FULL_PARTIAL_VALIDATED_CAPTURE"
        )
    elif malformed > 0:
        status = (
            Task9AngelOptionFullProbeStatus.MALFORMED
        )
        reason = (
            "OPTION_FULL_CAPTURE_MALFORMED"
        )
    else:
        status = (
            Task9AngelOptionFullProbeStatus.UNAVAILABLE
        )
        reason = (
            "OPTION_FULL_CAPTURE_UNAVAILABLE"
        )

    return Task9AngelOptionFullProofV1(
        proof_id=(
            "task9-angel-option-full:"
            f"{market}:"
            f"{exchange}:"
            f"{capture.evaluated_at.isoformat()}"
        ),
        observed_at=capture.evaluated_at,
        market=market,
        exchange=exchange,
        status=status,
        requested_contract_count=requested,
        fetched_contract_count=fetched,
        unfetched_contract_count=unfetched,
        malformed_contract_count=malformed,
        oldest_provider_timestamp=oldest,
        newest_provider_timestamp=newest,
        exchange_identity_verified=(
            identity_verified
        ),
        source_ref=(
            "live-option-chain-builder-full"
            if fetched > 0
            else None
        ),
        incident_ref=None,
        sanitized_reason=reason,
        execution_mode="PAPER",
        broker_order_submission=False,
        live_execution_eligible=False,
    )


def produce_task9_angel_greeks_proof(
    capture: LiveOptionCaptureResultV1,
) -> Task9AngelGreeksProofV1:
    market, exchange = _identity(capture)

    if market == "SENSEX":
        return Task9AngelGreeksProofV1(
            proof_id=(
                "task9-angel-greeks:"
                f"SENSEX:BFO:"
                f"{capture.evaluated_at.isoformat()}"
            ),
            observed_at=capture.evaluated_at,
            market="SENSEX",
            exchange="BFO",
            status=(
                Task9AngelGreeksProbeStatus.UNSUPPORTED
            ),
            requested_contract_count=0,
            enriched_contract_count=0,
            unavailable_contract_count=0,
            delta_present=False,
            gamma_present=False,
            theta_present=False,
            vega_present=False,
            implied_volatility_present=False,
            source_ref=None,
            incident_ref=None,
            sanitized_reason=(
                "BFO_GREEKS_PROVIDER_UNSUPPORTED"
            ),
            execution_mode="PAPER",
            broker_order_submission=False,
            live_execution_eligible=False,
        )

    greek_capture = capture.metadata.get(
        "greek_capture",
        {},
    )

    if not isinstance(greek_capture, Mapping):
        greek_capture = {}

    state = str(
        greek_capture.get(
            "state",
            "",
        )
    ).strip().upper()

    reason = str(
        greek_capture.get(
            "reason",
            "",
        )
    ).strip() or None

    contracts = capture.contracts
    requested = len(contracts)

    if requested <= 0:
        raise ValueError(
            "TASK9_NFO_GREEKS_NO_CONTRACTS"
        )

    complete = tuple(
        contract
        for contract in contracts
        if all(
            contract.get(field) is not None
            for field in _GREEK_FIELDS
        )
    )

    enriched = len(complete)
    unavailable = (
        requested - enriched
    )

    field_presence = {
        field: any(
            contract.get(field) is not None
            for contract in contracts
        )
        for field in _GREEK_FIELDS
    }

    if state == "SUPPORTED" and enriched == requested:
        status = (
            Task9AngelGreeksProbeStatus.AVAILABLE
        )
        sanitized_reason = None
    elif state == "SUPPORTED" and enriched > 0:
        status = (
            Task9AngelGreeksProbeStatus.PARTIAL
        )
        sanitized_reason = (
            "OPTION_GREEKS_PARTIAL_EXACT_MATCH"
        )
    elif state in {
        "PROVIDER_FAILURE",
        "DATA_UNAVAILABLE",
        "DATA_MALFORMED",
        "SUPPORTED",
    }:
        status = (
            Task9AngelGreeksProbeStatus.UNAVAILABLE
        )
        sanitized_reason = (
            reason
            or "OPTION_GREEKS_UNAVAILABLE"
        )
    else:
        status = (
            Task9AngelGreeksProbeStatus.UNAVAILABLE
        )
        sanitized_reason = (
            reason
            or "OPTION_GREEKS_CAPTURE_STATE_INVALID"
        )

    return Task9AngelGreeksProofV1(
        proof_id=(
            "task9-angel-greeks:"
            f"NIFTY:NFO:"
            f"{capture.evaluated_at.isoformat()}"
        ),
        observed_at=capture.evaluated_at,
        market="NIFTY",
        exchange="NFO",
        status=status,
        requested_contract_count=requested,
        enriched_contract_count=enriched,
        unavailable_contract_count=unavailable,
        delta_present=field_presence["delta"],
        gamma_present=field_presence["gamma"],
        theta_present=field_presence["theta"],
        vega_present=field_presence["vega"],
        implied_volatility_present=(
            field_presence["iv"]
        ),
        source_ref=(
            "live-option-chain-builder-greeks"
            if enriched > 0
            else None
        ),
        incident_ref=None,
        sanitized_reason=sanitized_reason,
        execution_mode="PAPER",
        broker_order_submission=False,
        live_execution_eligible=False,
    )


__all__ = (
    "produce_task9_angel_greeks_proof",
    "produce_task9_angel_option_full_proof",
)
