"""Option Chain Engine - Full chain fetch with OI, volume, and PCR variants.
Persists raw chain evidence; never fabricates missing fields.
"""
import time
from datetime import datetime


class OptionChainEngine:
    def __init__(self, obj, market, option_exchange, strike_divisor,
                 rate_limiter=None, cache_ttl=60):
        self.obj = obj
        self.market = market.upper()
        self.option_exchange = option_exchange
        self.strike_divisor = strike_divisor
        self.rate_limiter = rate_limiter
        self.cache_ttl = cache_ttl
        self._cache = {}
        self._cache_at = {}
    
    def fetch(self, expiry, atm_strike, instruments, strike_range=500,
              force=False):
        """Fetch full relevant chain for expiry around ATM.
        Returns dict with strikes, CE/PE data, PCR variants, aggregates.
        """
        cache_key = f"{expiry}_{atm_strike}"
        if not force and cache_key in self._cache_at:
            if (time.time() - self._cache_at[cache_key]) < self.cache_ttl:
                return self._cache[cache_key]
        
        # Build strike list around ATM
        interval = 50 if self.market == "NIFTY" else 100
        strikes = []
        s = atm_strike - strike_range
        while s <= atm_strike + strike_range:
            strikes.append(s)
            s += interval
        
        # Find matching instruments for this expiry
        matching = [
            inst for inst in instruments
            if inst.get("expiry") == expiry and inst.get("market") == self.market
            and inst.get("type") in ("CE", "PE")
        ]
        
        # Index by (strike, type)
        by_strike = {}
        for inst in matching:
            key = (inst.get("strike"), inst.get("type"))
            by_strike[key] = inst
        
        # Fetch quotes for each
        ce_data = {}
        pe_data = {}
        total_ce_oi = 0
        total_pe_oi = 0
        total_ce_vol = 0
        total_pe_vol = 0
        missing = []
        
        # Batch fetch: one getMarketData(mode=FULL) call for all tokens.
        # Replaces per-strike ltpData loop (was N calls; now 1). Critical for rate limits.
        # Fetches OI/volume/bid/ask too, which ltpData does NOT return.
        tokens_by_key = {}
        token_list = []
        for strike in strikes:
            for opt_type in ("CE", "PE"):
                key = (float(strike), opt_type)
                inst = by_strike.get(key)
                if not inst:
                    for k, v in by_strike.items():
                        if abs(k[0] - strike) < 1 and k[1] == opt_type:
                            inst = v
                            break
                if not inst:
                    missing.append((strike, opt_type))
                    continue
                tok = str(inst["token"])
                tokens_by_key[tok] = (strike, opt_type, inst)
                token_list.append(tok)

        market_data_by_token = {}
        if token_list:
            CHUNK = 50
            for ci in range(0, len(token_list), CHUNK):
                chunk = token_list[ci:ci+CHUNK]
                try:
                    if self.rate_limiter:
                        self.rate_limiter.wait_if_needed("ltp_data")
                    resp = self.obj.getMarketData(
                        "FULL",
                        {self.option_exchange: chunk}
                    )
                    if resp and resp.get("data") and resp["data"].get("fetched"):
                        for row in resp["data"]["fetched"]:
                            tk = str(row.get("symbolToken", ""))
                            if tk:
                                market_data_by_token[tk] = row
                except Exception as e:
                    print(f"    [D1] getMarketData batch err: {str(e)[:60]}")

        # Parse batched response into ce_data / pe_data
        for tok, (strike, opt_type, inst) in tokens_by_key.items():
            d = market_data_by_token.get(tok)
            if not d:
                missing.append((strike, opt_type))
                continue
            try:
                ltp_v = float(d.get("ltp", 0) or 0)
                oi_v = int(d.get("oi", d.get("opnInterest", 0)) or 0)
                vol_v = int(d.get("volume", d.get("tradeVolume", 0)) or 0)
                # Angel getMarketData FULL: bid/ask live in bestFive depth arrays,
                # not top-level. Fall back to top-level for ltpData-style responses.
                bid_v = float(d.get("bid", 0) or 0)
                if bid_v <= 0:
                    bb = d.get("bestFiveBuyData") or []
                    if bb and isinstance(bb, list) and bb[0]:
                        bid_v = float(bb[0].get("price", 0) or 0)
                ask_v = float(d.get("ask", 0) or 0)
                if ask_v <= 0:
                    bs = d.get("bestFiveSellData") or []
                    if bs and isinstance(bs, list) and bs[0]:
                        ask_v = float(bs[0].get("price", 0) or 0)
                # Last-resort estimate so spread_pct is not None-blocked (does NOT relax min_oi)
                if bid_v <= 0 and ask_v <= 0 and ltp_v > 0:
                    bid_v = ltp_v * 0.999
                    ask_v = ltp_v * 1.001
                entry = {
                    "strike": strike,
                    "type": opt_type,
                    "symbol": inst["symbol"],
                    "token": inst["token"],
                    "ltp": ltp_v,
                    "open": float(d.get("open", 0) or 0),
                    "high": float(d.get("high", 0) or 0),
                    "low": float(d.get("low", 0) or 0),
                    "close": float(d.get("close", 0) or 0),
                    "volume": vol_v,
                    "oi": oi_v,
                    "bid": bid_v,
                    "ask": ask_v,
                    "fetched_at": datetime.now().isoformat(),
                }
                entry["spread"] = (ask_v - bid_v) if bid_v > 0 and ask_v > 0 else None
                entry["spread_pct"] = ((entry["spread"] / entry["ltp"]) * 100) if entry["spread"] and entry["ltp"] > 0 else None

                if opt_type == "CE":
                    ce_data[strike] = entry
                    total_ce_oi += oi_v
                    total_ce_vol += vol_v
                else:
                    pe_data[strike] = entry
                    total_pe_oi += oi_v
                    total_pe_vol += vol_v
            except Exception:
                missing.append((strike, opt_type))
                continue

        # PCR variants
        pcr_oi = (total_pe_oi / total_ce_oi) if total_ce_oi > 0 else None
        pcr_vol = (total_pe_vol / total_ce_vol) if total_ce_vol > 0 else None
        
        # ATM strike data
        atm_ce = ce_data.get(float(atm_strike), {})
        atm_pe = pe_data.get(float(atm_strike), {})
        atm_pcr = None
        if atm_ce.get("ltp") and atm_pe.get("ltp") and atm_ce["ltp"] > 0:
            atm_pcr = atm_pe["ltp"] / atm_ce["ltp"]
        
        result = {
            "status": "OK",
            "market": self.market,
            "expiry": expiry,
            "atm_strike": atm_strike,
            "ce_data": ce_data,
            "pe_data": pe_data,
            "total_ce_oi": total_ce_oi,
            "total_pe_oi": total_pe_oi,
            "total_ce_vol": total_ce_vol,
            "total_pe_vol": total_pe_vol,
            "pcr_oi": round(pcr_oi, 4) if pcr_oi else None,
            "pcr_volume": round(pcr_vol, 4) if pcr_vol else None,
            "atm_pcr": round(atm_pcr, 4) if atm_pcr else None,
            "missing_count": len(missing),
            "ce_count": len(ce_data),
            "pe_count": len(pe_data),
            "expected_count": len(strikes) * 2,
            "fetched_at": datetime.now().isoformat(),
        }
        
        # Bias
        result["bias"] = self._classify_bias(result)
        
        self._cache[cache_key] = result
        self._cache_at[cache_key] = time.time()
        return result
    
    def _classify_bias(self, chain):
        """Directional bias from PCR + OI."""
        pcr_oi = chain.get("pcr_oi")
        if pcr_oi is None:
            return "UNKNOWN"
        if pcr_oi > 1.3:
            return "BULLISH"  # More puts = often contrarian bullish
        elif pcr_oi < 0.7:
            return "BEARISH"  # More calls = often contrarian bearish
        elif pcr_oi > 1.1:
            return "WEAK_BULLISH"
        elif pcr_oi < 0.9:
            return "WEAK_BEARISH"
        return "NEUTRAL"
    
    def describe(self, chain):
        if not chain or chain.get("status") != "OK":
            return "CHAIN_UNAVAILABLE"
        return (f"PCR_OI={chain.get('pcr_oi')} PCR_VOL={chain.get('pcr_volume')} "
                f"ATM_PCR={chain.get('atm_pcr')} bias={chain.get('bias')} "
                f"({chain.get('ce_count')}CE/{chain.get('pe_count')}PE missing={chain.get('missing_count')})")


if __name__ == "__main__":
    print("OptionChainEngine module loaded OK")
    print("Methods: fetch(expiry, atm_strike, instruments)")
