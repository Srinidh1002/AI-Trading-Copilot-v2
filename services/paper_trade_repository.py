"""
Persistent repository for paper-trade state.

The repository stores the latest state of paper trades
in a JSON file so simulated positions can survive
application or computer restarts.

Design principles:
- Paper trading only.
- No broker integration.
- No real order placement.
- Atomic file replacement.
- Defensive deep copies.
- Fail-closed validation.
- Duplicate trade ID protection.
- OPEN and CLOSED trades can both be persisted.
"""

import json
import os
from copy import deepcopy
from pathlib import Path


class PaperTradeRepository:
    """
    Persist and recover paper-trade state snapshots.

    Storage format
    --------------
    {
        "version": 1,
        "trades": {
            "trade-id-1": {...},
            "trade-id-2": {...}
        }
    }

    The repository stores dictionaries rather than
    constructing PaperTrade objects directly. Object
    reconstruction belongs to the paper-trading engine.
    """

    SCHEMA_VERSION = 1

    def __init__(
        self,
        file_path=None,
    ):
        if file_path is None:
            file_path = (
                "data/paper_trading/"
                "paper_trade_state.json"
            )

        self.file_path = Path(
            file_path
        )

    # ---------------------------------
    # VALIDATION
    # ---------------------------------

    @staticmethod
    def _validate_trade_id(
        trade_id,
    ):
        """
        Validate and normalize a trade ID.
        """

        if trade_id is None:
            raise ValueError(
                "trade_id is required."
            )

        trade_id = str(
            trade_id
        ).strip()

        if not trade_id:
            raise ValueError(
                "trade_id must not be empty."
            )

        return trade_id

    @classmethod
    def _validate_trade_state(
        cls,
        trade_state,
    ):
        """
        Validate one paper-trade state dictionary.
        """

        if not isinstance(
            trade_state,
            dict,
        ):
            raise TypeError(
                "trade_state must be a dictionary."
            )

        if "trade_id" not in trade_state:
            raise ValueError(
                "trade_state must contain trade_id."
            )

        trade_id = (
            cls._validate_trade_id(
                trade_state[
                    "trade_id"
                ]
            )
        )

        normalized = deepcopy(
            trade_state
        )

        normalized[
            "trade_id"
        ] = trade_id

        return normalized

    @classmethod
    def _validate_document(
        cls,
        document,
    ):
        """
        Validate the complete repository document.
        """

        if not isinstance(
            document,
            dict,
        ):
            raise ValueError(
                "Paper trade repository must "
                "contain a JSON object."
            )

        version = document.get(
            "version"
        )

        if version != cls.SCHEMA_VERSION:
            raise ValueError(
                "Unsupported paper trade repository "
                f"version: {version}"
            )

        trades = document.get(
            "trades"
        )

        if not isinstance(
            trades,
            dict,
        ):
            raise ValueError(
                "Paper trade repository trades "
                "must be a dictionary."
            )

        normalized_trades = {}

        for key, trade_state in (
            trades.items()
        ):
            resolved_key = (
                cls._validate_trade_id(
                    key
                )
            )

            normalized_state = (
                cls._validate_trade_state(
                    trade_state
                )
            )

            if (
                normalized_state[
                    "trade_id"
                ]
                != resolved_key
            ):
                raise ValueError(
                    "Repository trade ID does not "
                    "match trade_state trade_id."
                )

            normalized_trades[
                resolved_key
            ] = normalized_state

        return {
            "version": (
                cls.SCHEMA_VERSION
            ),
            "trades": (
                normalized_trades
            ),
        }

    # ---------------------------------
    # DOCUMENT HELPERS
    # ---------------------------------

    @classmethod
    def _empty_document(
        cls,
    ):
        """
        Build an empty repository document.
        """

        return {
            "version": (
                cls.SCHEMA_VERSION
            ),
            "trades": {},
        }

    def _read_document(
        self,
    ):
        """
        Read and validate the repository document.

        Missing files are treated as an empty repository.

        Invalid JSON or invalid repository structure
        fails closed with ValueError.
        """

        if not self.file_path.exists():
            return self._empty_document()

        try:
            with self.file_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                document = json.load(
                    file
                )

        except json.JSONDecodeError as exc:
            raise ValueError(
                "Invalid JSON in paper trade "
                f"repository: {exc}"
            ) from exc

        except OSError:
            raise

        return self._validate_document(
            document
        )

    def _write_document(
        self,
        document,
    ):
        """
        Atomically write the repository document.

        Data is first written to a temporary file and
        then moved over the destination using os.replace().
        """

        validated = (
            self._validate_document(
                document
            )
        )

        self.file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = (
            self.file_path.with_name(
                self.file_path.name
                + ".tmp"
            )
        )

        try:
            with temporary_path.open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    validated,
                    file,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )

                file.flush()

                os.fsync(
                    file.fileno()
                )

            os.replace(
                temporary_path,
                self.file_path,
            )

        except Exception:
            try:
                if temporary_path.exists():
                    temporary_path.unlink()
            except OSError:
                pass

            raise

    # ---------------------------------
    # SAVE
    # ---------------------------------

    def save_trade(
        self,
        trade_state,
    ):
        """
        Save or update one paper-trade state.

        Existing trade IDs are updated with the latest
        complete state snapshot.

        Returns an independent copy of the saved state.
        """

        normalized_state = (
            self._validate_trade_state(
                trade_state
            )
        )

        trade_id = (
            normalized_state[
                "trade_id"
            ]
        )

        document = (
            self._read_document()
        )

        document[
            "trades"
        ][
            trade_id
        ] = deepcopy(
            normalized_state
        )

        self._write_document(
            document
        )

        return deepcopy(
            normalized_state
        )

    def save_trades(
        self,
        trade_states,
    ):
        """
        Save multiple paper-trade states atomically.

        All states are validated before any file write
        occurs.
        """

        if not isinstance(
            trade_states,
            (
                list,
                tuple,
            ),
        ):
            raise TypeError(
                "trade_states must be a list "
                "or tuple."
            )

        normalized_states = []

        seen_trade_ids = set()

        for trade_state in trade_states:
            normalized_state = (
                self._validate_trade_state(
                    trade_state
                )
            )

            trade_id = (
                normalized_state[
                    "trade_id"
                ]
            )

            if trade_id in seen_trade_ids:
                raise ValueError(
                    "Duplicate trade_id in "
                    "trade_states."
                )

            seen_trade_ids.add(
                trade_id
            )

            normalized_states.append(
                normalized_state
            )

        document = (
            self._read_document()
        )

        for normalized_state in (
            normalized_states
        ):
            trade_id = (
                normalized_state[
                    "trade_id"
                ]
            )

            document[
                "trades"
            ][
                trade_id
            ] = deepcopy(
                normalized_state
            )

        self._write_document(
            document
        )

        return deepcopy(
            normalized_states
        )

    # ---------------------------------
    # READ
    # ---------------------------------

    def get_trade(
        self,
        trade_id,
    ):
        """
        Return one persisted trade state.

        Returns None when the trade ID does not exist.
        """

        resolved_trade_id = (
            self._validate_trade_id(
                trade_id
            )
        )

        document = (
            self._read_document()
        )

        trade_state = (
            document[
                "trades"
            ].get(
                resolved_trade_id
            )
        )

        if trade_state is None:
            return None

        return deepcopy(
            trade_state
        )

    def get_all_trades(
        self,
    ):
        """
        Return all persisted trade states.
        """

        document = (
            self._read_document()
        )

        return [
            deepcopy(
                trade_state
            )
            for trade_state in (
                document[
                    "trades"
                ].values()
            )
        ]

    def get_open_trades(
        self,
    ):
        """
        Return persisted OPEN paper trades.
        """

        return [
            trade_state
            for trade_state in (
                self.get_all_trades()
            )
            if str(
                trade_state.get(
                    "status",
                    "",
                )
            ).strip().upper()
            == "OPEN"
        ]

    def get_closed_trades(
        self,
    ):
        """
        Return persisted CLOSED paper trades.
        """

        return [
            trade_state
            for trade_state in (
                self.get_all_trades()
            )
            if str(
                trade_state.get(
                    "status",
                    "",
                )
            ).strip().upper()
            == "CLOSED"
        ]

    # ---------------------------------
    # EXISTS / COUNTS
    # ---------------------------------

    def exists(
        self,
        trade_id,
    ):
        """
        Return True when a trade ID is persisted.
        """

        return (
            self.get_trade(
                trade_id
            )
            is not None
        )

    def count_trades(
        self,
    ):
        """
        Return total persisted trade count.
        """

        return len(
            self.get_all_trades()
        )

    def count_open_trades(
        self,
    ):
        """
        Return persisted OPEN trade count.
        """

        return len(
            self.get_open_trades()
        )

    def count_closed_trades(
        self,
    ):
        """
        Return persisted CLOSED trade count.
        """

        return len(
            self.get_closed_trades()
        )

    # ---------------------------------
    # DELETE
    # ---------------------------------

    def delete_trade(
        self,
        trade_id,
    ):
        """
        Delete one persisted trade state.

        This method exists for repository maintenance
        and tests. The normal paper-trading lifecycle
        should preserve CLOSED trades rather than
        deleting them.

        Returns True when deleted.
        Returns False when not found.
        """

        resolved_trade_id = (
            self._validate_trade_id(
                trade_id
            )
        )

        document = (
            self._read_document()
        )

        if (
            resolved_trade_id
            not in document[
                "trades"
            ]
        ):
            return False

        del document[
            "trades"
        ][
            resolved_trade_id
        ]

        self._write_document(
            document
        )

        return True