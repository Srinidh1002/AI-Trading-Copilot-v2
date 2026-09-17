from __future__ import annotations

from datetime import date, datetime, timezone
from inspect import getsource
from pathlib import Path
from types import SimpleNamespace

from services.certification import (
    task9_certification_publication as publication_module,
)
from services.certification.task9_startup_campaign_transition import (
    _rollover_previous_official_run_publication,
    prepare_task9_startup_campaign_authority,
)
from services.certification.task9_prediction_lifecycle_outcome_store import (
    Task9PredictionLifecycleOutcomeStore,
)
from services.certification.task9_prediction_lifecycle_reconciliation_store import (
    Task9PredictionLifecycleReconciliationStore,
)
from services.certification.task9_prediction_paper_trade_binding_store import (
    Task9PredictionPaperTradeBindingStore,
)
from services.paper_orchestration.prediction_ledger import (
    PredictionLedger,
)
from services.paper_trading.paper_trade_persistence_service import (
    PaperTradePersistenceService,
)


def test_previous_run_publication_rollover_uses_exact_manifest_and_target_date(
    tmp_path,
    monkeypatch,
):
    evaluated_at = datetime(
        2026,
        8,
        22,
        3,
        30,
        tzinfo=timezone.utc,
    )

    previous_start = datetime(
        2026,
        8,
        21,
        3,
        45,
        tzinfo=timezone.utc,
    )

    previous_manifest = SimpleNamespace(
        official_run_id=(
            "synthetic-previous-official-run"
        ),
        official_start_at=previous_start,
        run_classification=(
            "OFFICIAL_CERTIFICATION"
        ),
    )

    captured = {}

    class FakePublicationAuthority:
        def __init__(
            self,
            **kwargs,
        ):
            captured[
                "init"
            ] = kwargs

        def rollover(
            self,
            *,
            session_date,
            evaluated_at,
        ):
            captured[
                "rollover"
            ] = (
                session_date,
                evaluated_at,
            )

            return (
                date(
                    2026,
                    8,
                    21,
                ),
            )

    monkeypatch.setattr(
        publication_module,
        "Task9CertificationPublicationAuthority",
        FakePublicationAuthority,
    )

    result = (
        _rollover_previous_official_run_publication(
            root=tmp_path,
            previous_run_manifest=(
                previous_manifest
            ),
            target_market_date=date(
                2026,
                8,
                22,
            ),
            evaluated_at=evaluated_at,
            starting_capital=10000.0,
        )
    )

    assert result == (
        date(
            2026,
            8,
            21,
        ),
    )

    init = captured[
        "init"
    ]

    assert (
        init[
            "official_run_id"
        ]
        == previous_manifest.official_run_id
    )

    assert (
        init[
            "official_start_at"
        ]
        == previous_start
    )

    assert (
        Path(
            init[
                "root"
            ]
        )
        == tmp_path
    )

    assert (
        init[
            "starting_capital"
        ]
        == 10000.0
    )

    assert (
        init[
            "run_classification"
        ]
        == "OFFICIAL_CERTIFICATION"
    )

    assert isinstance(
        init[
            "prediction_ledger"
        ],
        PredictionLedger,
    )

    assert isinstance(
        init[
            "binding_store"
        ],
        Task9PredictionPaperTradeBindingStore,
    )

    assert isinstance(
        init[
            "outcome_store"
        ],
        Task9PredictionLifecycleOutcomeStore,
    )

    assert isinstance(
        init[
            "reconciliation_store"
        ],
        Task9PredictionLifecycleReconciliationStore,
    )

    assert isinstance(
        init[
            "trade_persistence_service"
        ],
        PaperTradePersistenceService,
    )

    assert captured[
        "rollover"
    ] == (
        date(
            2026,
            8,
            22,
        ),
        evaluated_at,
    )


def test_startup_rolls_previous_publication_before_campaign_pointer_advance():
    source = getsource(
        prepare_task9_startup_campaign_authority
    )

    previous_manifest_read = (
        source.index(
            "previous_run_manifest_store.get"
        )
    )

    publication_rollover = (
        source.index(
            "_rollover_previous_official_run_publication("
        )
    )

    report_index_open = (
        source.index(
            "previous_report_index"
        )
    )

    campaign_rollover = (
        source.index(
            "apply_task9_campaign_rollover("
        )
    )

    assert (
        previous_manifest_read
        < publication_rollover
        < report_index_open
        < campaign_rollover
    )

    assert (
        "pointer.active_official_run_id"
        in source
    )

    assert (
        "target_market_date=(\n"
        "            runtime_config.market_date"
        in source
    )

    assert (
        "evaluated_at=observed_at"
        in source
    )

    assert (
        "TASK9_STARTUP_PREVIOUS_RUN_MANIFEST_MISSING"
        in source
    )


def test_previous_publication_rollover_has_no_run_discovery_or_date_inference():
    source = getsource(
        _rollover_previous_official_run_publication
    )

    forbidden = (
        "rglob(",
        "glob(",
        "iterdir(",
        "max(",
        "latest",
        "today(",
        "date.today",
    )

    for token in forbidden:
        assert token not in source

    assert (
        "previous_run_manifest.official_run_id"
        in source
    )

    assert (
        "session_date=target_market_date"
        in source
    )

    assert (
        "evaluated_at=evaluated_at"
        in source
    )
