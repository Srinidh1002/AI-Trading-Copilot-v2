"""FYERS data-only bridge for the existing MCX PAPER analysis stack.

Purpose:
- use canonical FYERS MCX_COM identity evidence;
- expose the existing read-only getMarketData/getCandleData shape;
- keep current MCX strategy/decision/lifecycle code unchanged;
- expose no broker order authority;
- provide no automatic Angel fallback.

This module does not authenticate and does not read environment variables.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from mcx.mcx_contracts import PRODUCTS
from services.broker.fyers_data_compatibility_v2 import (
    FyersDataOnlyCompatibilityV2,
)
from services.broker.fyers_five_market_resolver_v2 import (
    FyersFiveMarketInstrumentResolverV2,
    FyersResolutionError,
)
from services.broker.fyers_symbol_master_v2 import (
    FyersSymbolMasterStoreV2,
)

IST = ZoneInfo("Asia/Kolkata")

SUPPORTED_MCX_FYERS_PRODUCTS = (
    "CRUDEOILM",
    "GOLDM",
    "SILVERM",
)

# Existing mcx_chain.py consumes legacy master records where strike is x100.
# This is a compatibility representation only. FYERS master strike remains
# authoritative and is never modified.
LEGACY_CHAIN_STRIKE_SCALE = 100.0


class MCXFyersBridgeError(RuntimeError):
    """MCX FYERS bridge failed closed."""


def _utc_now():
    return datetime.now(timezone.utc)


def _aware_datetime(value, clock):
    if value is None:
        value = clock()

    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(
            value,
            time(0, 0),
            tzinfo=timezone.utc,
        )

    if not isinstance(value, datetime):
        raise MCXFyersBridgeError("as_of must be date or datetime")

    if value.tzinfo is None or value.utcoffset() is None:
        raise MCXFyersBridgeError("as_of datetime must be timezone-aware")

    return value


def _belongs_to_product(record, product):
    underlying = (record.underlying_symbol or "").upper()

    symbol = record.symbol.upper()

    return (
        underlying == product
        or symbol.startswith(f"MCX:{product}")
        or symbol.startswith(product)
    )


def _legacy_option_record(record):
    return {
        "symbol": record.symbol,
        # Opaque legacy handle. It is deliberately the FYERS provider
        # symbol, not an Angel token.
        "token": record.symbol,
        "provider": "FYERS",
        "provider_symbol": record.symbol,
        "provider_token": record.provider_token,
        "expiry": (record.expiry.isoformat() if record.expiry else None),
        # Existing mcx_chain divides its master strike by 100.
        "strike": (float(record.strike) * LEGACY_CHAIN_STRIKE_SCALE),
        "option_type": record.option_type,
        "lot_size": record.lot_size,
        "tick_size": record.tick_size,
    }


class MCXFyersIdentityResolverV2:
    """FYERS-native identity with legacy-compatible output shape."""

    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def __init__(
        self,
        *,
        data_client,
        master_store=None,
        clock=None,
    ):
        if data_client is None:
            raise ValueError("data_client is required")

        self._clock = clock or _utc_now
        self._store = master_store or FyersSymbolMasterStoreV2()

        self._resolver = FyersFiveMarketInstrumentResolverV2(
            data_client=data_client,
            master_store=self._store,
            clock=self._clock,
        )

    def resolve_active(
        self,
        product,
        as_of=None,
    ):
        product = str(product or "").upper().strip()

        if product not in SUPPORTED_MCX_FYERS_PRODUCTS:
            raise MCXFyersBridgeError(f"unsupported MCX FYERS product: {product!r}")

        if product not in PRODUCTS:
            raise MCXFyersBridgeError(f"product missing from MCX authority: {product}")

        as_of_dt = _aware_datetime(
            as_of,
            self._clock,
        )

        try:
            index = self._store.get_index("MCX_COM")

        except Exception as exc:
            return {
                "product": product,
                "status": "EVIDENCE_UNAVAILABLE_IDENTITY",
                "reason": (f"{type(exc).__name__}: {exc}"),
                "futures": None,
                "option_expiry": None,
                "calls": {},
                "puts": {},
            }

        as_of_ist_date = as_of_dt.astimezone(IST).date()

        # MCX same-day derivative expiry intentionally fails closed.
        options = [
            record
            for record in index.records
            if record.instrument_kind == "OPTION"
            and _belongs_to_product(
                record,
                product,
            )
            and record.expiry is not None
            and record.expiry > as_of_ist_date
            and record.strike is not None
            and record.option_type in ("CE", "PE")
        ]

        if not options:
            return {
                "product": product,
                "status": "EVIDENCE_UNAVAILABLE_IDENTITY",
                "reason": "NO_NON_EXPIRED_OPTION_EVIDENCE",
                "futures": None,
                "option_expiry": None,
                "calls": {},
                "puts": {},
            }

        nearest_expiry = min(record.expiry for record in options)

        option_underlying_futures = [
            record
            for record in index.records
            if record.instrument_kind == "FUTURE"
            and _belongs_to_product(
                record,
                product,
            )
            and record.expiry is not None
            and record.expiry > nearest_expiry
        ]

        if not option_underlying_futures:
            return {
                "product": product,
                "status": "EVIDENCE_UNAVAILABLE_IDENTITY",
                "reason": (
                    f"NO_FUTURE_AFTER_OPTION_EXPIRY:{nearest_expiry.isoformat()}"
                ),
                "futures": None,
                "option_expiry": None,
                "calls": {},
                "puts": {},
            }

        option_future_expiry = min(
            record.expiry for record in option_underlying_futures
        )

        option_future_records = [
            record
            for record in option_underlying_futures
            if record.expiry == option_future_expiry
        ]

        option_future_symbols = {record.symbol for record in option_future_records}

        if len(option_future_symbols) != 1:
            return {
                "product": product,
                "status": "EVIDENCE_UNAVAILABLE_IDENTITY",
                "reason": (
                    "AMBIGUOUS_OPTION_UNDERLYING_FUTURE:"
                    f"{option_future_expiry.isoformat()}"
                ),
                "futures": None,
                "option_expiry": None,
                "calls": {},
                "puts": {},
            }

        try:
            future = self._resolver.resolve(
                market_symbol=product,
                instrument_type="FUTURE",
                as_of=as_of_dt,
                expiry=option_future_expiry,
            )

        except FyersResolutionError as exc:
            return {
                "product": product,
                "status": "EVIDENCE_UNAVAILABLE_IDENTITY",
                "reason": (
                    f"OPTION_UNDERLYING_FUTURE_RESOLUTION:{type(exc).__name__}: {exc}"
                ),
                "futures": None,
                "option_expiry": None,
                "calls": {},
                "puts": {},
            }

        resolved_future_symbol = str(future.get("provider_symbol") or "").strip()

        if (
            not resolved_future_symbol
            or resolved_future_symbol not in option_future_symbols
        ):
            return {
                "product": product,
                "status": "EVIDENCE_UNAVAILABLE_IDENTITY",
                "reason": ("OPTION_UNDERLYING_FUTURE_MISMATCH"),
                "futures": None,
                "option_expiry": None,
                "calls": {},
                "puts": {},
            }

        nearest = [record for record in options if record.expiry == nearest_expiry]

        calls = {}
        puts = {}

        for record in nearest:
            strike = float(record.strike)
            side = calls if record.option_type == "CE" else puts

            if strike in side:
                return {
                    "product": product,
                    "status": "EVIDENCE_UNAVAILABLE_IDENTITY",
                    "reason": (
                        f"AMBIGUOUS_OPTION_IDENTITY:{record.option_type}:{strike}"
                    ),
                    "futures": None,
                    "option_expiry": None,
                    "calls": {},
                    "puts": {},
                }

            side[strike] = _legacy_option_record(record)

        if not calls or not puts:
            return {
                "product": product,
                "status": "EVIDENCE_UNAVAILABLE_IDENTITY",
                "reason": "INCOMPLETE_CE_PE_UNIVERSE",
                "futures": None,
                "option_expiry": None,
                "calls": {},
                "puts": {},
            }

        future_record = {
            "symbol": future["provider_symbol"],
            # Same opaque FYERS-symbol handle used by compatibility data calls.
            "token": future["provider_symbol"],
            "provider": "FYERS",
            "provider_symbol": future["provider_symbol"],
            "provider_token": future.get("provider_token"),
            "expiry": future.get("expiry"),
            "lot_size": future.get("lot_size"),
            "tick_size": future.get("tick_size"),
        }

        return {
            "product": product,
            "as_of": as_of_dt.isoformat(),
            "provider": "FYERS",
            "futures": future_record,
            "option_expiry": (nearest_expiry.isoformat()),
            "calls": calls,
            "puts": puts,
            "status": "OK",
        }

    def resolve_provider_symbol(
        self,
        exchange,
        tradingsymbol,
        symboltoken,
    ):
        if str(exchange or "").upper() != "MCX":
            raise MCXFyersBridgeError("MCX bridge rejects non-MCX exchange")

        values = []

        for raw in (
            symboltoken,
            tradingsymbol,
        ):
            if raw is None:
                continue

            text = str(raw).strip()

            if text and text not in values:
                values.append(text)

        if not values:
            raise MCXFyersBridgeError("provider-symbol handle is required")

        try:
            index = self._store.get_index("MCX_COM")
        except Exception as exc:
            raise MCXFyersBridgeError(f"MCX_COM master unavailable: {exc}") from exc

        matches = set()

        for record in index.records:
            if not any(
                _belongs_to_product(record, product)
                for product in SUPPORTED_MCX_FYERS_PRODUCTS
            ):
                continue

            for value in values:
                if record.symbol == value or (
                    record.provider_token is not None and record.provider_token == value
                ):
                    matches.add(record.symbol)

        if len(matches) != 1:
            raise MCXFyersBridgeError(
                "FYERS provider-symbol identity missing or ambiguous"
            )

        return next(iter(matches))


def _normalize_crudeoilm_fyers_execution_depth(
    row,
):
    """Preserve FYERS CRUDEOILM depth quantity without unit conversion.

    FYERS identifies market-depth values as quantities but the currently
    available provider evidence does not establish that those quantities are
    lot counts or contract-unit counts for MCX commodity options.

    Therefore the bridge must preserve the provider value exactly and keep
    certification quantity semantics explicitly unverified.
    """

    if not isinstance(
        row,
        dict,
    ):
        raise MCXFyersBridgeError("normalized FULL row invalid")

    token = str(row.get("symbolToken") or "").strip().upper()

    if not token.startswith("MCX:CRUDEOILM"):
        return

    row["provider_depth_quantity_unit"] = "UNVERIFIED"

    row["depth_quantity_semantics_verified"] = False


class MCXFyersDataCompatibilityV2:
    """MCX-specific guard around the existing FYERS compatibility layer."""

    provider = "FYERS"
    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False
    live_execution_eligible = False

    def __init__(
        self,
        *,
        client,
        identity,
    ):
        self._compat = FyersDataOnlyCompatibilityV2(
            client=client,
            symbol_resolver=(identity.resolve_provider_symbol),
        )

    def ltpData(
        self,
        exchange,
        tradingsymbol,
        symboltoken,
    ):
        result = self._compat.ltpData(
            exchange,
            tradingsymbol,
            symboltoken,
        )

        result = dict(result)
        result["provider"] = "FYERS"
        result["data_only"] = True

        return result

    def getMarketData(
        self,
        mode,
        exchange_tokens,
    ):
        result = self._compat.getMarketData(
            mode,
            exchange_tokens,
        )

        rows = result.get("data", {}).get("fetched", [])

        if not isinstance(rows, list):
            raise MCXFyersBridgeError("normalized FULL rows missing")

        for row in rows:
            if not isinstance(row, dict):
                raise MCXFyersBridgeError("normalized FULL row invalid")

            row["provider"] = "FYERS"
            row["data_only"] = True
            row["live_execution_eligible"] = False

            # MCX execution quantity normalization is provider/product
            # scoped. Only CRUDEOILM is live-proven at this checkpoint.
            _normalize_crudeoilm_fyers_execution_depth(row)

        return result

    def getCandleData(self, params):
        result = self._compat.getCandleData(params)

        rows = result.get("data")

        if not isinstance(rows, list):
            raise MCXFyersBridgeError("normalized candle rows missing")

        normalized = []

        for index, row in enumerate(rows):
            if not isinstance(row, list) or len(row) < 6:
                raise MCXFyersBridgeError(f"invalid candle row {index}")

            # Existing MCX pandas readers expect exactly:
            # [timestamp, open, high, low, close, volume].
            # FYERS OI may be a seventh field and is deliberately not
            # smuggled into this legacy candle shape.
            normalized.append(list(row[:6]))

        result = dict(result)
        result["data"] = normalized
        result["provider"] = "FYERS"
        result["data_only"] = True

        return result


@dataclass(frozen=True)
class MCXFyersBridgeV2:
    identity: MCXFyersIdentityResolverV2
    data: MCXFyersDataCompatibilityV2

    provider: str = "FYERS"
    data_only: bool = True
    order_capability_allowed: bool = False
    automatic_fallback_allowed: bool = False
    live_execution_eligible: bool = False


def build_mcx_fyers_bridge_v2(
    *,
    data_client,
    master_store=None,
    clock=None,
):
    identity = MCXFyersIdentityResolverV2(
        data_client=data_client,
        master_store=master_store,
        clock=clock,
    )

    data = MCXFyersDataCompatibilityV2(
        client=data_client,
        identity=identity,
    )

    return MCXFyersBridgeV2(
        identity=identity,
        data=data,
    )
