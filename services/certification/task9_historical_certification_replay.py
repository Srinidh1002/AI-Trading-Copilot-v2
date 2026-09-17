"""Isolated, non-counting Task 9 completed-session historical replay."""
from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from services.bse_holiday_calendar import get_bse_holiday_calendar
from services.data_normalizer import normalize_angel_candles
from services.market.live_multi_timeframe_data import required_closed_candle_at
from services.nse_holiday_calendar import get_nse_holiday_calendar
from services.contracts.pre_entry_market_action_v1 import PreEntryMarketActionV1
from services.contracts.prediction_outcome_evaluation_input_v1 import PredictionOutcomeEvaluationInputV1
from services.contracts.prediction_record_v1 import PredictionRecordV1
from services.paper_orchestration.prediction_outcome_evaluator import evaluate_prediction_outcome


IST = ZoneInfo("Asia/Kolkata")
REPLAY_ROOT = Path("data/paper_trading/certified_runtime/task9_historical_replay")
LIVE_ROOT = Path("data/paper_trading/certified_runtime/task9")
RECORD_SOURCE = "HISTORICAL_REPLAY"
MARKETS = (("NIFTY", "NSE", "99926000"), ("SENSEX", "BSE", "99919000"))
TIMEFRAMES = ("5m", "15m", "1h", "1d")
_CASH_OPEN = time(9, 15)
_CASH_CLOSE = time(15, 30)


class Task9HistoricalReplayError(RuntimeError):
    """Typed local replay rejection; never a live-session failure."""


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(name)
    return value.astimezone(IST)


