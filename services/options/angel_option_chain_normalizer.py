"""Pure conversion of captured Angel option payloads to canonical PAPER inputs."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from services.contracts.option_contract_universe_v1 import OptionContractUniverseV1
from services.contracts.option_contract_v1 import OptionContractV1
from services.option_chain_intelligence.normalization import normalize_option_chain_records
from services.paper_orchestration.certified_live_provider_readers import CertifiedIndexMarketSpecV1


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None: raise ValueError(name)
    return value

def _num(value: object, name: str, *, positive: bool = False, integer: bool = False, signed: bool = False):
    if value is None: return None
    if isinstance(value, bool): raise ValueError(name)
    try: value = int(value) if integer else float(value)
    except (TypeError, ValueError) as exc: raise ValueError(name) from exc
    if not math.isfinite(value) or (value <= 0 if positive else value < 0 and not signed): raise ValueError(name)
    return value

def _expiry(value: object) -> date:
    if isinstance(value, datetime): return value.date()
    if isinstance(value, date): return value
    if isinstance(value, str):
        try: return date.fromisoformat(value.strip())
        except ValueError: pass
    raise ValueError("expiry")

def _spec(value: object) -> CertifiedIndexMarketSpecV1:
    if type(value) is not CertifiedIndexMarketSpecV1: raise TypeError("market_spec")
    return value

def _type(value: object) -> str:
    normalized = str(value or "").strip().upper()
    if normalized == "CE": normalized = "CALL"
    if normalized == "PE": normalized = "PUT"
    if normalized not in {"CALL", "PUT"}: raise ValueError("option_type")
    return normalized

@dataclass(frozen=True, slots=True)
class AngelOptionNormalizationResultV1:
    snapshot: object | None
    universe: OptionContractUniverseV1 | None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    provider_state: str = "OK"
    underlying_symbol: str | None = None
    exchange: str | None = None
    option_exchange: str | None = None

    def __post_init__(self) -> None:
        if self.snapshot is None and self.universe is None and not self.blockers: raise ValueError("unavailable option data requires blocker")
        if (self.snapshot is None) != (self.universe is None): raise ValueError("snapshot/universe availability mismatch")

def normalize_angel_option_chain(*, contracts: object, market_spec: CertifiedIndexMarketSpecV1, spot_price: object, provider_timestamp: datetime, evaluated_at: datetime, provider_state: str = "OK", blockers: tuple[str, ...] = (), warnings: tuple[str, ...] = ()) -> AngelOptionNormalizationResultV1:
    """Normalize captured ``LiveOptionChainBuilder.build_chain`` contracts only."""
    spec = _spec(market_spec); _aware(provider_timestamp, "provider_timestamp"); _aware(evaluated_at, "evaluated_at")
    spot = _num(spot_price, "spot_price", positive=True)
    if not isinstance(contracts, Sequence) or isinstance(contracts, (str, bytes)) or not contracts:
        return AngelOptionNormalizationResultV1(None, None, tuple(blockers) or ("OPTION_CHAIN_UNAVAILABLE",), tuple(warnings), provider_state, spec.underlying_symbol, spec.exchange, spec.option_exchange)
    values: list[OptionContractV1] = []; records = []; tokens=set(); symbols=set(); identities=set(); expiry_value=None
    for raw in contracts:
        if not isinstance(raw, Mapping): raise ValueError("option contract mapping")
        segment = str(raw.get("exchange", raw.get("option_exchange", spec.option_exchange))).strip().upper()
        if segment != spec.option_exchange: raise ValueError("option segment mismatch")
        underlying = str(raw.get("underlying", raw.get("underlying_symbol", spec.underlying_symbol))).strip().upper()
        if underlying != spec.underlying_symbol: raise ValueError("underlying mismatch")
        token = str(raw.get("token", raw.get("symbolToken", ""))).strip(); symbol = str(raw.get("symbol", raw.get("trading_symbol", ""))).strip().upper()
        if not token or not symbol or token in tokens or symbol in symbols: raise ValueError("duplicate or missing contract identity")
        tokens.add(token); symbols.add(symbol); option_type = _type(raw.get("option_type", "CE" if symbol.endswith("CE") else "PE" if symbol.endswith("PE") else None))
        expiry = _expiry(raw.get("expiry"));
        if expiry < evaluated_at.date(): raise ValueError("expired contract")
        if expiry_value is None: expiry_value = expiry
        if expiry != expiry_value: raise ValueError("mixed expiry snapshot")
        strike = _num(raw.get("strike"), "strike", positive=True); lot = _num(raw.get("lot_size", raw.get("lotsize")), "lot_size", positive=True, integer=True)
        tick = _num(raw.get("tick_size"), "tick_size", positive=True)
        bid = _num(raw.get("bid"), "bid"); ask = _num(raw.get("ask"), "ask")
        if bid is not None and ask is not None and ask < bid: raise ValueError("crossed market")
        last = _num(raw.get("premium", raw.get("ltp")), "premium"); volume = _num(raw.get("volume", raw.get("tradeVolume")), "volume"); oi = _num(raw.get("open_interest", raw.get("opnInterest")), "open_interest")
        change = _num(raw.get("change_in_open_interest"), "change_in_open_interest", signed=True)
        iv = _num(raw.get("iv", raw.get("implied_volatility")), "iv")
        identity = (expiry, strike, option_type)
        if identity in identities: raise ValueError("duplicate contract identity")
        identities.add(identity)
        values.append(OptionContractV1(token, spec.underlying_symbol, spec.exchange, symbol, option_type, strike, expiry, lot, provider_timestamp, instrument_token=token, tick_size=tick, last_price=last, bid_price=bid, ask_price=ask, open_interest=oi, volume=volume, implied_volatility=iv, metadata={"derivative_segment": segment, **{key: raw[key] for key in ("delta", "gamma", "theta", "vega") if key in raw and raw[key] is not None}}))
        records.append({"strike": strike, "option_type": option_type, "ltp": last, "bid_price": bid, "ask_price": ask, "bid_quantity": _num(raw.get("bid_quantity"), "bid_quantity", integer=True), "ask_quantity": _num(raw.get("ask_quantity"), "ask_quantity", integer=True), "volume": int(volume) if volume is not None else None, "open_interest": int(oi) if oi is not None else None, "change_in_open_interest": int(change) if change is not None else None, "implied_volatility": iv, "underlying_value": spot, "source_record_id": token, "is_complete": True})
    snapshot = normalize_option_chain_records(underlying_symbol=spec.underlying_symbol, exchange=spec.exchange, expiry=expiry_value, underlying_value=spot, source_timestamp=provider_timestamp, provider_name="ANGEL_ONE", records=tuple(records), clock=lambda: evaluated_at)
    universe = OptionContractUniverseV1(f"angel-universe:{spec.symboltoken}:{provider_timestamp.isoformat()}", spec.underlying_symbol, spec.exchange, evaluated_at, spot, tuple(values), "ANGEL_ONE", True)
    return AngelOptionNormalizationResultV1(snapshot, universe, tuple(blockers), tuple(warnings), provider_state, spec.underlying_symbol, spec.exchange, spec.option_exchange)
