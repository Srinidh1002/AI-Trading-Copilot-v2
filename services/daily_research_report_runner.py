"""Read-only orchestration for daily research report generation and archiving."""

from copy import deepcopy
from datetime import date, datetime
from zoneinfo import ZoneInfo

from services.daily_research_report import DailyResearchReport
from services.market_cycle_journal import MarketCycleJournal
from services.paper_trade_repository import PaperTradeRepository
from services.research_report_archive import ResearchReportArchive


class DailyResearchReportRunner:
    """Load a session, build research, and persist it without trading authority."""

    INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")

    def __init__(
        self,
        *,
        market_cycle_journal=None,
        paper_trade_repository=None,
        daily_research_report=None,
        research_report_archive=None,
    ):
        self.market_cycle_journal = market_cycle_journal or MarketCycleJournal()
        self.paper_trade_repository = paper_trade_repository or PaperTradeRepository()
        self.daily_research_report = daily_research_report or DailyResearchReport()
        self.research_report_archive = research_report_archive or ResearchReportArchive()

    @classmethod
    def _normalize_session_date(cls, value):
        if value is None:
            return datetime.now(cls.INDIA_TIMEZONE).date().isoformat()
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                raise ValueError("session_date must use YYYY-MM-DD format.")
            try:
                return date.fromisoformat(normalized).isoformat()
            except ValueError as exc:
                raise ValueError("session_date must use YYYY-MM-DD format.") from exc
        raise ValueError("session_date must be a date, datetime, YYYY-MM-DD string, or None.")

    @classmethod
    def _entry_matches_session(cls, entry, session_date):
        if not isinstance(entry, dict):
            return False
        value = entry.get("session_date")
        if value is None:
            return False
        try:
            return cls._normalize_session_date(value) == session_date
        except ValueError:
            return False

    @staticmethod
    def _error_text(error):
        return "{}: {}".format(type(error).__name__, str(error))

    def _failed_result(self, *, session_date, error, journal_entries_loaded=None, paper_trades_loaded=None, report=None, archive_result=None):
        return {
            "status": "FAILED",
            "read_only": True,
            "research_only": True,
            "session_date": session_date,
            "journal_entries_loaded": journal_entries_loaded,
            "paper_trades_loaded": paper_trades_loaded,
            "report_status": report.get("status") if isinstance(report, dict) else None,
            "archive_status": archive_result.get("status") if isinstance(archive_result, dict) else None,
            "archive_success": archive_result.get("success") if isinstance(archive_result, dict) else False,
            "archive_path": archive_result.get("path") if isinstance(archive_result, dict) else None,
            "report": deepcopy(report) if isinstance(report, dict) else None,
            "archive_result": deepcopy(archive_result) if isinstance(archive_result, dict) else None,
            "error": self._error_text(error),
        }

    def run(self, *, session_date=None):
        """Run the complete read-only daily research orchestration."""
        try:
            normalized_date = self._normalize_session_date(session_date)
        except Exception as error:
            return self._failed_result(session_date=None, error=error)

        try:
            raw_entries = self.market_cycle_journal.read_entries(normalized_date)
            if not isinstance(raw_entries, (list, tuple)):
                raise ValueError("MarketCycleJournal.read_entries must return a list or tuple.")
            entries = [deepcopy(entry) for entry in raw_entries if self._entry_matches_session(entry, normalized_date)]
        except Exception as error:
            return self._failed_result(session_date=normalized_date, error=error)

        try:
            raw_trades = self.paper_trade_repository.get_all_trades()
            if not isinstance(raw_trades, (list, tuple)):
                raise ValueError("PaperTradeRepository.get_all_trades must return a list or tuple.")
            trades = deepcopy(list(raw_trades))
        except Exception as error:
            return self._failed_result(session_date=normalized_date, error=error, journal_entries_loaded=len(entries))

        try:
            report = self.daily_research_report.build_report(entries, trades=trades, session_date=normalized_date)
            if not isinstance(report, dict):
                raise ValueError("DailyResearchReport.build_report must return a dictionary.")
            if report.get("read_only") is not True or report.get("research_only") is not True:
                raise ValueError("Daily research report must remain read_only and research_only.")
            if report.get("session_date") != normalized_date:
                raise ValueError("Daily research report session_date must match the requested session.")
            if report.get("status") not in ("COMPLETED", "COMPLETED_WITH_ERRORS"):
                raise ValueError("Daily research report returned an unsupported status.")
        except Exception as error:
            return self._failed_result(session_date=normalized_date, error=error, journal_entries_loaded=len(entries), paper_trades_loaded=len(trades))

        try:
            archive_result = self.research_report_archive.save_report(deepcopy(report))
            if not isinstance(archive_result, dict) or archive_result.get("success") is not True:
                raise RuntimeError("Research report archive did not confirm a successful save.")
        except Exception as error:
            return self._failed_result(session_date=normalized_date, error=error, journal_entries_loaded=len(entries), paper_trades_loaded=len(trades), report=report)

        return {
            "status": report["status"],
            "read_only": True,
            "research_only": True,
            "session_date": normalized_date,
            "journal_entries_loaded": len(entries),
            "paper_trades_loaded": len(trades),
            "report_status": report.get("status"),
            "archive_status": archive_result.get("status"),
            "archive_success": archive_result.get("success"),
            "archive_path": archive_result.get("path"),
            "report": deepcopy(report),
            "archive_result": deepcopy(archive_result),
        }