def _trading_date(value: object) -> date:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise TypeError("trading_date")
    if value.weekday() >= 5 or get_nse_holiday_calendar().is_holiday(value) or get_bse_holiday_calendar().is_holiday(value):
        raise Task9HistoricalReplayError("HISTORICAL_REPLAY_NON_TRADING_DATE")
    return value


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class Task9HistoricalReplayReceiptStore:
    """Atomic idempotent store deliberately separate from Task 9 live roots."""

    schema_version = "task9_historical_replay_receipts.v1"

    def __init__(self, root: str | Path = REPLAY_ROOT):
        self.root = Path(root)
        try:
            if self.root.resolve() == LIVE_ROOT.resolve():
                raise Task9HistoricalReplayError("HISTORICAL_REPLAY_LIVE_ROOT_FORBIDDEN")
        except OSError as exc:
            raise Task9HistoricalReplayError("HISTORICAL_REPLAY_LIVE_ROOT_FORBIDDEN") from exc
        self.path = self.root / "receipts.json"

    def _load(self) -> dict[str, object]:
        if not self.path.exists():
            return {"schema_version": self.schema_version, "receipts": {}}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise Task9HistoricalReplayError("HISTORICAL_REPLAY_CACHE_CORRUPT") from exc
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != self.schema_version
            or not isinstance(value.get("receipts"), dict)
        ):
            raise Task9HistoricalReplayError("HISTORICAL_REPLAY_CACHE_CORRUPT")
        return value

    def load(self, replay_id: str) -> dict[str, object] | None:
        return self._load()["receipts"].get(replay_id)

    def save(self, receipt: dict[str, object]) -> dict[str, object]:
        replay_id = receipt.get("replay_id")
        if not isinstance(replay_id, str) or not replay_id:
            raise ValueError("replay_id")

        try:
            canonical = json.loads(
                json.dumps(
                    receipt,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
            )
        except (TypeError, ValueError) as exc:
            raise Task9HistoricalReplayError(
                "HISTORICAL_REPLAY_RECEIPT_NOT_JSON_SAFE"
            ) from exc

        if not isinstance(canonical, dict):
            raise Task9HistoricalReplayError(
                "HISTORICAL_REPLAY_RECEIPT_NOT_JSON_SAFE"
            )

        document = self._load()
        existing = document["receipts"].get(replay_id)

        if existing is not None:
            if existing != canonical:
                raise Task9HistoricalReplayError(
                    "HISTORICAL_REPLAY_ID_CONFLICT"
                )
            return existing

        document["receipts"][replay_id] = canonical
        _atomic_json(self.path, document)

        return canonical


class Task9HistoricalCertificationReplay:
    """Thin replay adapter using injected completed-session candle authority only."""

    def __init__(self, *, completed_session_reader: Callable | None = None, receipt_store: Task9HistoricalReplayReceiptStore | None = None, production_action_reader: Callable | None = None, production_lifecycle_evaluator: Callable | None = None, decision_engine: Callable | None = None, report_publisher: Callable | None = None):
        if completed_session_reader is not None and not callable(completed_session_reader):
            raise TypeError("completed_session_reader")
        if decision_engine is not None and not callable(decision_engine):
            raise TypeError("decision_engine")
        if production_action_reader is not None and not callable(production_action_reader):
            raise TypeError("production_action_reader")
        if production_lifecycle_evaluator is not None and not callable(production_lifecycle_evaluator):
            raise TypeError("production_lifecycle_evaluator")
        if report_publisher is not None and not callable(report_publisher):
            raise TypeError("report_publisher")
        self.completed_session_reader = completed_session_reader
        self.receipt_store = receipt_store or Task9HistoricalReplayReceiptStore()
        self.decision_engine = decision_engine
        self.production_action_reader = production_action_reader
        self.production_lifecycle_evaluator = production_lifecycle_evaluator
        self.report_publisher = report_publisher

    @staticmethod
    def _replay_id(trading_date: date, cycle_boundary: datetime) -> str:
        return f"task9-historical:{trading_date.isoformat()}:{cycle_boundary.isoformat()}"

    @staticmethod
    def _market_id(trading_date: date, market: str, cycle_boundary: datetime) -> str:
        return f"task9-historical:{trading_date.isoformat()}:{market}:{cycle_boundary.isoformat()}"

    def _read_market(self, *, market: str, exchange: str, token: str, trading_date: date, cycle_boundary: datetime) -> dict[str, object]:
        if self.completed_session_reader is None:
            raise Task9HistoricalReplayError("HISTORICAL_REPLAY_READER_REQUIRED")
        try:
            raw = self.completed_session_reader(
                market=market,
                exchange=exchange,
                symboltoken=token,
                trading_date=trading_date,
            )
        except Task9HistoricalReplayError:
            raise
        except Exception as exc:
            raise Task9HistoricalReplayError(
                "HISTORICAL_REPLAY_READER_FAILURE"
            ) from exc
        if not isinstance(raw, Mapping) or set(raw) != set(TIMEFRAMES):
            raise Task9HistoricalReplayError("HISTORICAL_REPLAY_REQUIRED_TIMEFRAME_MISSING")
        normalized: dict[str, object] = {}
        for timeframe in TIMEFRAMES:
            try:
                frame = normalize_angel_candles(raw[timeframe])
            except (TypeError, ValueError) as exc:
                raise Task9HistoricalReplayError("HISTORICAL_REPLAY_MALFORMED_CANDLES") from exc
            timestamps = tuple(value.to_pydatetime().astimezone(IST) for value in frame["timestamp"])
            required = required_closed_candle_at(
                timeframe,
                datetime.combine(trading_date, _CASH_CLOSE, IST),
                exchange=exchange,
            )
            if timeframe == "1d":
                # An intraday replay decision uses only daily sessions completed
                # before the replay date; a current-day daily candle is forming
                # evidence at every intraday decision boundary.
                if (
                    any(value.date() >= trading_date for value in timestamps)
                    or not timestamps
                ):
                    raise Task9HistoricalReplayError("HISTORICAL_REPLAY_INCOMPLETE_OR_FUTURE_SESSION")
                if any(value.time().replace(tzinfo=None) != time.min for value in timestamps):
                    raise Task9HistoricalReplayError("HISTORICAL_REPLAY_INCOMPLETE_SESSION")
            else:
                if any(value.date() != trading_date for value in timestamps):
                    raise Task9HistoricalReplayError("HISTORICAL_REPLAY_INCOMPLETE_OR_FUTURE_SESSION")
                minutes = {"5m": 5, "15m": 15, "1h": 60}[timeframe]
                # Angel labels intraday candles by their start. Its hourly
                # bars are wall-clock aligned (09:00, 10:00, ...), unlike
                # the 5m/15m cash-session bars that begin at 09:15.
                start = time(9, 0) if timeframe == "1h" else _CASH_OPEN
                current = datetime.combine(trading_date, start, IST)
                expected_values = []
                while current <= required:
                    expected_values.append(current)
                    current += timedelta(minutes=minutes)
                expected = tuple(expected_values)
            if timeframe != "1d" and timestamps != expected:
                raise Task9HistoricalReplayError("HISTORICAL_REPLAY_INCOMPLETE_SESSION")
            normalized[timeframe] = tuple(
                {"timestamp": timestamp.isoformat(), "open": float(row.Open), "high": float(row.High), "low": float(row.Low), "close": float(row.Close), "volume": float(row.Volume)}
                for timestamp, row in zip(timestamps, frame.itertuples(index=False))
            )
        return normalized

    def _decision(self, evidence: dict[str, object]) -> dict[str, object]:
        if self.production_action_reader is not None:
            action = self.production_action_reader(evidence)
            if type(action) is not PreEntryMarketActionV1:
                raise Task9HistoricalReplayError("HISTORICAL_REPLAY_INVALID_PRODUCTION_ACTION")
            if (action.underlying_symbol, action.exchange) != (evidence["market"], evidence["exchange"]):
                raise Task9HistoricalReplayError("HISTORICAL_REPLAY_ACTION_IDENTITY_MISMATCH")
            if action.evaluated_at != datetime.fromisoformat(evidence["cycle_boundary"]):
                raise Task9HistoricalReplayError("HISTORICAL_REPLAY_ACTION_TIMESTAMP_MISMATCH")
            replay_action = "NO_TRADE" if action.action == "UNAVAILABLE" else action.action
            return {
                "action": replay_action,
                "reason": action.reasons[0] if action.reasons else "PRODUCTION_ACTION_UNAVAILABLE",
                "authority": "services.analysis.pre_entry_action_resolver.resolve_pre_entry_market_action",
                "action_id": action.action_id,
            }
        if self.decision_engine is None:
            return {"action": "NO_TRADE", "reason": "REPLAY_CAPABILITY_UNAVAILABLE_LIVE_QUOTE_AND_GREEKS", "authority": "replay_fail_closed_capability_policy"}
        value = self.decision_engine(evidence)
        if isinstance(value, str):
            value = {"action": value}
        if not isinstance(value, Mapping) or value.get("action") not in {"CALL", "PUT", "WAIT", "NO_TRADE"}:
            raise Task9HistoricalReplayError("HISTORICAL_REPLAY_INVALID_DECISION")
        return {"action": value["action"], "reason": str(value.get("reason", "INJECTED_REPLAY_DECISION")), "authority": "test_or_compatibility_injected_decision"}

    @staticmethod
    def _objective_outcome(*, action: str, evidence: dict[str, object], future: tuple[dict[str, object], ...], cycle_boundary: datetime, production_lifecycle_evaluator: Callable | None) -> dict[str, object]:
        """Use the production prediction outcome evaluator; never invent option levels."""
        if action in {"CALL", "PUT"} and production_lifecycle_evaluator is not None:
            result = production_lifecycle_evaluator(action=action, evidence=evidence, future_candles=future)
            if not isinstance(result, Mapping) or not all(key in result for key in ("planner_authority", "terminal_authority", "entry", "stop", "targets", "terminal_outcome")):
                raise Task9HistoricalReplayError("HISTORICAL_REPLAY_INVALID_PRODUCTION_LIFECYCLE")
            return dict(result)
        if action in {"CALL", "PUT"}:
            return {"status": "UNEVALUABLE", "reason": "HISTORICAL_REPLAY_PRODUCTION_OPTION_PLAN_UNAVAILABLE", "authority": "production_option_planner_required"}
        if not future:
            return {"status": "UNEVALUABLE", "reason": "HISTORICAL_REPLAY_FUTURE_OBSERVATION_UNAVAILABLE", "authority": "services.paper_orchestration.prediction_outcome_evaluator.evaluate_prediction_outcome"}
        start = evidence["timeframes"]["5m"][-1]["close"]
        terminal = future[-1]
        # PredictionOutcomeRecordV1 deliberately has no NO_TRADE vocabulary;
        # production evaluates an abstention through its WAIT outcome policy.
        outcome_action = "WAIT" if action == "NO_TRADE" else action
        direction = {"CALL": "BULLISH", "PUT": "BEARISH"}.get(outcome_action, "NEUTRAL")
        selected = action in {"CALL", "PUT"}
        prediction = PredictionRecordV1(
            prediction_id=f"{evidence['market_replay_id']}:prediction", parent_cycle_id=evidence["market_replay_id"], decision_result_id=f"{evidence['market_replay_id']}:decision", child_result_id=f"{evidence['market_replay_id']}:child", observation_id=f"{evidence['market_replay_id']}:observation", underlying_symbol=evidence["market"], exchange=evidence["exchange"], requested_at=cycle_boundary, completed_at=cycle_boundary, market_timestamp=cycle_boundary, received_at=cycle_boundary, start_underlying_price=start, terminal_status="COMPLETED", candidate_id=f"{evidence['market_replay_id']}:candidate" if selected else None, predicted_direction=direction, eligibility="ELIGIBLE" if selected else "INELIGIBLE", confidence=1.0 if selected else 0.0, score=1.0 if selected else 0.0, rank_value=1.0 if selected else 0.0, eligible_for_comparison=selected, outcome_reason="SELECTED" if selected else "INELIGIBLE", parent_decision="SELECTED" if selected else "NO_TRADE", parent_selected=selected,
            predicted_action=outcome_action,
        )
        due = datetime.fromisoformat(terminal["timestamp"])
        outcome = evaluate_prediction_outcome(PredictionOutcomeEvaluationInputV1(prediction=prediction, evaluation_observation_id=f"{evidence['market_replay_id']}:outcome:{due.isoformat()}", start_underlying_price=start, end_underlying_price=terminal["close"], evaluation_due_at=due, evaluated_at=due, evaluation_horizon_seconds=(due - cycle_boundary).total_seconds(), threshold_percent=0.20))
        return {"status": outcome.outcome, "evaluation_kind": outcome.evaluation_kind, "evaluated_prediction_action": outcome_action, "movement_percent": outcome.movement_percent, "authority": "services.paper_orchestration.prediction_outcome_evaluator.evaluate_prediction_outcome"}

    def replay(self, *, trading_date: date, cycle_boundary: datetime) -> dict[str, object]:
        trading_date = _trading_date(trading_date)
        cycle_boundary = _aware(cycle_boundary, "cycle_boundary")
        if (
            cycle_boundary.date() != trading_date
            or not _CASH_OPEN <= cycle_boundary.time().replace(tzinfo=None) <= _CASH_CLOSE
        ):
            raise Task9HistoricalReplayError("HISTORICAL_REPLAY_INVALID_CYCLE_BOUNDARY")
        replay_id = self._replay_id(trading_date, cycle_boundary)
        existing = self.receipt_store.load(replay_id)
        if existing is not None:
            return existing
        markets: dict[str, object] = {}
        for market, exchange, token in MARKETS:
            try:
                completed_session = self._read_market(market=market, exchange=exchange, token=token, trading_date=trading_date, cycle_boundary=cycle_boundary)
            except Task9HistoricalReplayError as exc:
                markets[market] = {"market": market, "exchange": exchange, "market_replay_id": self._market_id(trading_date, market, cycle_boundary), "record_source": RECORD_SOURCE, "status": "UNAVAILABLE", "reason": str(exc)}
                continue
            try:
                timeframes = {
                    timeframe: tuple(
                        candle
                        for candle in candles
                        if datetime.fromisoformat(candle["timestamp"])
                        <= required_closed_candle_at(
                            timeframe,
                            cycle_boundary,
                            exchange=exchange,
                        )
                    )
                    for timeframe, candles in completed_session.items()
                }
                if any(not candles for candles in timeframes.values()):
                    raise Task9HistoricalReplayError("HISTORICAL_REPLAY_INCOMPLETE_OR_FUTURE_SESSION")
                evidence = {"market": market, "exchange": exchange, "market_replay_id": self._market_id(trading_date, market, cycle_boundary), "timeframes": timeframes, "record_source": RECORD_SOURCE, "cycle_boundary": cycle_boundary.isoformat()}
                decision = self._decision(evidence)
                decision_closed = required_closed_candle_at(
                    "5m",
                    cycle_boundary,
                    exchange=exchange,
                )
                future = tuple(
                    candle
                    for candle in completed_session["5m"]
                    if datetime.fromisoformat(candle["timestamp"]) > decision_closed
                )
                markets[market] = {
                    **evidence,
                    "decision": decision,
                    "outcome": self._objective_outcome(action=decision["action"], evidence=evidence, future=future, cycle_boundary=cycle_boundary, production_lifecycle_evaluator=self.production_lifecycle_evaluator),
                    "outcome_5m": future,
                    "status": "COMPLETED",
                }
            except Task9HistoricalReplayError as exc:
                markets[market] = {"market": market, "exchange": exchange, "market_replay_id": self._market_id(trading_date, market, cycle_boundary), "record_source": RECORD_SOURCE, "status": "UNAVAILABLE", "reason": str(exc)}
            except Exception:
                markets[market] = {"market": market, "exchange": exchange, "market_replay_id": self._market_id(trading_date, market, cycle_boundary), "record_source": RECORD_SOURCE, "status": "UNAVAILABLE", "reason": "HISTORICAL_REPLAY_INTERNAL_ERROR"}
        receipt = {"schema_version": "task9_historical_replay_receipt.v1", "replay_id": replay_id, "trading_date": trading_date.isoformat(), "cycle_boundary": cycle_boundary.isoformat(), "record_source": RECORD_SOURCE, "execution_mode": "PAPER", "broker_order_submission": False, "live_execution_eligible": False, "counting_status": "EXCLUDED_HISTORICAL_REPLAY", "markets": markets}
        saved = self.receipt_store.save(receipt)
        if self.report_publisher is not None:
            try:
                self.report_publisher(saved)
            except Exception:
                pass
        return saved
