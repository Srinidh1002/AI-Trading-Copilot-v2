"""Task 9 current-session certification draft and derived read-only progress."""
from __future__ import annotations

import json
import os
import hashlib
from datetime import date, datetime
from pathlib import Path

from services.certification.task9_daily_report_index import Task9DailyReportIndex
from services.certification.task9_daily_report_recovery import recover_task9_daily_reports
from services.certification.task9_live_paper_certification_progress_builder import build_task9_live_paper_certification_progress_from_raw
from services.certification.task9_live_paper_trade_counting_evaluator import evaluate_task9_live_paper_trade_counting
from services.certification.task9_prediction_lifecycle_outcome_store import Task9PredictionLifecycleOutcomeStore
from services.certification.task9_prediction_lifecycle_reconciliation_store import Task9PredictionLifecycleReconciliationStore
from services.certification.task9_prediction_paper_trade_binding_store import Task9PredictionPaperTradeBindingStore
from services.contracts.prediction_certification_counting_decision_v1 import PredictionCertificationCountingDecisionV1
from services.contracts.task9_live_paper_trade_counting_input_v1 import Task9LivePaperTradeCountingInputV1
from services.paper_orchestration.prediction_ledger import PredictionLedger
from services.paper_trading.paper_trade_persistence_service import PaperTradePersistenceService
from services.reports.paper_certification_daily_report import build_paper_certification_daily_report
from services.reporting.paper_certification_report_archive import PaperCertificationReportArchive


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True); tmp = path.with_suffix(path.suffix + ".tmp")
    try: tmp.write_text(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False), encoding="utf-8"); os.replace(tmp, path)
    finally: tmp.unlink(missing_ok=True)


def _semantic_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _content_hash(value):
    normalized = dict(value)
    normalized["report_id"] = "TASK9_REPORT_ID_NORMALIZED"
    return _semantic_hash(normalized)


