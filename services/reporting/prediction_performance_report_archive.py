"""Atomic persistence and deterministic export for prediction reports."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from services.contracts.prediction_performance_report_v1 import (
    PredictionPerformanceReportV1,
)


class PredictionPerformanceReportArchive:
    """Persist immutable prediction reports without execution authority."""

    def __init__(
        self,
        base_directory: str | Path = (
            "data/paper_trading/certified_runtime/"
            "prediction_reports"
        ),
    ) -> None:
        self.base_directory = Path(
            base_directory
        ).expanduser().resolve()

    def _path_for_report(
        self,
        report_id: str,
        suffix: str,
    ) -> Path:
        if (
            type(report_id) is not str
            or not report_id.strip()
        ):
            raise ValueError(
                "report_id must be non-empty"
            )
        cleaned = report_id.strip()
        if any(
            token in cleaned
            for token in (
                "/",
                "\\",
                "..",
                ":",
            )
        ):
            raise ValueError(
                "report_id contains unsafe path characters"
            )

        target = (
            self.base_directory
            / f"{cleaned}.{suffix}"
        ).resolve()
        if target.parent != self.base_directory:
            raise ValueError(
                "report path must remain inside archive"
            )
        return target

    @staticmethod
    def render_text(
        report: PredictionPerformanceReportV1,
    ) -> str:
        if type(report) is not PredictionPerformanceReportV1:
            raise TypeError(
                "report must be exact "
                "PredictionPerformanceReportV1"
            )

        def line(
            label: str,
            value: object,
        ) -> str:
            return f"{label}: {value}"

        rows = [
            "Prediction Performance Report",
            line("Report ID", report.report_id),
            line(
                "Generated At",
                report.generated_at.isoformat(),
            ),
            line(
                "Period Start",
                report.period_started_at.isoformat()
                if report.period_started_at
                else "NONE",
            ),
            line(
                "Period End",
                report.period_ended_at.isoformat()
                if report.period_ended_at
                else "NONE",
            ),
        ]

        for label, metrics in (
            ("Overall", report.overall),
            ("NIFTY", report.nifty),
            ("SENSEX", report.sensex),
        ):
            rows.extend(
                (
                    "",
                    label,
                    line(
                        "Predictions",
                        metrics.prediction_count,
                    ),
                    line(
                        "Evaluated",
                        metrics.evaluated_count,
                    ),
                    line(
                        "Pending",
                        metrics.pending_count,
                    ),
                    line(
                        "Unevaluable",
                        metrics.unevaluable_count,
                    ),
                    line(
                        "Directional Accuracy Percent",
                        metrics.directional_accuracy_percent
                        if metrics.directional_accuracy_percent
                        is not None
                        else "NONE",
                    ),
                    line(
                        "Wait Quality Percent",
                        metrics.wait_quality_percent
                        if metrics.wait_quality_percent
                        is not None
                        else "NONE",
                    ),
                    line(
                        "Actions",
                        json.dumps(
                            dict(
                                metrics.action_distribution
                            ),
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    ),
                    line(
                        "Outcomes",
                        json.dumps(
                            dict(
                                metrics.outcome_distribution
                            ),
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    ),
                )
            )

        rows.extend(
            (
                "",
                line(
                    "Execution Mode",
                    report.execution_mode,
                ),
                line(
                    "Live Execution Eligible",
                    report.live_execution_eligible,
                ),
                line(
                    "Broker Order Submission",
                    report.broker_order_submission,
                ),
                line(
                    "Read Only",
                    report.read_only,
                ),
            )
        )
        return "\n".join(rows) + "\n"

    @staticmethod
    def _atomic_write(
        target: Path,
        content: str,
    ) -> None:
        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
                newline="\n",
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(
                temporary_path,
                target,
            )
        except Exception:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(
                        missing_ok=True
                    )
                except OSError:
                    pass
            raise

    def save(
        self,
        report: PredictionPerformanceReportV1,
    ) -> dict[str, object]:
        if type(report) is not PredictionPerformanceReportV1:
            raise TypeError(
                "report must be exact "
                "PredictionPerformanceReportV1"
            )

        json_path = self._path_for_report(
            report.report_id,
            "json",
        )
        text_path = self._path_for_report(
            report.report_id,
            "txt",
        )

        json_content = report.to_json() + "\n"
        text_content = self.render_text(report)

        prior_json = (
            json_path.read_bytes()
            if json_path.is_file()
            else None
        )

        self._atomic_write(
            json_path,
            json_content,
        )
        try:
            self._atomic_write(
                text_path,
                text_content,
            )
        except Exception:
            if prior_json is None:
                json_path.unlink(missing_ok=True)
            else:
                self._atomic_write(
                    json_path,
                    prior_json.decode("utf-8"),
                )
            raise

        return {
            "status": "SAVED",
            "report_id": report.report_id,
            "json_path": str(json_path),
            "text_path": str(text_path),
            "execution_mode": "PAPER",
            "live_execution_eligible": False,
            "broker_order_submission": False,
            "read_only": True,
        }

    def load_json(
        self,
        report_id: str,
    ) -> dict[str, object] | None:
        path = self._path_for_report(
            report_id,
            "json",
        )
        if not path.is_file():
            return None
        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as handle:
                value = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "invalid JSON in prediction report archive"
            ) from exc
        if type(value) is not dict:
            raise ValueError(
                "prediction report archive must contain an object"
            )
        return dict(value)
