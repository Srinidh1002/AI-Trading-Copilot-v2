from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.certification.five_market_certification_report_writer_v1 import (
    write_five_market_certification_report_v1,
)
from services.contracts.five_market_certification_report_v1 import (
    FiveMarketCertificationMarketReportV1,
    FiveMarketCertificationReportV1,
)


NOW = datetime(2026, 10, 5, 11, 30, tzinfo=timezone.utc)


def _market(name):
    return FiveMarketCertificationMarketReportV1(
        market=name,
        strategy_version="v1",
        certification_epoch="e1",
        target_trade_count=100,
        accepted_trade_count=0,
        t1_first_wins=0,
        sl_first_losses=0,
        operational_completed_trades=0,
        operational_net_pnl=0.0,
        noncountable_completed_trades=0,
        ambiguous_completed_trades=0,
        distinct_trading_days=0,
        distinct_regimes=0,
        distinct_session_phases=0,
        max_countable_per_day=0,
        diversity_pass=False,
        accuracy_threshold_pass=False,
        state_counter_integrity=True,
        ledger_reconciliation_pass=True,
        final_status="IN_PROGRESS",
    )


def _report():
    return FiveMarketCertificationReportV1(
        generated_at=NOW,
        release_commit="99cf",
        markets=tuple(
            _market(name)
            for name in (
                "NIFTY",
                "SENSEX",
                "CRUDEOILM",
                "GOLDM",
                "NATGASMINI",
            )
        ),
    )


def test_writer_creates_immutable_json_and_hash(tmp_path):
    path = tmp_path / "report.json"
    written, digest = write_five_market_certification_report_v1(
        _report(),
        path,
    )
    assert written == path
    assert len(digest) == 64
    assert path.read_text(encoding="utf-8").endswith("\n")

    with pytest.raises(FileExistsError):
        write_five_market_certification_report_v1(
            _report(),
            path,
        )
