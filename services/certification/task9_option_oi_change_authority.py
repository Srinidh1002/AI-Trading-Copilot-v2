"""Persistent live-snapshot authority for Task 9 option OI change evidence."""
from __future__ import annotations

from services.certification.task9_atomic_file_replace import replace_task9_atomic_file

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


IST = ZoneInfo("Asia/Kolkata")


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(name)
    return value.strip().upper()


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(name)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(name)
    return value


def _optional_int(
    value: object,
    name: str,
    *,
    signed: bool = False,
) -> int | None:
    if value is None:
        return None

    if isinstance(value, bool):
        raise ValueError(name)

    if type(value) is int:
        result = value
    elif type(value) is float and value.is_integer():
        result = int(value)
    else:
        raise ValueError(name)

    if not signed and result < 0:
        raise ValueError(name)

    return result


def _strike(value: object) -> float:
    if isinstance(value, bool):
        raise ValueError("strike")

    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("strike") from exc

    if result <= 0:
        raise ValueError("strike")

    return result


def _expiry(value: object) -> str:
    if value is None:
        raise ValueError("expiry")

    if hasattr(value, "isoformat"):
        rendered = value.isoformat()
    else:
        rendered = str(value).strip()

    if not rendered:
        raise ValueError("expiry")

    return rendered


def _token(contract: Mapping[str, object]) -> str:
    value = (
        contract.get("token")
        or contract.get("symbolToken")
        or contract.get("instrument_token")
    )
    return _text(str(value or ""), "token")


def _option_type(contract: Mapping[str, object]) -> str:
    value = str(
        contract.get("option_type", "")
    ).strip().upper()

    if value in {"CALL", "CE"}:
        return "CE"

    if value in {"PUT", "PE"}:
        return "PE"

    symbol = str(
        contract.get(
            "symbol",
            contract.get("trading_symbol", ""),
        )
    ).strip().upper()

    if symbol.endswith("CE"):
        return "CE"

    if symbol.endswith("PE"):
        return "PE"

    raise ValueError("option_type")


def _open_interest(
    contract: Mapping[str, object],
) -> int | None:
    value = contract.get(
        "open_interest",
        contract.get("opnInterest"),
    )
    return _optional_int(
        value,
        "open_interest",
    )


def _provider_change(
    contract: Mapping[str, object],
) -> int | None:
    return _optional_int(
        contract.get("change_in_open_interest"),
        "change_in_open_interest",
        signed=True,
    )


def _identity(
    contract: Mapping[str, object],
) -> tuple[str, str, float, str]:
    return (
        _token(contract),
        _expiry(contract.get("expiry")),
        _strike(contract.get("strike")),
        _option_type(contract),
    )


def _identity_from_stored(
    value: Mapping[str, object],
) -> tuple[str, str, float, str]:
    return (
        _text(value.get("token"), "token"),
        _expiry(value.get("expiry")),
        _strike(value.get("strike")),
        _text(value.get("option_type"), "option_type"),
    )


def _stored_contract(
    contract: Mapping[str, object],
    *,
    change_in_open_interest: int | None,
) -> dict[str, object]:
    token, expiry, strike, option_type = (
        _identity(contract)
    )

    return {
        "token": token,
        "expiry": expiry,
        "strike": strike,
        "option_type": option_type,
        "open_interest": _open_interest(contract),
        "change_in_open_interest": (
            change_in_open_interest
        ),
    }


@dataclass(frozen=True, slots=True)
class Task9OptionOiChangeEnrichmentV1:
    contracts: tuple[dict[str, object], ...]
    status: str
    derived_count: int
    provider_count: int
    matched_count: int
    source_snapshot_timestamp: datetime | None

    def metadata(self) -> dict[str, object]:
        return {
            "status": self.status,
            "derived_count": self.derived_count,
            "provider_count": self.provider_count,
            "matched_count": self.matched_count,
            "source_snapshot_timestamp": (
                self.source_snapshot_timestamp.isoformat()
                if self.source_snapshot_timestamp is not None
                else None
            ),
        }


class Task9OptionOiSnapshotStore:
    """Atomic latest-snapshot persistence per certified option market."""

    def __init__(
        self,
        file_path: str | Path,
    ) -> None:
        self.file_path = Path(file_path)

    def _read(self) -> dict[str, object]:
        if not self.file_path.exists():
            return {
                "version": 1,
                "markets": {},
            }

        try:
            document = json.loads(
                self.file_path.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                "invalid Task 9 option OI snapshot JSON"
            ) from exc

        if (
            type(document) is not dict
            or set(document) != {
                "version",
                "markets",
            }
            or document["version"] != 1
            or type(document["markets"]) is not dict
        ):
            raise ValueError(
                "invalid Task 9 option OI snapshot store"
            )

        return document

    def _write(
        self,
        document: dict[str, object],
    ) -> None:
        self.file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = self.file_path.with_name(
            self.file_path.name + ".tmp"
        )

        try:
            temporary.write_text(
                json.dumps(
                    document,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ),
                encoding="utf-8",
            )
            replace_task9_atomic_file(
                temporary,
                self.file_path,
            )
        finally:
            temporary.unlink(
                missing_ok=True
            )

    def recover(
        self,
        market_key: str,
    ) -> dict[str, object] | None:
        key = _text(
            market_key,
            "market_key",
        )

        value = self._read()["markets"].get(key)

        if value is None:
            return None

        if type(value) is not dict:
            raise ValueError(
                "invalid persisted Task 9 option OI snapshot"
            )

        return value

    def save(
        self,
        *,
        market_key: str,
        snapshot: dict[str, object],
    ) -> str:
        key = _text(
            market_key,
            "market_key",
        )

        if type(snapshot) is not dict:
            raise TypeError("snapshot")

        document = self._read()
        document["markets"][key] = snapshot
        self._write(document)

        return "SAVED"


