"""Market Selector - Picks NIFTY vs SENSEX based on evidence quality."""


class MarketSelector:
    def score_market(self, ctx):
        """Score 0-100 for market opportunity."""
        score = 0.0
        reasons = []
        
        # Data quality (25 pts)
        coverage_pct = ctx.get("evidence_coverage_pct", 0)
        score += (coverage_pct / 100) * 25
        if coverage_pct >= 80:
            reasons.append(f"coverage={coverage_pct:.0f}%")
        
        # Bias strength (25 pts)
        bias_conf = ctx.get("bias_confidence", "WEAK")
        if bias_conf == "STRONG":
            score += 25
            reasons.append("strong_bias")
        elif bias_conf == "MODERATE":
            score += 15
            reasons.append("moderate_bias")
        elif bias_conf == "WEAK":
            score += 5
        
        # Regime clarity (15 pts)
        regime = ctx.get("regime", "UNKNOWN")
        if regime in ("TRENDING_UP", "TRENDING_DOWN"):
            score += 15
            reasons.append(f"regime={regime}")
        elif regime in ("RANGE_BOUND", "LOW_VOLATILITY_COMPRESSION"):
            score += 8
        elif regime == "HIGH_VOLATILITY":
            score += 4
            reasons.append("high_vol_caution")
        
        # Option liquidity (20 pts)
        top_score = ctx.get("top_strike_score", 0)
        score += (top_score / 100) * 20
        if top_score >= 80:
            reasons.append(f"top_strike={top_score:.0f}")
        
        # Readiness (15 pts)
        readiness = ctx.get("readiness", "BLOCKED")
        if readiness == "READY":
            score += 15
            reasons.append("READY")
        elif readiness == "WAIT":
            score += 5
        
        return round(score, 1), reasons
    
    def select(self, nifty_ctx, sensex_ctx):
        """Pick best market or DUAL_WATCH."""
        n_score, n_reasons = self.score_market(nifty_ctx)
        s_score, s_reasons = self.score_market(sensex_ctx)
        
        n_eligible = nifty_ctx.get("readiness") == "READY"
        s_eligible = sensex_ctx.get("readiness") == "READY"
        
        if not n_eligible and not s_eligible:
            return {
                "selection": "DUAL_WATCH",
                "nifty_score": n_score,
                "sensex_score": s_score,
                "nifty_reasons": n_reasons,
                "sensex_reasons": s_reasons,
                "reason": "Neither market ready",
            }
        
        if n_eligible and not s_eligible:
            return {
                "selection": "SELECT_NIFTY",
                "nifty_score": n_score,
                "sensex_score": s_score,
                "reason": "Only NIFTY eligible",
            }
        
        if s_eligible and not n_eligible:
            return {
                "selection": "SELECT_SENSEX",
                "nifty_score": n_score,
                "sensex_score": s_score,
                "reason": "Only SENSEX eligible",
            }
        
        # Both eligible - pick higher score
        if n_score > s_score * 1.1:
            return {
                "selection": "SELECT_NIFTY",
                "nifty_score": n_score,
                "sensex_score": s_score,
                "reason": f"NIFTY score {n_score} > SENSEX {s_score}",
            }
        elif s_score > n_score * 1.1:
            return {
                "selection": "SELECT_SENSEX",
                "nifty_score": n_score,
                "sensex_score": s_score,
                "reason": f"SENSEX score {s_score} > NIFTY {n_score}",
            }
        else:
            return {
                "selection": "DUAL_WATCH",
                "nifty_score": n_score,
                "sensex_score": s_score,
                "reason": f"Scores close ({n_score} vs {s_score})",
            }


if __name__ == "__main__":
    sel = MarketSelector()
    
    # Test 1: NIFTY strong
    nifty = {
        "evidence_coverage_pct": 90,
        "bias_confidence": "STRONG",
        "regime": "TRENDING_DOWN",
        "top_strike_score": 85,
        "readiness": "READY",
    }
    sensex = {
        "evidence_coverage_pct": 65,
        "bias_confidence": "WEAK",
        "regime": "CHOPPY",
        "top_strike_score": 0,
        "readiness": "WAIT",
    }
    print("Test 1:", sel.select(nifty, sensex))
    
    # Test 2: Both weak
    nifty2 = {"evidence_coverage_pct": 50, "bias_confidence": "WEAK",
              "regime": "UNKNOWN", "top_strike_score": 0, "readiness": "BLOCKED"}
    sensex2 = dict(nifty2)
    print()
    print("Test 2:", sel.select(nifty2, sensex2))
