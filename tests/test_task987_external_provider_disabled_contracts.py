import inspect
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from services.analysis.shared_external_market_context import (
    build_shared_external_market_context,
)
from services.certification.task9_disabled_external_readers import (
    Task9DisabledExternalReadersV1,
)
from services.certification.task9_external_provider_snapshot_builder import (
    build_task9_external_provider_snapshot,
)
from services.certification.task9_external_provider_snapshot_store import (
    Task9ExternalProviderSnapshotStore,
)
from services.contracts.task9_external_provider_state_v1 import (
    Task9ExternalFailureSemantic,
    Task9ExternalProviderDomain,
    Task9ExternalProviderFreshness,
    Task9ExternalProviderStatus,
)


NOW = datetime(
    2026,
    8,
    18,
    10,
    0,
    tzinfo=ZoneInfo("Asia/Kolkata"),
)


def _snapshot():
    return build_task9_external_provider_snapshot(
        snapshot_id="task987-test",
        observed_at=NOW,
    )


def test_all_five_external_domains_are_explicitly_not_selected():
    snapshot = _snapshot()

    assert len(snapshot.states) == 5

    assert {
        state.domain
        for state in snapshot.states
    } == set(Task9ExternalProviderDomain)

    for state in snapshot.states:
        assert (
            state.status
            is Task9ExternalProviderStatus.PROVIDER_NOT_SELECTED
        )
        assert state.availability is False
        assert state.provider_selected is False
        assert state.network_calls_allowed is False
        assert (
            state.freshness
            is Task9ExternalProviderFreshness.NOT_APPLICABLE
        )
        assert (
            state.failure_semantic
            is Task9ExternalFailureSemantic.OPTIONAL_UNAVAILABLE
        )
        assert state.provider_name is None
        assert (
            state.reason_code
            == "TASK9_EXTERNAL_PROVIDER_NOT_SELECTED"
        )


def test_disabled_readers_return_unavailable_shapes_without_provider_work():
    readers = Task9DisabledExternalReadersV1(
        _snapshot()
    )

    breadth_state, breadth = (
        readers.read_market_breadth()
    )
    fii_state, institutional = (
        readers.read_institutional_flow()
    )
    event_state, events = (
        readers.read_scheduled_events()
    )
    global_state, global_markets = (
        readers.read_global_markets()
    )
    news_state, news = (
        readers.read_structured_news()
    )

    assert breadth is None
    assert institutional is None
    assert events == ()
    assert global_markets == ()
    assert news == ()

    assert {
        breadth_state.domain,
        fii_state.domain,
        event_state.domain,
        global_state.domain,
        news_state.domain,
    } == set(Task9ExternalProviderDomain)


def test_disabled_readers_have_no_transport_or_provider_arguments():
    methods = (
        Task9DisabledExternalReadersV1.read_market_breadth,
        Task9DisabledExternalReadersV1.read_institutional_flow,
        Task9DisabledExternalReadersV1.read_scheduled_events,
        Task9DisabledExternalReadersV1.read_global_markets,
        Task9DisabledExternalReadersV1.read_structured_news,
    )

    for method in methods:
        assert tuple(
            inspect.signature(
                method
            ).parameters
        ) == ("self",)


def test_snapshot_store_preserves_provider_disabled_provenance(
    tmp_path,
):
    snapshot = _snapshot()

    store = Task9ExternalProviderSnapshotStore(
        tmp_path
    )

    store.save(snapshot)

    value = store.load_dict()

    assert value["snapshot_id"] == (
        "task987-test"
    )

    assert (
        value["execution_mode"]
        == "PAPER"
    )

    assert (
        value["broker_order_submission"]
        is False
    )

    assert (
        value["live_execution_eligible"]
        is False
    )

    states = {
        item["domain"]: item
        for item in value["states"]
    }

    assert set(states) == {
        item.value
        for item
        in Task9ExternalProviderDomain
    }

    for state in states.values():
        assert (
            state["status"]
            == "PROVIDER_NOT_SELECTED"
        )
        assert (
            state["network_calls_allowed"]
            is False
        )
        assert state["provenance"]


def test_provider_free_external_context_build_remains_zero_call_authority():
    result = (
        build_shared_external_market_context(
            cycle_id="task987-zero-provider",
            evaluated_at=NOW,
            observations=(),
            institutional_snapshot=None,
            scheduled_events=(),
        )
    )

    assert result.build_count == 1
    assert (
        result.global_provider_call_count
        == 0
    )
    assert (
        result.institutional_provider_call_count
        == 0
    )
    assert (
        result.event_provider_call_count
        == 0
    )
    assert (
        result.breadth_provider_call_count
        == 0
    )

    for market in (
        result.nifty,
        result.sensex,
    ):
        # Missing optional external evidence may never become
        # fabricated positive/negative directional evidence.
        if market.context_status == "UNAVAILABLE":
            assert (
                market.aggregate_direction
                == "UNAVAILABLE"
            )
            assert (
                market.aggregate_strength
                == 0
            )


def test_current_snapshot_contains_no_selected_provider_name():
    payload = json.dumps(
        _snapshot().to_dict(),
        sort_keys=True,
    )

    for forbidden in (
        "YAHOO",
        "YFINANCE",
        "OPENAI",
        "NEWSAPI",
        "ALPHA_VANTAGE",
    ):
        assert forbidden not in payload.upper()
