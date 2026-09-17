"""Strike Ranking v2 - Ranks option candidates using liquidity + delta + cost."""


class StrikeRanker:
    def __init__(self, liquidity_gate):
        self.gate = liquidity_gate
    
    def rank(self, chain, direction, atm_strike, capital=100000):
        """Rank option candidates in given direction.
        
        Args:
            chain: from OptionChainEngine.fetch()
            direction: 'BULLISH' or 'BEARISH'
            atm_strike: spot's ATM strike
            capital: available capital
        """
        if not chain or chain.get("status") != "OK":
            return {"status": "CHAIN_UNAVAILABLE", "candidates": []}
        
        opt_type = "CE" if direction == "BULLISH" else "PE"
        pool = chain.get("ce_data", {}) if opt_type == "CE" else chain.get("pe_data", {})
        
        candidates = []
        for strike, opt in pool.items():
            # Liquidity gate first
            passes, reasons = self.gate.check(opt)
            
            # Compute score even for rejected (for logging)
            score = self._score(opt, opt_type, atm_strike, capital, passes)
            
            candidates.append({
                "strike": strike,
                "type": opt_type,
                "ltp": opt.get("ltp", 0),
                "symbol": opt.get("symbol"),
                "token": opt.get("token"),
                "bid": opt.get("bid", 0),
                "ask": opt.get("ask", 0),
                "oi": opt.get("oi", 0),
                "volume": opt.get("volume", 0),
                "spread_pct": opt.get("spread_pct"),
                "passes_liquidity": passes,
                "reject_reasons": reasons,
                "score": round(score, 1),
            })
        
        # Sort by score desc; passing candidates first
        candidates.sort(key=lambda x: (x["passes_liquidity"], x["score"]), reverse=True)
        
        return {
            "status": "OK",
            "direction": direction,
            "opt_type": opt_type,
            "candidates": candidates,
            "top_pick": candidates[0] if candidates and candidates[0]["passes_liquidity"] else None,
        }
    
    def _score(self, opt, opt_type, atm, capital, passes_liquidity):
        """Score 0-100."""
        if not passes_liquidity:
            return 0
        
        score = 40.0  # base for passing liquidity
        
        # Distance from ATM (25 pts) - closer is better
        dist = abs(opt.get("strike", atm) - atm)
        if dist == 0:
            score += 25
        elif dist <= 50:
            score += 20
        elif dist <= 100:
            score += 15
        else:
            score += 8
        
        # Premium range (20 pts) - sweet spot for intraday
        ltp = opt.get("ltp", 0)
        if 50 <= ltp <= 200:
            score += 20
        elif 200 < ltp <= 400:
            score += 15
        elif ltp > 400:
            score += 8
        else:
            score += 3
        
        # ITM vs ATM vs OTM (15 pts)
        if opt_type == "CE":
            if opt["strike"] < atm:
                score += 15  # ITM
            elif opt["strike"] == atm:
                score += 12  # ATM
            else:
                score += 6   # OTM
        else:  # PE
            if opt["strike"] > atm:
                score += 15  # ITM
            elif opt["strike"] == atm:
                score += 12  # ATM
            else:
                score += 6   # OTM
        
        return min(100, score)
    
    def describe(self, result):
        if not result or result.get("status") != "OK":
            return "RANKING_UNAVAILABLE"
        
        top = result.get("top_pick")
        if not top:
            return "NO_ELIGIBLE_CANDIDATES"
        
        cands = result.get("candidates", [])[:5]
        lines = [f"Top {top['type']} {top['strike']} score={top['score']} LTP={top['ltp']}"]
        for c in cands:
            status = "OK " if c["passes_liquidity"] else "REJ"
            lines.append(f"  [{status}] {c['type']} {c['strike']} score={c['score']} LTP={c['ltp']} "
                        f"spread={c['spread_pct']}% vol={c['volume']} oi={c['oi']}")
        return "\n".join(lines)


if __name__ == "__main__":
    from liquidity_gate import LiquidityGate
    gate = LiquidityGate()
    ranker = StrikeRanker(gate)
    
    # Mock chain
    chain = {
        "status": "OK",
        "atm_strike": 23600,
        "ce_data": {
            23500.0: {"strike": 23500, "type": "CE", "ltp": 175, "bid": 174.5, "ask": 175.5,
                      "spread_pct": 0.57, "volume": 5000, "oi": 30000, "symbol": "NIFTY23500CE", "token": "1"},
            23600.0: {"strike": 23600, "type": "CE", "ltp": 120, "bid": 119.5, "ask": 120.5,
                      "spread_pct": 0.83, "volume": 8000, "oi": 50000, "symbol": "NIFTY23600CE", "token": "2"},
            23700.0: {"strike": 23700, "type": "CE", "ltp": 75, "bid": 74, "ask": 76,
                      "spread_pct": 2.67, "volume": 3000, "oi": 25000, "symbol": "NIFTY23700CE", "token": "3"},
        },
        "pe_data": {},
    }
    
    result = ranker.rank(chain, "BULLISH", 23600)
    print(ranker.describe(result))
