from __future__ import annotations

from types import SimpleNamespace

from dashboard import five_market_paper_campaign_sync as sync


def test_sync_stores_only_returned_read_model(monkeypatch):
    sentinel = SimpleNamespace(read_only=True)
    calls = []

    def build(repo_root):
        calls.append(repo_root)
        return sentinel

    monkeypatch.setattr(
        sync,
        "build_five_market_paper_campaign_view_v1",
        build,
    )

    state = {}
    result = sync.synchronize_five_market_paper_campaign_projection(
        state,
        repo_root="repo",
    )

    assert result is sentinel
    assert calls == ["repo"]
    assert (
        state[sync.FIVE_MARKET_CAMPAIGN_STATE_KEY]
        is sentinel
    )
    assert sync.FIVE_MARKET_CAMPAIGN_ERROR_KEY not in state


def test_sync_failure_publishes_error_without_stale_view(monkeypatch):
    from services.reporting.five_market_paper_campaign_reader_v1 import (
        FiveMarketPaperCampaignReadError,
    )

    def build(_repo_root):
        raise FiveMarketPaperCampaignReadError("HOLD")

    monkeypatch.setattr(
        sync,
        "build_five_market_paper_campaign_view_v1",
        build,
    )

    state = {
        sync.FIVE_MARKET_CAMPAIGN_STATE_KEY: object(),
    }

    result = sync.synchronize_five_market_paper_campaign_projection(
        state,
        repo_root="repo",
    )

    assert result is None
    assert sync.FIVE_MARKET_CAMPAIGN_STATE_KEY not in state
    assert "HOLD" in state[sync.FIVE_MARKET_CAMPAIGN_ERROR_KEY]


def test_sync_module_imports_no_provider_or_execution_authority():
    source = __import__("pathlib").Path(
        "dashboard/five_market_paper_campaign_sync.py"
    ).read_text(encoding="utf-8")

    prohibited = (
        "fyers",
        "angel_client",
        "place_order",
        "submit_order",
        "new_entry",
        "paper_lifecycle_executor",
    )
    lowered = source.lower()
    assert all(item not in lowered for item in prohibited)
