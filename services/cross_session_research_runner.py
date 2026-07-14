"""
Cross-Session Research Runner Service.

Coordinates:

ResearchReportArchive
    -> load archived daily research reports

CrossSessionResearchIntelligence
    -> analyse research observations across sessions

IMPORTANT:
- READ ONLY.
- RESEARCH ONLY.
- NO BROKER INTEGRATION.
- NO MARKET DATA REQUEST.
- NO PAPER TRADE MUTATION.
- NO REAL ORDER PLACEMENT.
- NO STRATEGY TUNING.
"""

from copy import deepcopy

from services.cross_session_research_intelligence import (
    CrossSessionResearchIntelligence,
)
from services.research_report_archive import (
    ResearchReportArchive,
)


class CrossSessionResearchRunner:
    """
    Read-only cross-session research coordinator.
    """

    def __init__(
        self,
        *,
        archive=None,
        intelligence=None,
    ):
        self.archive = (
            archive
            if archive is not None
            else ResearchReportArchive()
        )

        self.intelligence = (
            intelligence
            if intelligence is not None
            else CrossSessionResearchIntelligence()
        )

    def run(
        self,
        *,
        start_date=None,
        end_date=None,
    ):
        """
        Load archived reports and run cross-session research.
        """

        archive_result = self.archive.load_reports(
            start_date=start_date,
            end_date=end_date,
        )

        if not isinstance(
            archive_result,
            dict,
        ):
            archive_result = {}

        reports = archive_result.get(
            "reports",
            [],
        )

        if not isinstance(
            reports,
            list,
        ):
            reports = []

        archive_errors = archive_result.get(
            "errors",
            [],
        )

        if not isinstance(
            archive_errors,
            list,
        ):
            archive_errors = []

        intelligence_result = self.intelligence.analyze(
            deepcopy(
                reports
            )
        )

        if not isinstance(
            intelligence_result,
            dict,
        ):
            intelligence_result = {}

        component_errors = []

        for error in archive_errors:
            component_errors.append(
                {
                    "component": (
                        "research_report_archive"
                    ),
                    "error": deepcopy(
                        error
                    ),
                }
            )

        archive_status = archive_result.get(
            "status"
        )

        intelligence_status = (
            intelligence_result.get(
                "status"
            )
        )

        status = self._resolve_status(
            archive_status=archive_status,
            intelligence_status=(
                intelligence_status
            ),
            component_errors=(
                component_errors
            ),
        )

        return {
            "status": status,
            "read_only": True,
            "research_only": True,
            "start_date": (
                archive_result.get(
                    "start_date",
                    start_date,
                )
            ),
            "end_date": (
                archive_result.get(
                    "end_date",
                    end_date,
                )
            ),
            "archive_status": archive_status,
            "reports_loaded": len(
                reports
            ),
            "archive_errors": deepcopy(
                archive_errors
            ),
            "component_errors": (
                component_errors
            ),
            "intelligence": deepcopy(
                intelligence_result
            ),
        }

    def _resolve_status(
        self,
        *,
        archive_status,
        intelligence_status,
        component_errors,
    ):
        """
        Resolve coordinator status without granting authority.
        """

        failed_statuses = {
            "ERROR",
            "FAILED",
        }

        if (
            archive_status
            in failed_statuses
            or intelligence_status
            in failed_statuses
        ):
            return "FAILED"

        if component_errors:
            return "COMPLETED_WITH_ERRORS"

        if not intelligence_status:
            return "COMPLETED_WITH_ERRORS"

        return "COMPLETED"