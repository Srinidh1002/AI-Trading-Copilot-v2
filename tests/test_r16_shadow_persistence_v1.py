from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from services.analysis.pre_entry_action_resolver import (
    resolve_pre_entry_market_action,
)
from services.certification.task9_prediction_lifecycle_context_store import (
    Task9PredictionLifecycleContextStore,
)
from services.paper_orchestration.certified_live_provider_readers import (
    CertifiedLiveProviderReaders,
)
from services.paper_orchestration.paper_orchestration_journal import (
    PaperOrchestrationJournal,
)
from services.paper_orchestration.prediction_ledger import (
    PredictionLedger,
)
from services.paper_orchestration.r16_two_market_shadow_source_v1 import (
    R16TwoMarketShadowSourceV1,
)
from services.paper_orchestration.two_market_parent_cycle_journal_adapter import (
    TwoMarketParentCycleJournalAdapter,
)
from test_certified_two_market_parent_runtime import candidate_for
from test_two_market_runtime_readiness import (
    OfflineAnalysisPipeline,
    OfflineOptionPipeline,
)


NOW = datetime(2026, 8, 4, 5, 0, 10, tzinfo=UTC)
MARKET_TS = datetime(2026, 8, 4, 5, 0, 0, tzinfo=UTC)


class RetainedActionReader:
    def __init__(self):
        self.evaluations = {}

    def __call__(
        self,
        cycle,
        data,
        analysis,
        captured,
        shared_context,
        *,
        parent_cycle_id,
    ):
        score = 85.0 if cycle.underlying_symbol == "NIFTY" else 65.0
        candidate = candidate_for(cycle, data, score=score)
        action = resolve_pre_entry_market_action(
            candidate=candidate,
            cycle_id=parent_cycle_id,
            observation_id=cycle.observation_id,
            evaluated_at=cycle.received_at,
        )
        self.evaluations[(parent_cycle_id, cycle.underlying_symbol)] = (
            SimpleNamespace(pre_entry_action=action)
        )
        return candidate

    def get_evaluation(self, *, parent_cycle_id, market):
        return self.evaluations.get(
            (str(parent_cycle_id), str(market).upper())
        )


def _source(reader):
    def quote(exchange, token, symbol):
        offset = 0 if symbol == "NIFTY" else 1
        market = MARKET_TS + timedelta(seconds=offset)
        return {
            "spot_price": 22000.0 if symbol == "NIFTY" else 72000.0,
            "market_timestamp": market,
            "received_at": market + timedelta(seconds=1),
            "timestamp_source": "TEST",
        }

    readers = CertifiedLiveProviderReaders(
        quote_reader=quote,
        analysis_pipeline=OfflineAnalysisPipeline(),
        option_decision_pipeline=OfflineOptionPipeline(),
        available_capital=100_000.0,
        candidate_reader=reader,
    )
    return R16TwoMarketShadowSourceV1(
        readers=readers,
        clock=lambda: NOW,
    )


def _stores(tmp_path):
    root = tmp_path / "shadow"
    journal = PaperOrchestrationJournal(root / "parent_journal.json")
    adapter = TwoMarketParentCycleJournalAdapter(
        journal=journal,
        clock=lambda: NOW,
    )
    predictions = PredictionLedger(root / "prediction_ledger.json")
    contexts = Task9PredictionLifecycleContextStore(
        root / "prediction_lifecycle_contexts.json"
    )
    return root, journal, adapter, predictions, contexts


def test_shadow_cycle_persists_exact_parent_and_prediction_evidence(tmp_path):
    root, journal, adapter, predictions, contexts = _stores(tmp_path)
    reader = RetainedActionReader()

    result = _source(reader).run_shadow_cycle(
        parent_journal_adapter=adapter,
        prediction_ledger=predictions,
        prediction_lifecycle_context_store=contexts,
    )

    assert result.decision.decision == "SELECTED"
    assert result.decision.selected_market == ("NIFTY", "NSE")
    assert journal.count() == 1
    assert predictions.count() == 2

    rows = predictions.records_for_parent(result.parent.parent_cycle_id)
    assert tuple(
        (row["underlying_symbol"], row["exchange"])
        for row in rows
    ) == (("NIFTY", "NSE"), ("SENSEX", "BSE"))
    assert tuple(row["predicted_action"] for row in rows) == (
        "CALL",
        "CALL",
    )
    assert sum(row["parent_selected"] is True for row in rows) == 1

    for row in rows:
        context = contexts.recover(row["prediction_id"])
        assert context is not None
        assert context.prediction_id == row["prediction_id"]

    assert not (tmp_path / "runtime").exists()
    assert not (root / "runtime").exists()


def test_identical_shadow_cycle_is_idempotent_in_durable_ledgers(tmp_path):
    _root, journal, adapter, predictions, contexts = _stores(tmp_path)

    first = _source(RetainedActionReader()).run_shadow_cycle(
        parent_journal_adapter=adapter,
        prediction_ledger=predictions,
        prediction_lifecycle_context_store=contexts,
    )
    second = _source(RetainedActionReader()).run_shadow_cycle(
        parent_journal_adapter=adapter,
        prediction_ledger=predictions,
        prediction_lifecycle_context_store=contexts,
    )

    assert first.parent.parent_cycle_id == second.parent.parent_cycle_id
    assert first.decision.semantic_hash == second.decision.semantic_hash
    assert journal.count() == 1
    assert predictions.count() == 2
