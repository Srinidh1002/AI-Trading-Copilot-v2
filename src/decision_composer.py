"""Decision Composer - Separates bias, readiness, and action.
Implements rule-based decision with mandatory gates.
"""


class DecisionComposer:
    MANDATORY_GATES = [
        "market_identity",
        "session_state",
        "spot_freshness",
        "option_freshness",
        "contract_metadata",
        "expiry_validity",
    ]
    
    def compose(self, ctx):
        """ctx keys:
            market_identity_ok: bool
            session_state: dict (phase, can_enter, can_exit)
            spot_freshness: str
            option_freshness: str
            contract_metadata_ok: bool
            expiry_validity_ok: bool
            bull_score: float
            bear_score: float
            bull_pillars: int
            bear_pillars: int
            evidence_coverage: dict (mandatory_x_y, directional_x_y, pct)
            technical_data_ok: bool
            regime: str
            event_block: bool
        """
        gates = {}
        gates["market_identity"] = ctx.get("market_identity_ok", False)
        gates["session_state"] = ctx.get("session_state", {}).get("can_enter", False)
        gates["spot_freshness"] = ctx.get("spot_freshness", "") in ("FRESH", "FRESH_UNCHANGED_PRICE")
        gates["option_freshness"] = ctx.get("option_freshness", "") in ("FRESH", "FRESH_UNCHANGED_PRICE", "NOT_YET_CHECKED")
        gates["contract_metadata"] = ctx.get("contract_metadata_ok", False)
        gates["expiry_validity"] = ctx.get("expiry_validity_ok", False)
        
        # Check mandatory failures
        failed_gates = [k for k, v in gates.items() if not v]
        
        # Event block
        if ctx.get("event_block"):
            return {
                "bias": "NEUTRAL",
                "bias_confidence": 0.0,
                "readiness": "BLOCKED",
                "action": "NO_TRADE",
                "blockers": ["HIGH_IMPACT_EVENT"],
                "gates": gates,
            }
        
        # Compose bias
        bull = ctx.get("bull_score", 0)
        bear = ctx.get("bear_score", 0)
        bull_p = ctx.get("bull_pillars", 0)
        bear_p = ctx.get("bear_pillars", 0)
        
        if bull > bear * 2.0 and bull_p >= 4:
            bias = "BULLISH"
            confidence = "STRONG"
        elif bear > bull * 2.0 and bear_p >= 4:
            bias = "BEARISH"
            confidence = "STRONG"
        elif bull > bear * 1.5 and bull > 1.5 and bull_p >= 3:
            bias = "BULLISH"
            confidence = "MODERATE"
        elif bear > bull * 1.5 and bear > 1.5 and bear_p >= 3:
            bias = "BEARISH"
            confidence = "MODERATE"
        else:
            bias = "NEUTRAL"
            confidence = "WEAK"
        
        # Mandatory gate failures block entry
        if failed_gates:
            return {
                "bias": bias,
                "bias_confidence": confidence,
                "readiness": "BLOCKED",
                "action": "NO_TRADE",
                "blockers": [f"GATE_FAIL:{g}" for g in failed_gates],
                "gates": gates,
            }
        
        # Technical data must be available for entry
        if not ctx.get("technical_data_ok", False):
            return {
                "bias": bias,
                "bias_confidence": confidence,
                "readiness": "WAIT",
                "action": "WAIT",
                "blockers": ["TECHNICAL_MTF_INSUFFICIENT_DATA"],
                "gates": gates,
            }
        
        # VWAP alignment gate (Phase H strategy fix)
        vwap_pos = ctx.get("vwap_position", "UNKNOWN")
        if bias == "BULLISH" and vwap_pos == "BELOW":
            return {
                "bias": bias, "bias_confidence": confidence,
                "readiness": "WAIT", "action": "WAIT",
                "blockers": ["VWAP_NOT_ALIGNED_BULL"],
                "gates": gates,
            }
        if bias == "BEARISH" and vwap_pos == "ABOVE":
            return {
                "bias": bias, "bias_confidence": confidence,
                "readiness": "WAIT", "action": "WAIT",
                "blockers": ["VWAP_NOT_ALIGNED_BEAR"],
                "gates": gates,
            }
        
        # RSI exhaustion gate (Phase H strategy fix)
        rsi_min = ctx.get("rsi_min")
        rsi_max = ctx.get("rsi_max")
        if bias == "BEARISH" and rsi_min is not None and rsi_min < 25:
            return {
                "bias": bias, "bias_confidence": confidence,
                "readiness": "WAIT", "action": "WAIT",
                "blockers": ["OVERSOLD_RSI_SKIP_BEAR"],
                "gates": gates,
            }
        if bias == "BULLISH" and rsi_max is not None and rsi_max > 75:
            return {
                "bias": bias, "bias_confidence": confidence,
                "readiness": "WAIT", "action": "WAIT",
                "blockers": ["OVERBOUGHT_RSI_SKIP_BULL"],
                "gates": gates,
            }
        
        # Short-term momentum gate (Phase H strategy fix #2)
        # If bias is BEARISH but spot rose recently, don't fade the bounce
        recent_move = ctx.get("recent_move_pct")
        if recent_move is not None:
            if bias == "BEARISH" and recent_move > 0.10:
                return {
                    "bias": bias, "bias_confidence": confidence,
                    "readiness": "WAIT", "action": "WAIT",
                    "blockers": [f"SHORT_TERM_BOUNCE({recent_move:+.2f}%)"],
                    "gates": gates,
                }
            if bias == "BULLISH" and recent_move < -0.10:
                return {
                    "bias": bias, "bias_confidence": confidence,
                    "readiness": "WAIT", "action": "WAIT",
                    "blockers": [f"SHORT_TERM_DROP({recent_move:+.2f}%)"],
                    "gates": gates,
                }
        
        # Action from bias
        if bias == "BULLISH":
            action = "BUY_CALL"
            readiness = "READY"
        elif bias == "BEARISH":
            action = "BUY_PUT"
            readiness = "READY"
        else:
            action = "WAIT"
            readiness = "WAIT"
        
        return {
            "bias": bias,
            "bias_confidence": confidence,
            "readiness": readiness,
            "action": action,
            "blockers": [],
            "gates": gates,
        }


if __name__ == "__main__":
    c = DecisionComposer()
    
    # Test 1: All gates pass, strong bullish
    ctx1 = {
        "market_identity_ok": True,
        "session_state": {"phase": "CONTINUOUS", "can_enter": True},
        "spot_freshness": "FRESH",
        "option_freshness": "FRESH",
        "contract_metadata_ok": True,
        "expiry_validity_ok": True,
        "bull_score": 2.0, "bear_score": 0.5, "bull_pillars": 4, "bear_pillars": 1,
        "technical_data_ok": True,
    }
    print("Test 1 (STRONG BULL):", c.compose(ctx1))
    
    # Test 2: Missing gate
    ctx2 = dict(ctx1)
    ctx2["spot_freshness"] = "STALE"
    print()
    print("Test 2 (STALE spot):", c.compose(ctx2))
    
    # Test 3: Event block
    ctx3 = dict(ctx1)
    ctx3["event_block"] = True
    print()
    print("Test 3 (Event block):", c.compose(ctx3))
