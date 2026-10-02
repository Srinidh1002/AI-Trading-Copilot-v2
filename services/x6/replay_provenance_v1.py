"""Offline X6 replay auditor: independent witnesses, reproducible calculations.

The supplied witness must be retained outside the capture being audited. Hashes
prove consistency relative to that witness, not independent FYERS authenticity,
point-in-time availability, profitability, or permission to trade.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime

from services.x5.contracts_v1 import X5ChainCaptureV1, canonical_sha256
from services.x6.contracts_v1 import IST, MODEL_BY_MARKET, X6VolatilityCaptureV1
from services.x6.input_validation_v1 import X6InputValidationV1, validate_x6_input_v1
from services.x6.iv_greeks_v1 import X6IVGreeksResultV1, analyze_iv_greeks_v1
from services.x6.reference_pricing_v1 import X6ReferencePricingResultV1, price_x6_capture_v1
from services.x6.volatility_regime_v1 import (
    X6ATMHistoryPointV1,
    X6VolatilityRegimeResultV1,
    analyze_volatility_regime_v1,
)


def _sha(value: object) -> bool:
    return (
        isinstance(value, str) and len(value) == 64 and all(x in "0123456789abcdef" for x in value)
    )


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value) and value.strip() == value


def _aware(value: object) -> bool:
    return (
        isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    )


def _seals(rows: tuple) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((row.source_record_id, canonical_sha256(asdict(row))) for row in rows))


def _window(capture: X6VolatilityCaptureV1) -> tuple[tuple[float, str, str], ...]:
    return tuple(
        sorted(
            (float(row.strike), row.option_type, row.canonical_option_id)
            for row in capture.observations
        )
    )


def _fixed_authority(obj: object, schema: str) -> None:
    if (
        obj.schema_version != schema
        or obj.data_only is not True
        or obj.independent_vote is not False
        or any(
            getattr(obj, field) is not False
            for field in (
                "execution_authority",
                "risk_authority",
                "position_authority",
                "certification_authority",
                "live_execution_eligible",
            )
        )
    ):
        raise ValueError("X6 replay is data-only and has zero trading authority")


@dataclass(frozen=True, slots=True)
class X6ReplayReferenceInputV1:
    """Exact B1 parameters retained with a stored B1 output; never infer IV."""

    annual_volatility: float | None
    volatility_source_id: str | None
    volatility_verified: bool
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "X6_REPLAY_REFERENCE_INPUT_V1"

    def __post_init__(self) -> None:
        if type(self.volatility_verified) is not bool:
            raise ValueError("Volatility verification must be explicit")
        if self.annual_volatility is not None and (
            type(self.annual_volatility) not in (int, float) or not 0 <= self.annual_volatility <= 5
        ):
            raise ValueError("Volatility must be within the model range")
        if self.volatility_source_id is not None and not _text(self.volatility_source_id):
            raise ValueError("Invalid volatility source ID")
        if self.volatility_verified and (
            self.annual_volatility is None or not _text(self.volatility_source_id)
        ):
            raise ValueError("Verified volatility needs value and source ID")
        _fixed_authority(self, "X6_REPLAY_REFERENCE_INPUT_V1")


@dataclass(frozen=True, slots=True)
class X6ReplayFrameV1:
    """Self-contained frozen objects plus separately retainable digest witnesses."""

    source_x5: X5ChainCaptureV1
    capture: X6VolatilityCaptureV1
    validation: X6InputValidationV1
    iv_greeks: X6IVGreeksResultV1
    regime: X6VolatilityRegimeResultV1
    history: tuple[X6ATMHistoryPointV1, ...]
    history_minimum: int
    reference_input: X6ReplayReferenceInputV1 | None
    reference: X6ReferencePricingResultV1 | None
    expected_x5_sha256: str
    expected_x6_sha256: str
    expected_validation_sha256: str
    expected_iv_greeks_sha256: str
    expected_regime_sha256: str
    expected_reference_sha256: str | None
    expected_x5_row_seals: tuple[tuple[str, str], ...]
    expected_x6_row_seals: tuple[tuple[str, str], ...]
    expected_history_sha256: tuple[str, ...]
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "X6_REPLAY_FRAME_V1"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source_x5, X5ChainCaptureV1)
            or not isinstance(self.capture, X6VolatilityCaptureV1)
            or not isinstance(self.validation, X6InputValidationV1)
            or not isinstance(self.iv_greeks, X6IVGreeksResultV1)
            or not isinstance(self.regime, X6VolatilityRegimeResultV1)
        ):
            raise ValueError("X5, X6, validation, B2 and B3 objects are required")
        if (
            type(self.history) is not tuple
            or len(self.history) > 10_000
            or any(not isinstance(p, X6ATMHistoryPointV1) for p in self.history)
            or type(self.history_minimum) is not int
            or not 2 <= self.history_minimum <= 10_000
        ):
            raise ValueError("Bounded immutable history and an explicit minimum required")
        if (self.reference_input is None) != (self.reference is None) or (
            self.reference_input is not None
            and (
                not isinstance(self.reference_input, X6ReplayReferenceInputV1)
                or not isinstance(self.reference, X6ReferencePricingResultV1)
            )
        ):
            raise ValueError("B1 replay parameters and reference result must appear together")
        witness = (
            self.expected_x5_sha256,
            self.expected_x6_sha256,
            self.expected_validation_sha256,
            self.expected_iv_greeks_sha256,
            self.expected_regime_sha256,
        )
        if any(not _sha(x) for x in witness) or (
            self.expected_reference_sha256 is not None and not _sha(self.expected_reference_sha256)
        ):
            raise ValueError("Canonical SHA-256 witnesses required")
        if (self.reference is None) != (self.expected_reference_sha256 is None):
            raise ValueError("B1 reference witness must match B1 presence")
        for rows in (self.expected_x5_row_seals, self.expected_x6_row_seals):
            if (
                type(rows) is not tuple
                or tuple(sorted(rows)) != rows
                or len({pair[0] for pair in rows}) != len(rows)
                or any(
                    type(pair) is not tuple
                    or len(pair) != 2
                    or not _text(pair[0])
                    or not _sha(pair[1])
                    for pair in rows
                )
            ):
                raise ValueError("Canonical per-row SHA-256 witnesses required")
        if (
            type(self.expected_history_sha256) is not tuple
            or len(self.expected_history_sha256) != len(self.history)
            or any(not _sha(x) for x in self.expected_history_sha256)
        ):
            raise ValueError("Each history point requires an independent digest")
        _fixed_authority(self, "X6_REPLAY_FRAME_V1")


def seal_x6_replay_frame_v1(
    *,
    source_x5: X5ChainCaptureV1,
    capture: X6VolatilityCaptureV1,
    history: tuple[X6ATMHistoryPointV1, ...] = (),
    history_minimum: int = 20,
    reference_input: X6ReplayReferenceInputV1 | None = None,
) -> X6ReplayFrameV1:
    """Seal in-memory evidence once; retain the witnesses independently afterward.

    Re-sealing altered evidence does not reveal alteration. This helper does not
    independently confirm the provenance flags supplied by an external caller.
    """
    validation = validate_x6_input_v1(capture=capture, source_x5=source_x5)
    iv_greeks = analyze_iv_greeks_v1(capture=capture, source_x5=source_x5)
    regime = analyze_volatility_regime_v1(
        capture=capture,
        source_x5=source_x5,
        iv_greeks=iv_greeks,
        history=history,
        history_minimum=history_minimum,
    )
    reference = (
        None
        if reference_input is None
        else price_x6_capture_v1(
            capture=capture,
            source_x5=source_x5,
            annual_volatility=reference_input.annual_volatility,
            volatility_source_id=reference_input.volatility_source_id,
            volatility_verified=reference_input.volatility_verified,
        )
    )
    return X6ReplayFrameV1(
        source_x5,
        capture,
        validation,
        iv_greeks,
        regime,
        history,
        history_minimum,
        reference_input,
        reference,
        source_x5.sha256(),
        capture.sha256(),
        validation.sha256(),
        iv_greeks.sha256(),
        regime.sha256(),
        None if reference is None else reference.sha256(),
        _seals(source_x5.observations),
        _seals(capture.observations),
        tuple(point.sha256() for point in history),
    )


def _audit_frame(frame: X6ReplayFrameV1) -> None:
    x5, cap = frame.source_x5, frame.capture
    if (
        frame.expected_x5_sha256 != x5.sha256()
        or frame.expected_x6_sha256 != cap.sha256()
        or frame.expected_x5_row_seals != _seals(x5.observations)
        or frame.expected_x6_row_seals != _seals(cap.observations)
        or frame.expected_history_sha256 != tuple(p.sha256() for p in frame.history)
    ):
        raise ValueError("SOURCE_OR_ROW_WITNESS_MISMATCH")
    validation = validate_x6_input_v1(capture=cap, source_x5=x5)
    if frame.validation.sha256() != frame.expected_validation_sha256 or (
        validation.sha256() != frame.expected_validation_sha256
    ):
        raise ValueError("INPUT_VALIDATION_REPLAY_MISMATCH")
    b2 = analyze_iv_greeks_v1(capture=cap, source_x5=x5)
    if (
        frame.iv_greeks.sha256() != frame.expected_iv_greeks_sha256
        or b2.sha256() != frame.expected_iv_greeks_sha256
    ):
        raise ValueError("IV_GREEKS_REPLAY_MISMATCH")
    regime = analyze_volatility_regime_v1(
        capture=cap,
        source_x5=x5,
        iv_greeks=b2,
        history=frame.history,
        history_minimum=frame.history_minimum,
    )
    if (
        frame.regime.sha256() != frame.expected_regime_sha256
        or regime.sha256() != frame.expected_regime_sha256
    ):
        raise ValueError("VOLATILITY_REGIME_REPLAY_MISMATCH")
    if frame.reference_input is not None:
        p = frame.reference_input
        reference = price_x6_capture_v1(
            capture=cap,
            source_x5=x5,
            annual_volatility=p.annual_volatility,
            volatility_source_id=p.volatility_source_id,
            volatility_verified=p.volatility_verified,
        )
        if (
            frame.reference.sha256() != frame.expected_reference_sha256
            or reference.sha256() != frame.expected_reference_sha256
        ):
            raise ValueError("REFERENCE_PRICING_REPLAY_MISMATCH")


@dataclass(frozen=True, slots=True)
class X6ReplayRecordV1:
    market: str
    model: str
    option_expiry: date
    futures_contract_id: str | None
    session_id: str
    capture_id: str
    as_of: datetime
    source_x5_sha256: str
    source_x6_sha256: str
    validation_sha256: str
    iv_greeks_sha256: str
    regime_sha256: str
    reference_sha256: str | None
    history_witness_sha256: str
    x5_rows_witness_sha256: str
    x6_rows_witness_sha256: str
    capture_window_sha256: str
    transition: str
    observation_provenance: str
    model_assumption_changed: bool
    validation_status: str
    iv_greeks_status: str
    regime_status: str
    reference_status: str | None
    previous_record_sha256: str | None
    scope: str = "CAPTURED_STRIKE_WINDOW"
    cross_frame_metric_comparison_allowed: bool = False
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "X6_REPLAY_RECORD_V1"

    def __post_init__(self) -> None:
        if (
            self.market not in MODEL_BY_MARKET
            or self.model != MODEL_BY_MARKET[self.market]
            or not isinstance(self.option_expiry, date)
            or isinstance(self.option_expiry, datetime)
            or not _text(self.session_id)
            or not _text(self.capture_id)
            or not _aware(self.as_of)
        ):
            raise ValueError("Invalid replay record identity")
        if self.futures_contract_id is not None and not _text(self.futures_contract_id):
            raise ValueError("Invalid futures contract")
        hashes = (
            self.source_x5_sha256,
            self.source_x6_sha256,
            self.validation_sha256,
            self.iv_greeks_sha256,
            self.regime_sha256,
            self.history_witness_sha256,
            self.x5_rows_witness_sha256,
            self.x6_rows_witness_sha256,
            self.capture_window_sha256,
        )
        if (
            any(not _sha(x) for x in hashes)
            or (self.reference_sha256 is not None and not _sha(self.reference_sha256))
            or (self.previous_record_sha256 is not None and not _sha(self.previous_record_sha256))
        ):
            raise ValueError("Replay record needs canonical SHA-256")
        if self.transition not in {
            "FIRST_FRAME",
            "SAME_WINDOW",
            "WINDOW_CHANGED",
            "EXPIRY_CHANGED",
        }:
            raise ValueError("Unknown replay transition")
        if self.observation_provenance not in {"CLAIMED_POINT_IN_TIME", "RETROSPECTIVE_UNPROVEN"}:
            raise ValueError("Unknown provenance")
        if type(self.model_assumption_changed) is not bool or (
            self.validation_status not in {"AVAILABLE", "PARTIAL", "UNAVAILABLE"}
            or self.iv_greeks_status not in {"AVAILABLE", "PARTIAL", "RETROSPECTIVE", "UNAVAILABLE"}
            or self.regime_status not in {"AVAILABLE", "PARTIAL", "RETROSPECTIVE", "UNAVAILABLE"}
            or self.reference_status
            not in {None, "AVAILABLE", "PARTIAL", "RETROSPECTIVE", "UNAVAILABLE"}
        ):
            raise ValueError("Unknown replay status")
        if self.observation_provenance == "RETROSPECTIVE_UNPROVEN" and (
            self.iv_greeks_status == "AVAILABLE"
            or self.regime_status == "AVAILABLE"
            or self.reference_status == "AVAILABLE"
        ):
            raise ValueError("Retrospective replay cannot promote model evidence")
        if (
            self.scope != "CAPTURED_STRIKE_WINDOW"
            or self.cross_frame_metric_comparison_allowed is not False
        ):
            raise ValueError("No full-exchange coverage or cross-frame trade evidence")
        _fixed_authority(self, "X6_REPLAY_RECORD_V1")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def sha256(self) -> str:
        return canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class X6ReplayResultV1:
    market: str
    records: tuple[X6ReplayRecordV1, ...]
    source_frame_count: int
    expiry_transition_count: int
    window_transition_count: int
    retrospective_count: int
    final_record_sha256: str
    scope: str = "CAPTURED_STRIKE_WINDOW"
    cross_frame_metric_comparison_allowed: bool = False
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "X6_REPLAY_RESULT_V1"

    def __post_init__(self) -> None:
        if (
            self.market not in MODEL_BY_MARKET
            or type(self.records) is not tuple
            or not self.records
            or (
                len(self.records) != self.source_frame_count
                or any(
                    not isinstance(r, X6ReplayRecordV1) or r.market != self.market
                    for r in self.records
                )
            )
        ):
            raise ValueError("Invalid replay result identity and counts")
        if (
            type(self.source_frame_count) is not int
            or any(
                type(v) is not int or v < 0
                for v in (
                    self.expiry_transition_count,
                    self.window_transition_count,
                    self.retrospective_count,
                )
            )
            or self.expiry_transition_count
            != sum(r.transition == "EXPIRY_CHANGED" for r in self.records)
            or self.window_transition_count
            != sum(r.transition == "WINDOW_CHANGED" for r in self.records)
            or self.retrospective_count
            != sum(r.observation_provenance == "RETROSPECTIVE_UNPROVEN" for r in self.records)
        ):
            raise ValueError("Replay counters disagree with records")
        for index, record in enumerate(self.records):
            previous = self.records[index - 1].sha256() if index else None
            if record.previous_record_sha256 != previous:
                raise ValueError("Broken replay record hash chain")
        if (
            not _sha(self.final_record_sha256)
            or self.final_record_sha256 != self.records[-1].sha256()
        ):
            raise ValueError("Invalid final record digest")
        if (
            self.scope != "CAPTURED_STRIKE_WINDOW"
            or self.cross_frame_metric_comparison_allowed is not False
        ):
            raise ValueError("No cross-frame metric comparisons authorized")
        _fixed_authority(self, "X6_REPLAY_RESULT_V1")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def sha256(self) -> str:
        return canonical_sha256(self.to_dict())


def replay_x6_history_v1(
    *, frames: tuple[X6ReplayFrameV1, ...], expected_final_sha256: str | None = None
) -> X6ReplayResultV1:
    """Audit ordered captures and source witnesses without provider I/O.

    A final digest retained outside the replay detects later record or sequence
    changes. The function does not infer actual provider publication time.
    """
    if (
        type(frames) is not tuple
        or not 1 <= len(frames) <= 10_000
        or any(not isinstance(frame, X6ReplayFrameV1) for frame in frames)
    ):
        raise ValueError("A bounded, immutable nonempty replay sequence is required")
    if expected_final_sha256 is not None and not _sha(expected_final_sha256):
        raise ValueError("Final digest must be canonical SHA-256")
    market = frames[0].capture.context.market
    records: list[X6ReplayRecordV1] = []
    seen_captures: set[str] = set()
    seen_x5: set[str] = set()
    seen_row_ids: set[str] = set()
    previous: X6ReplayFrameV1 | None = None
    previous_hash: str | None = None
    for frame in frames:
        x5, cap = frame.source_x5, frame.capture
        if cap.context.market != market or x5.contract.market != market:
            raise ValueError("MIXED_MARKETS_IN_REPLAY")
        if cap.capture_id in seen_captures or x5.capture_id in seen_x5:
            raise ValueError("DUPLICATE_CAPTURE_ID")
        if previous is not None and cap.context.as_of <= previous.capture.context.as_of:
            raise ValueError("NONCHRONOLOGICAL_REPLAY")
        if previous is not None:
            prev_cap = previous.capture
            if (
                cap.context.as_of.astimezone(IST).date()
                == prev_cap.context.as_of.astimezone(IST).date()
                and cap.session_id != prev_cap.session_id
            ):
                raise ValueError("INCONSISTENT_SAME_DAY_SESSION")
            if (
                cap.context.as_of.astimezone(IST).date()
                != prev_cap.context.as_of.astimezone(IST).date()
                and cap.session_id == prev_cap.session_id
            ):
                raise ValueError("REUSED_SESSION_ACROSS_DAYS")
            if cap.context.option_expiry < prev_cap.context.option_expiry:
                raise ValueError("BACKWARD_EXPIRY_TRANSITION")
            if cap.context.option_expiry == prev_cap.context.option_expiry and (
                cap.context.option_expiry_at != prev_cap.context.option_expiry_at
                or cap.context.futures_contract_id != prev_cap.context.futures_contract_id
                or cap.context.futures_expiry != prev_cap.context.futures_expiry
            ):
                raise ValueError("SAME_EXPIRY_CONTRACT_OR_EXPIRY_INSTANT_DRIFT")
        _audit_frame(frame)
        for obs in x5.observations:
            if obs.source_record_id in seen_row_ids:
                raise ValueError("REUSED_X5_SOURCE_RECORD_ACROSS_CAPTURES")
            seen_row_ids.add(obs.source_record_id)
        seen_captures.add(cap.capture_id)
        seen_x5.add(x5.capture_id)
        prior_window = _window(previous.capture) if previous is not None else None
        current_window = _window(cap)
        if previous is None:
            transition = "FIRST_FRAME"
        elif cap.context.option_expiry != previous.capture.context.option_expiry:
            transition = "EXPIRY_CHANGED"
        elif prior_window != current_window:
            old_id = {(strike, side): option_id for strike, side, option_id in prior_window}
            if any(
                (strike, side) in old_id and old_id[strike, side] != option_id
                for strike, side, option_id in current_window
            ):
                raise ValueError("SAME_EXPIRY_CANONICAL_OPTION_ID_DRIFT")
            transition = "WINDOW_CHANGED"
        else:
            transition = "SAME_WINDOW"
        ctx = cap.context
        model_assumption_changed = previous is not None and (
            ctx.model != previous.capture.context.model
            or ctx.reference_unit != previous.capture.context.reference_unit
            or ctx.rate_source_id != previous.capture.context.rate_source_id
            or ctx.annual_risk_free_rate != previous.capture.context.annual_risk_free_rate
            or ctx.rate_verified != previous.capture.context.rate_verified
            or ctx.dividend_source_id != previous.capture.context.dividend_source_id
            or ctx.annual_dividend_yield != previous.capture.context.annual_dividend_yield
            or ctx.dividend_verified != previous.capture.context.dividend_verified
            or ctx.reference_verified != previous.capture.context.reference_verified
            or ctx.expiry_instant_verified != previous.capture.context.expiry_instant_verified
            or ctx.futures_identity_verified != previous.capture.context.futures_identity_verified
            or frame.reference_input != previous.reference_input
            or ctx.rate_convention != previous.capture.context.rate_convention
            or ctx.day_count != previous.capture.context.day_count
        )
        provenance = (
            "CLAIMED_POINT_IN_TIME"
            if cap.point_in_time_verified
            and x5.point_in_time_verified
            and not x5.historical_retrieval
            else "RETROSPECTIVE_UNPROVEN"
        )
        record = X6ReplayRecordV1(
            market=market,
            model=ctx.model,
            option_expiry=ctx.option_expiry,
            futures_contract_id=ctx.futures_contract_id,
            session_id=cap.session_id,
            capture_id=cap.capture_id,
            as_of=ctx.as_of,
            source_x5_sha256=frame.expected_x5_sha256,
            source_x6_sha256=frame.expected_x6_sha256,
            validation_sha256=frame.expected_validation_sha256,
            iv_greeks_sha256=frame.expected_iv_greeks_sha256,
            regime_sha256=frame.expected_regime_sha256,
            reference_sha256=frame.expected_reference_sha256,
            history_witness_sha256=canonical_sha256(frame.expected_history_sha256),
            x5_rows_witness_sha256=canonical_sha256(frame.expected_x5_row_seals),
            x6_rows_witness_sha256=canonical_sha256(frame.expected_x6_row_seals),
            capture_window_sha256=canonical_sha256(current_window),
            transition=transition,
            observation_provenance=provenance,
            model_assumption_changed=model_assumption_changed,
            validation_status=frame.validation.status,
            iv_greeks_status=frame.iv_greeks.status,
            regime_status=frame.regime.status,
            reference_status=None if frame.reference is None else frame.reference.status,
            previous_record_sha256=previous_hash,
        )
        records.append(record)
        previous_hash = record.sha256()
        previous = frame
    result = X6ReplayResultV1(
        market=market,
        records=tuple(records),
        source_frame_count=len(records),
        expiry_transition_count=sum(r.transition == "EXPIRY_CHANGED" for r in records),
        window_transition_count=sum(r.transition == "WINDOW_CHANGED" for r in records),
        retrospective_count=sum(
            r.observation_provenance == "RETROSPECTIVE_UNPROVEN" for r in records
        ),
        final_record_sha256=records[-1].sha256(),
    )
    if expected_final_sha256 is not None and result.sha256() != expected_final_sha256:
        raise ValueError("EXTERNALLY_RETAINED_FINAL_DIGEST_MISMATCH")
    return result
