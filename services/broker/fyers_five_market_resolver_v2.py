
    FYERS responses from the synchronous SDK use both "d" (depth) and
    "data" (futures_chain / optionchain). We accept either, and search
    common nested list keys.
    """
    if not isinstance(response, Mapping):
        return []
    if response.get("s") not in (None, "ok"):
        return []
    for root_key in ("d", "data"):
        root = response.get(root_key)
        if isinstance(root, list):
            return [r for r in root if isinstance(r, Mapping)]
        if isinstance(root, Mapping):
            for key in ("futures", "futures_list", "rows", "data",
                        "contracts", "expiry", "expiries", "list",
                        "optionsChain"):
                val = root.get(key)
                if isinstance(val, list):
                    return [r for r in val if isinstance(r, Mapping)]
    return []

class FyersFiveMarketInstrumentResolverV2:
    """Deterministic FYERS identity resolver for the five-market universe."""

    def __init__(self, *, data_client, master_store=None, clock=None) -> None:
        if data_client is None:
            raise ValueError("data_client is required")
        self._client = data_client
        self._store = master_store or FyersSymbolMasterStoreV2()
        self._clock = clock or _now_utc

    # ---------- public API ----------

    def resolve(self, *, market_symbol, instrument_type, as_of=None,
                expiry=None, strike=None, option_type=None) -> dict:
        market = get_target_market(market_symbol)
        kind = str(instrument_type or "").upper().strip()
        if kind not in _VALID_INSTRUMENT_TYPES:
            raise FyersResolutionError(
                f"unsupported instrument_type: {instrument_type!r}"
            )
        as_of_dt = as_of if as_of is not None else self._clock()
        if not isinstance(as_of_dt, datetime):
            raise FyersResolutionError("as_of must be a datetime")
        if as_of_dt.tzinfo is None or as_of_dt.utcoffset() is None:
            raise FyersResolutionError("as_of must be timezone-aware")

        if kind == "UNDERLYING":
            if expiry is not None or strike is not None or option_type is not None:
                raise FyersResolutionError("UNDERLYING must not carry derivative args")
            return self._resolve_underlying(market, as_of_dt)
        if kind == "FUTURE":
            if strike is not None or option_type is not None:
                raise FyersResolutionError("FUTURE must not carry strike/option_type")
            return self._resolve_future(market, as_of_dt, _coerce_date(expiry) if expiry else None)
        # OPTION
        if strike is None or option_type is None:
            raise FyersResolutionError("OPTION requires strike and option_type")
        if expiry is None:
            raise FyersResolutionError("OPTION requires expiry")
        return self._resolve_option(
            market, as_of_dt, _coerce_date(expiry), float(strike), str(option_type)
        )

    def nearest_option_expiry(self, *, market_symbol, as_of=None, exclude_same_day=False):
        """Return the nearest master-backed tradable option expiry.

        This is a data-only discovery helper over the already-loaded FYERS
        symbol master.  It performs no provider network call and is used by
        R16 shadow capture to choose the same expiry authority as resolve().
        """
        market = get_target_market(market_symbol)
        as_of_dt = as_of if as_of is not None else self._clock()
        if not isinstance(as_of_dt, datetime):
            raise FyersResolutionError("as_of must be a datetime")
        if as_of_dt.tzinfo is None or as_of_dt.utcoffset() is None:
            raise FyersResolutionError("as_of must be timezone-aware")

        segment = _MARKET_SEGMENTS[market.symbol]["derivative"]
        idx = self._require_index(segment)
        expiries = {
            record.expiry
            for record in idx.records
            if record.instrument_kind == "OPTION"
            and record.expiry is not None
            and _is_expiry_tradable(record.expiry, as_of_dt, market.symbol)
            and (
                not bool(exclude_same_day)
                or record.expiry > as_of_dt.astimezone(_IST_TZ).date()
            )
            and (
                (record.underlying_symbol or "").upper() == market.symbol
                or record.symbol.upper().startswith(market.symbol)
                or record.symbol.upper().startswith(
                    f"{market.derivative_exchange}:{market.symbol}"
                )
            )
        }
        if not expiries:
            raise FyersResolutionError(
                f"no non-expired options for {market.symbol}"
            )
        return min(expiries)

    # ---------- UNDERLYING ----------

    def _resolve_underlying(self, market, as_of_dt):
        if market.market_type == "INDEX":
            provider_symbol = _UNDERLYING_BY_MARKET.get(market.symbol)
            if provider_symbol is None:
                raise FyersResolutionError(
                    f"no canonical FYERS underlying for {market.symbol}"
                )
            return self._build(
                market=market,
                instrument_type="UNDERLYING",
                provider_symbol=provider_symbol,
                provider_exchange=market.underlying_exchange,
                provider_token=None,
                expiry=None, strike=None, option_type=None,
                lot_size=None, tick_size=None,
                metadata_status="NOT_APPLICABLE",
                metadata_source=None,
                resolved_at=as_of_dt,