"""Atomic JSON repository for P8 PAPER portfolio state."""
from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path


class PaperPortfolioRepository:
    """Persist latest typed P8 portfolio envelopes using atomic replacement."""

    SCHEMA_VERSION = 1

    def __init__(self, file_path=None):
        if file_path is None:
            file_path = "data/paper_trading/paper_portfolio_state.json"
        self.file_path = Path(file_path)

    @staticmethod
    def _validate_portfolio_id(portfolio_id):
        if portfolio_id is None:
            raise ValueError("portfolio_id is required")
        portfolio_id = str(portfolio_id).strip()
        if not portfolio_id:
            raise ValueError("portfolio_id must not be empty")
        return portfolio_id

    @classmethod
    def _validate_portfolio_state(cls, portfolio_state):
        if not isinstance(portfolio_state, dict):
            raise TypeError("portfolio_state must be a dictionary")
        if "portfolio_id" not in portfolio_state:
            raise ValueError("portfolio_state must contain portfolio_id")
        normalized = deepcopy(portfolio_state)
        normalized["portfolio_id"] = cls._validate_portfolio_id(
            normalized["portfolio_id"]
        )
        return normalized

    @classmethod
    def _empty_document(cls):
        return {"version": cls.SCHEMA_VERSION, "portfolios": {}}

    @classmethod
    def _validate_document(cls, document):
        if not isinstance(document, dict):
            raise ValueError("portfolio repository must contain a JSON object")
        if document.get("version") != cls.SCHEMA_VERSION:
            raise ValueError(
                f"unsupported portfolio repository version: {document.get('version')}"
            )
        portfolios = document.get("portfolios")
        if not isinstance(portfolios, dict):
            raise ValueError("portfolio repository portfolios must be a dictionary")

        normalized = {}
        for key, state in portfolios.items():
            portfolio_id = cls._validate_portfolio_id(key)
            normalized_state = cls._validate_portfolio_state(state)
            if normalized_state["portfolio_id"] != portfolio_id:
                raise ValueError("repository key does not match portfolio_id")
            normalized[portfolio_id] = normalized_state
        return {"version": cls.SCHEMA_VERSION, "portfolios": normalized}

    def _read_document(self):
        if not self.file_path.exists():
            return self._empty_document()
        try:
            with self.file_path.open("r", encoding="utf-8") as file:
                document = json.load(file)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in portfolio repository: {exc}") from exc
        return self._validate_document(document)

    def _write_document(self, document):
        validated = self._validate_document(document)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.file_path.with_name(self.file_path.name + ".tmp")
        try:
            with temporary_path.open("w", encoding="utf-8") as file:
                json.dump(
                    validated,
                    file,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                )
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self.file_path)
        except Exception:
            try:
                if temporary_path.exists():
                    temporary_path.unlink()
            except OSError:
                pass
            raise

    def save_portfolio(self, portfolio_state):
        normalized = self._validate_portfolio_state(portfolio_state)
        document = self._read_document()
        document["portfolios"][normalized["portfolio_id"]] = deepcopy(normalized)
        self._write_document(document)
        return deepcopy(normalized)

    def save_portfolios(self, portfolio_states):
        if not isinstance(portfolio_states, (list, tuple)):
            raise TypeError("portfolio_states must be a list or tuple")
        normalized = []
        seen = set()
        for state in portfolio_states:
            item = self._validate_portfolio_state(state)
            if item["portfolio_id"] in seen:
                raise ValueError("duplicate portfolio_id in portfolio_states")
            seen.add(item["portfolio_id"])
            normalized.append(item)
        document = self._read_document()
        for item in normalized:
            document["portfolios"][item["portfolio_id"]] = deepcopy(item)
        self._write_document(document)
        return deepcopy(normalized)

    def get_portfolio(self, portfolio_id):
        portfolio_id = self._validate_portfolio_id(portfolio_id)
        state = self._read_document()["portfolios"].get(portfolio_id)
        return None if state is None else deepcopy(state)

    def get_all_portfolios(self):
        return [
            deepcopy(state)
            for state in self._read_document()["portfolios"].values()
        ]

    def exists(self, portfolio_id):
        return self.get_portfolio(portfolio_id) is not None

    def count_portfolios(self):
        return len(self.get_all_portfolios())

    def delete_portfolio(self, portfolio_id):
        portfolio_id = self._validate_portfolio_id(portfolio_id)
        document = self._read_document()
        if portfolio_id not in document["portfolios"]:
            return False
        del document["portfolios"][portfolio_id]
        self._write_document(document)
        return True
