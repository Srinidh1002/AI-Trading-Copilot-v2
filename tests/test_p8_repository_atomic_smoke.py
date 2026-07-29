from __future__ import annotations

import json

import pytest

from services.paper_portfolio_repository import PaperPortfolioRepository


def test_repository_missing_file_is_empty(tmp_path):
    repository = PaperPortfolioRepository(tmp_path / "state.json")
    assert repository.get_all_portfolios() == []
    assert repository.count_portfolios() == 0


def test_repository_save_get_delete(tmp_path):
    repository = PaperPortfolioRepository(tmp_path / "state.json")
    repository.save_portfolio({"portfolio_id": "p1", "status": "ACTIVE"})
    assert repository.get_portfolio("p1")["status"] == "ACTIVE"
    assert repository.delete_portfolio("p1") is True
    assert repository.get_portfolio("p1") is None


def test_repository_fails_closed_on_invalid_json(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{", encoding="utf-8")
    repository = PaperPortfolioRepository(path)
    with pytest.raises(ValueError):
        repository.get_all_portfolios()


def test_repository_rejects_duplicate_batch_ids(tmp_path):
    repository = PaperPortfolioRepository(tmp_path / "state.json")
    with pytest.raises(ValueError):
        repository.save_portfolios(
            [
                {"portfolio_id": "p1"},
                {"portfolio_id": "p1"},
            ]
        )