class Task9CertificationPublicationAuthority:
    """Rebuilds, never increments, the mutable current-session report draft."""
    def __init__(self, *, official_run_id, official_start_at, root, prediction_ledger: PredictionLedger, binding_store: Task9PredictionPaperTradeBindingStore, outcome_store: Task9PredictionLifecycleOutcomeStore, reconciliation_store: Task9PredictionLifecycleReconciliationStore, trade_persistence_service: PaperTradePersistenceService, starting_capital: float):
        if type(official_run_id) is not str or not official_run_id.strip() or not isinstance(official_start_at, datetime) or official_start_at.tzinfo is None or type(starting_capital) not in (int, float) or starting_capital <= 0: raise ValueError("publication identity")
        self.official_run_id, self.official_start_at, self.root, self.starting_capital = official_run_id.strip(), official_start_at, Path(root), float(starting_capital)
        self.prediction_ledger, self.binding_store, self.outcome_store, self.reconciliation_store, self.trade_persistence_service = prediction_ledger, binding_store, outcome_store, reconciliation_store, trade_persistence_service
        self.archive_root = self.root / "certification_reports"; self.index = Task9DailyReportIndex(official_run_id=self.official_run_id, file_path=self.root / "daily-report-index.json")

    def _draft_path(self, session_date): return self.root / "current-session-reports" / f"{session_date.isoformat()}.json"
    def _draft_report_id(self, session_date): return f"task9-draft:{self.official_run_id}:{session_date.isoformat()}"
    def _finalized_report_id(self, session_date):
        report_id = f"task9-daily-{self.official_run_id}-{session_date.isoformat()}"
        return PaperCertificationReportArchive._safe_report_id(report_id)
    def _archive_path(self, session_date): return Path("daily") / session_date.isoformat() / f"{self._finalized_report_id(session_date)}.json"

    def _build_report(self, *, session_date, evaluated_at, report_id=None):
        predictions = tuple(item for item in (self.prediction_ledger.recover(raw["prediction_id"]) for raw in self.prediction_ledger.all_records()) if item is not None and item.completed_at.date() == session_date)
        outcomes = tuple(item for item in (self.outcome_store.recover(prediction.prediction_id) for prediction in predictions) if item is not None)
        reconciliations = tuple(item for item in (self.reconciliation_store.recover(prediction.prediction_id) for prediction in predictions) if item is not None)
        positions = []
        position_bindings = []
        for prediction in predictions:
            binding = self.binding_store.by_prediction(prediction.prediction_id)
            if binding is not None:
                snapshot = self.trade_persistence_service.get(binding.paper_trade_id)
                if snapshot is not None and snapshot.position is not None:
                    positions.append(snapshot.position)
                    position_bindings.append((prediction.prediction_id, snapshot.position.position_id))
        return build_paper_certification_daily_report(report_id=self._draft_report_id(session_date) if report_id is None else report_id, session_date=session_date, generated_at=evaluated_at, starting_capital=self.starting_capital, predictions=predictions, counting_decisions=tuple(self._decision(prediction, self.outcome_store.recover(prediction.prediction_id), self.reconciliation_store.recover(prediction.prediction_id), evaluated_at) for prediction in predictions), lifecycle_outcomes=outcomes, reconciliations=reconciliations, positions=tuple(positions), prediction_position_ids=tuple(position_bindings))

    def _build_finalized_report(self, *, session_date, evaluated_at):
        return self._build_report(session_date=session_date, evaluated_at=evaluated_at, report_id=self._finalized_report_id(session_date))

    def _progress(self, report=None):
        archived = recover_task9_daily_reports(index=self.index, official_run_id=self.official_run_id, archive_root=self.archive_root)
        archived_by_session = {item["session_date"]: item for item in archived}
        if report is not None:
            current = report.to_dict()
            archived_same = archived_by_session.get(current["session_date"])
            if archived_same is not None:
                if _content_hash(archived_same) != _content_hash(current):
                    raise ValueError("TASK9_FINALIZED_DRAFT_CONFLICT")
            else:
                archived_by_session[current["session_date"]] = current
        progress = build_task9_live_paper_certification_progress_from_raw(tuple(archived_by_session[key] for key in sorted(archived_by_session)))
        _write(self.root / "task9-live-paper-certification-progress.json", progress.to_dict())
        return progress

    def finalize_session(self, *, session_date, evaluated_at, session_closed):
        """Archive one explicitly closed past Task 9 session, then index it."""
        if type(session_date) is not date or not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None or type(session_closed) is not bool:
            raise ValueError("Task9 daily finalization input")
        if session_closed is not True or session_date >= evaluated_at.date():
            raise ValueError("TASK9_SESSION_NOT_CLOSED")
        relative = self._archive_path(session_date)
        indexed = next((item for item in self.index.all_records() if item["session_date"] == session_date.isoformat()), None)
        if indexed is not None:
            recover_task9_daily_reports(index=self.index, official_run_id=self.official_run_id, archive_root=self.archive_root)
            if indexed["archive_path"] != relative.as_posix() or indexed["report_id"] != self._finalized_report_id(session_date):
                raise ValueError("TASK9_DAILY_REPORT_INDEX_CONFLICT")
            return self._progress()
        report = self._build_finalized_report(session_date=session_date, evaluated_at=evaluated_at)
        archive = PaperCertificationReportArchive(self.archive_root)
        archive_path = self.archive_root / relative
        if archive_path.exists():
            try: raw = json.loads(archive_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc: raise ValueError("invalid archived Task 9 daily report JSON") from exc
            if type(raw) is not dict or raw.get("schema_version") != "paper_certification_daily_report.v1" or raw.get("report_status") != "RECONCILED" or raw.get("report_id") != report.report_id or raw.get("session_date") != session_date.isoformat() or raw.get("execution_mode") != "PAPER" or raw.get("broker_order_submission") is not False or raw.get("live_execution_eligible") is not False or raw.get("read_only") is not True:
                raise ValueError("TASK9_DAILY_REPORT_INDEX_CONFLICT")
            semantic_hash = _semantic_hash(raw)
        else:
            archive.save(report)
            semantic_hash = report.semantic_hash
        self.index.save(report_id=report.report_id, session_date=session_date.isoformat(), semantic_hash=semantic_hash, archive_path=relative.as_posix())
        return self._progress()

    def rollover(self, *, session_date, evaluated_at):
        """Finalize only draft sessions strictly before the supplied session date."""
        if type(session_date) is not date or not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None:
            raise ValueError("Task9 rollover input")
        draft_root = self.root / "current-session-reports"
        if not draft_root.exists(): return ()
        finalized = []
        for path in sorted(draft_root.glob("*.json")):
            try: draft_date = date.fromisoformat(path.stem)
            except ValueError: raise ValueError("invalid Task9 daily draft path")
            if draft_date < session_date:
                self.finalize_session(session_date=draft_date, evaluated_at=evaluated_at, session_closed=True)
                finalized.append(draft_date)
        return tuple(finalized)
    def _child_failure(self, prediction):
        cycle_id = f"task9:{self.official_run_id}:{prediction.parent_cycle_id}"
        path = self.root / "task9-cycle-results" / f"{hashlib.sha256(cycle_id.encode('utf-8')).hexdigest()}.json"
        if not path.exists():
            return None
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("invalid persisted Task 9 cycle result") from exc
        if type(document) is not dict or set(document) != {"cycle_id", "payload"} or document["cycle_id"] != cycle_id:
            raise ValueError("persisted Task 9 cycle result identity")
        payload = document["payload"]
        if type(payload) is not dict or payload.get("cycle_id") != cycle_id or type(payload.get("market_results")) is not list:
            raise ValueError("persisted Task 9 cycle result payload")
        matches = [item for item in payload["market_results"] if type(item) is list and len(item) == 3 and item[0] == prediction.underlying_symbol]
        if len(matches) != 1:
            raise ValueError("persisted Task 9 market result identity")
        _, status, detail = matches[0]
        if status == "INTERNAL_CHILD_FAILURE":
            reason = detail.get("reason_code") if type(detail) is dict else None
            if type(reason) is not str or not reason.startswith("INTERNAL_CHILD_FAILURE_"):
                raise ValueError("persisted Task 9 child failure")
            return "EXCLUDED_CHILD_FAILURE", (reason,)
        if status == "DATA_INCIDENT":
            reasons = detail.get("reason_codes") if type(detail) is dict else None
            if type(reasons) is not list or not all(type(item) is str and item for item in reasons):
                raise ValueError("persisted Task 9 data incident")
            return "EXCLUDED_DATA_INCIDENT", tuple(dict.fromkeys(("DATA_INCIDENT", *reasons)))
        return None

    def _decision(self, prediction, outcome, reconciliation, evaluated_at):
        child_failure = self._child_failure(prediction)
        if child_failure is not None:
            status, reasons = child_failure
            return PredictionCertificationCountingDecisionV1(decision_id=f"task9-report:child-failure:{self.official_run_id}:{prediction.prediction_id}", counting_key="0" * 64, prediction_id=prediction.prediction_id, outcome_id=None, official_run_id=self.official_run_id, underlying_symbol=prediction.underlying_symbol, exchange=prediction.exchange, predicted_action=prediction.predicted_action, parent_decision=prediction.parent_decision, status=status, countable=False, pending=False, reason_codes=reasons, policy_id="task9-live-counting", policy_version="1.0", system_version="task9", provider_version="task9", evaluated_at=evaluated_at)
        task9 = evaluate_task9_live_paper_trade_counting(Task9LivePaperTradeCountingInputV1(prediction=prediction, lifecycle_outcome=outcome, reconciliation=reconciliation, record_source="LIVE_REAL_TIME", session_status="REAL_TIME_MARKET_SESSION", evidence_status="VALID", official_run_id=self.official_run_id, record_run_id=self.official_run_id, official_start_at=self.official_start_at, evaluated_at=evaluated_at))
        trade = task9.status == "COUNTED_TRADE"; non_trade = task9.status == "NO_TRADE"; wait = task9.status == "WAIT"; pending = task9.pending
        if trade:
            status = "INCLUDED"
        elif non_trade:
            status = "INCLUDED_NON_TRADE"
        elif wait:
            status = "INCLUDED_WAIT"
        elif pending:
            status = "PENDING_OUTCOME"
        elif outcome is not None and outcome.evaluation_status == "DATA_UNAVAILABLE":
            status = "EXCLUDED_DATA_UNAVAILABLE"
        else:
            status = {
                "EXCLUDED_DATA_INCIDENT": "EXCLUDED_DATA_INCIDENT",
                "EXCLUDED_INVALID_EVIDENCE": "EXCLUDED_INVALID_EVIDENCE",
                "EXCLUDED_REPLAY": "EXCLUDED_REPLAY",
                "EXCLUDED_RUN_MISMATCH": "EXCLUDED_RUN_MISMATCH",
                "EXCLUDED_PRE_START": "EXCLUDED_PRE_START",
                "EXCLUDED_OUT_OF_SESSION": "EXCLUDED_OUT_OF_SESSION",
            }.get(task9.status, "EXCLUDED_UNEVALUABLE_OUTCOME")
        return PredictionCertificationCountingDecisionV1(decision_id=f"task9-report:{task9.decision_id}", counting_key=("1" * 64) if trade else ("0" * 64), prediction_id=prediction.prediction_id, outcome_id=(outcome.outcome_id if trade or non_trade or wait else None), official_run_id=self.official_run_id, underlying_symbol=prediction.underlying_symbol, exchange=prediction.exchange, predicted_action=prediction.predicted_action, parent_decision=prediction.parent_decision, status=status, countable=trade, pending=pending, reason_codes=() if trade or non_trade or wait else task9.reason_codes, policy_id="task9-live-counting", policy_version="1.0", system_version="task9", provider_version="task9", evaluated_at=evaluated_at)

    def refresh(self, *, session_date, evaluated_at):
        if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None: raise ValueError("evaluated_at")
        self.rollover(session_date=session_date, evaluated_at=evaluated_at)
        if any(item["session_date"] == session_date.isoformat() for item in self.index.all_records()):
            return self._progress()
        report = self._build_report(session_date=session_date, evaluated_at=evaluated_at)
        _write(self._draft_path(session_date), report.to_dict())
        return self._progress(report)