class Task9OptionOiChangeAuthority:
    """Derive OI change only from an earlier same-session live snapshot."""

    def __init__(
        self,
        store: Task9OptionOiSnapshotStore,
    ) -> None:
        if type(store) is not Task9OptionOiSnapshotStore:
            raise TypeError("store")
        self.store = store

    @staticmethod
    def _market_key(
        underlying_symbol: str,
        spot_exchange: str,
        option_exchange: str,
    ) -> str:
        return "|".join(
            (
                _text(
                    underlying_symbol,
                    "underlying_symbol",
                ),
                _text(
                    spot_exchange,
                    "spot_exchange",
                ),
                _text(
                    option_exchange,
                    "option_exchange",
                ),
            )
        )

    @staticmethod
    def _snapshot_signature(
        contracts,
    ) -> tuple[
        tuple[
            tuple[str, str, float, str],
            int | None,
        ],
        ...,
    ]:
        values = []

        for contract in contracts:
            if not isinstance(
                contract,
                Mapping,
            ):
                raise TypeError(
                    "option contract must be a mapping"
                )

            values.append(
                (
                    _identity(contract),
                    _open_interest(contract),
                )
            )

        signature = tuple(sorted(values, key=lambda item: item[0]))
        if len({item[0] for item in signature}) != len(signature):
            raise ValueError("TASK9_OPTION_OI_DUPLICATE_IDENTITY")
        return signature

    def enrich(
        self,
        *,
        underlying_symbol: str,
        spot_exchange: str,
        option_exchange: str,
        provider_timestamp: datetime,
        contracts,
    ) -> Task9OptionOiChangeEnrichmentV1:
        timestamp = _aware(
            provider_timestamp,
            "provider_timestamp",
        )

        if type(contracts) not in {
            tuple,
            list,
        }:
            raise TypeError(
                "contracts must be a tuple or list"
            )

        # Provider-native OI change is not a certified Task 9 source.
        # Preserve current open interest and contract identity, but discard
        # any incoming provider change value before baseline persistence,
        # duplicate handling, or same-session derivation.
        current_contracts = tuple(
            {
                key: value
                for key, value
                in dict(contract).items()
                if key != "change_in_open_interest"
            }
            if isinstance(contract, Mapping)
            else contract
            for contract in contracts
        )

        current_signature = (
            self._snapshot_signature(
                current_contracts
            )
        )

        market_key = self._market_key(
            underlying_symbol,
            spot_exchange,
            option_exchange,
        )

        trading_date = (
            timestamp.astimezone(IST)
            .date()
            .isoformat()
        )

        previous = self.store.recover(
            market_key
        )

        if previous is None:
            enriched = tuple(
                dict(contract)
                for contract in current_contracts
            )

            self._persist(
                market_key=market_key,
                underlying_symbol=underlying_symbol,
                spot_exchange=spot_exchange,
                option_exchange=option_exchange,
                provider_timestamp=timestamp,
                trading_date=trading_date,
                contracts=enriched,
            )

            return Task9OptionOiChangeEnrichmentV1(
                contracts=enriched,
                status="BASELINE_SAVED",
                derived_count=0,
                provider_count=sum(
                    1
                    for contract in enriched
                    if _provider_change(contract)
                    is not None
                ),
                matched_count=0,
                source_snapshot_timestamp=None,
            )

        previous_timestamp = _aware(
            datetime.fromisoformat(
                str(
                    previous.get(
                        "provider_timestamp"
                    )
                )
            ),
            "persisted provider_timestamp",
        )

        previous_trading_date = str(
            previous.get(
                "trading_date",
                "",
            )
        )

        previous_contracts_raw = previous.get(
            "contracts"
        )

        if type(previous_contracts_raw) is not list:
            raise ValueError(
                "invalid persisted Task 9 option OI contracts"
            )

        previous_signature = tuple(
            sorted(
                (
                    (
                        _identity_from_stored(item),
                        _optional_int(
                            item.get(
                                "open_interest"
                            ),
                            "open_interest",
                        ),
                    )
                    for item in previous_contracts_raw
                    if isinstance(item, Mapping)
                ),
                key=lambda item: item[0],
            )
        )
        if len({item[0] for item in previous_signature}) != len(previous_signature):
            raise ValueError("invalid persisted Task 9 option OI duplicate identity")

        if timestamp < previous_timestamp:
            raise ValueError(
                "TASK9_OPTION_OI_SNAPSHOT_OUT_OF_ORDER"
            )

        if timestamp == previous_timestamp:
            if (
                current_signature
                != previous_signature
            ):
                raise ValueError(
                    "TASK9_OPTION_OI_SNAPSHOT_CONFLICT"
                )

            persisted_changes = {
                _identity_from_stored(item):
                _optional_int(
                    item.get(
                        "change_in_open_interest"
                    ),
                    "change_in_open_interest",
                    signed=True,
                )
                for item in previous_contracts_raw
                if isinstance(item, Mapping)
            }

            enriched = []

            for contract in current_contracts:
                copied = dict(contract)
                identity = _identity(copied)
                persisted_change = (
                    persisted_changes.get(identity)
                )

                if (
                    copied.get(
                        "change_in_open_interest"
                    )
                    is None
                    and persisted_change is not None
                ):
                    copied[
                        "change_in_open_interest"
                    ] = persisted_change

                enriched.append(copied)

            return Task9OptionOiChangeEnrichmentV1(
                contracts=tuple(enriched),
                status="DUPLICATE_SAME_SNAPSHOT",
                derived_count=sum(
                    1
                    for contract in enriched
                    if (
                        _provider_change(contract)
                        is not None
                    )
                ),
                provider_count=0,
                matched_count=len(enriched),
                source_snapshot_timestamp=(
                    previous_timestamp
                ),
            )

        if (
            previous_trading_date
            != trading_date
        ):
            enriched = tuple(
                dict(contract)
                for contract in current_contracts
            )

            self._persist(
                market_key=market_key,
                underlying_symbol=underlying_symbol,
                spot_exchange=spot_exchange,
                option_exchange=option_exchange,
                provider_timestamp=timestamp,
                trading_date=trading_date,
                contracts=enriched,
            )

            return Task9OptionOiChangeEnrichmentV1(
                contracts=enriched,
                status="NEW_TRADING_DAY_BASELINE",
                derived_count=0,
                provider_count=sum(
                    1
                    for contract in enriched
                    if _provider_change(contract)
                    is not None
                ),
                matched_count=0,
                source_snapshot_timestamp=None,
            )

        previous_by_identity = {
            _identity_from_stored(item):
            _optional_int(
                item.get("open_interest"),
                "open_interest",
            )
            for item in previous_contracts_raw
            if isinstance(item, Mapping)
        }

        enriched = []
        matched_count = 0
        derived_count = 0
        provider_count = 0

        for contract in current_contracts:
            copied = dict(contract)
            identity = _identity(copied)

            provider_change = (
                _provider_change(copied)
            )

            if provider_change is not None:
                provider_count += 1
                enriched.append(copied)
                continue

            current_oi = _open_interest(
                copied
            )

            previous_oi = (
                previous_by_identity.get(
                    identity
                )
            )

            if (
                current_oi is not None
                and previous_oi is not None
            ):
                copied[
                    "change_in_open_interest"
                ] = (
                    current_oi
                    - previous_oi
                )
                matched_count += 1
                derived_count += 1

            enriched.append(copied)

        enriched_tuple = tuple(enriched)

        self._persist(
            market_key=market_key,
            underlying_symbol=underlying_symbol,
            spot_exchange=spot_exchange,
            option_exchange=option_exchange,
            provider_timestamp=timestamp,
            trading_date=trading_date,
            contracts=enriched_tuple,
        )

        return Task9OptionOiChangeEnrichmentV1(
            contracts=enriched_tuple,
            status="DERIVED_FROM_PREVIOUS_LIVE_SNAPSHOT",
            derived_count=derived_count,
            provider_count=provider_count,
            matched_count=matched_count,
            source_snapshot_timestamp=(
                previous_timestamp
            ),
        )

    def _persist(
        self,
        *,
        market_key: str,
        underlying_symbol: str,
        spot_exchange: str,
        option_exchange: str,
        provider_timestamp: datetime,
        trading_date: str,
        contracts,
    ) -> None:
        stored_contracts = []

        for contract in contracts:
            if not isinstance(
                contract,
                Mapping,
            ):
                raise TypeError(
                    "option contract must be a mapping"
                )

            stored_contracts.append(
                _stored_contract(
                    contract,
                    change_in_open_interest=(
                        _provider_change(
                            contract
                        )
                    ),
                )
            )

        self.store.save(
            market_key=market_key,
            snapshot={
                "underlying_symbol": _text(
                    underlying_symbol,
                    "underlying_symbol",
                ),
                "spot_exchange": _text(
                    spot_exchange,
                    "spot_exchange",
                ),
                "option_exchange": _text(
                    option_exchange,
                    "option_exchange",
                ),
                "provider_timestamp": (
                    provider_timestamp.isoformat()
                ),
                "trading_date": trading_date,
                "contracts": stored_contracts,
            },
        )


__all__ = (
    "Task9OptionOiChangeAuthority",
    "Task9OptionOiChangeEnrichmentV1",
    "Task9OptionOiSnapshotStore",
)
