"""OI Analysis - Detects OI walls, support/resistance from open interest."""


class OIAnalyzer:
    def analyze(self, chain):
        """Extract OI walls and support/resistance levels."""
        if not chain or chain.get("status") != "OK":
            return {"status": "EVIDENCE_UNAVAILABLE"}
        
        ce_data = chain.get("ce_data", {})
        pe_data = chain.get("pe_data", {})
        atm = chain.get("atm_strike", 0)
        
        # Find top 3 CE OI (resistance) and PE OI (support)
        # RULE 3: if all OI is zero, analyzer has no evidence - abstain
        _total_ce_oi = sum(o.get("oi", 0) for o in ce_data.values())
        _total_pe_oi = sum(o.get("oi", 0) for o in pe_data.values())
        if _total_ce_oi == 0 or _total_pe_oi == 0:
            return {
                "status": "EVIDENCE_UNAVAILABLE",
                "reason": "ZERO_OI_ALL_STRIKES",
                "total_ce_oi": _total_ce_oi,
                "total_pe_oi": _total_pe_oi,
            }

        ce_sorted = sorted(ce_data.values(), key=lambda x: x.get("oi", 0), reverse=True)
        pe_sorted = sorted(pe_data.values(), key=lambda x: x.get("oi", 0), reverse=True)
        
        resistance = [
            {"strike": o["strike"], "oi": o["oi"], "distance_from_atm": o["strike"] - atm}
            for o in ce_sorted[:3]
        ]
        support = [
            {"strike": o["strike"], "oi": o["oi"], "distance_from_atm": atm - o["strike"]}
            for o in pe_sorted[:3]
        ]
        
        # Max pain (weighted strike where total writer loss is minimized)
        all_strikes = sorted(set(list(ce_data.keys()) + list(pe_data.keys())))
        max_pain = None
        if all_strikes:
            pain_by_strike = []
            for test_strike in all_strikes:
                total_pain = 0
                for s, ce in ce_data.items():
                    if test_strike > s:
                        total_pain += (test_strike - s) * ce.get("oi", 0)
                for s, pe in pe_data.items():
                    if test_strike < s:
                        total_pain += (s - test_strike) * pe.get("oi", 0)
                pain_by_strike.append((test_strike, total_pain))
            
            if pain_by_strike:
                max_pain = min(pain_by_strike, key=lambda x: x[1])[0]
        
        # OI imbalance at ATM ± 2 strikes
        near_range = [atm - 100, atm - 50, atm, atm + 50, atm + 100]
        near_ce_oi = sum(ce_data.get(float(s), {}).get("oi", 0) for s in near_range)
        near_pe_oi = sum(pe_data.get(float(s), {}).get("oi", 0) for s in near_range)
        near_pcr = (near_pe_oi / near_ce_oi) if near_ce_oi > 0 else None
        
        return {
            "status": "OK",
            "resistance_levels": resistance,
            "support_levels": support,
            "max_pain": max_pain,
            "near_pcr": round(near_pcr, 3) if near_pcr else None,
            "near_ce_oi": near_ce_oi,
            "near_pe_oi": near_pe_oi,
        }
    
    def describe(self, analysis):
        if not analysis or analysis.get("status") != "OK":
            return "OI_UNAVAILABLE"
        r = analysis.get("resistance_levels", [])
        s = analysis.get("support_levels", [])
        return (f"Resistance: {[x['strike'] for x in r]} | "
                f"Support: {[x['strike'] for x in s]} | "
                f"MaxPain: {analysis.get('max_pain')} | "
                f"near_PCR: {analysis.get('near_pcr')}")


if __name__ == "__main__":
    print("OIAnalyzer module loaded OK")
    print("Methods: analyze(chain)")
