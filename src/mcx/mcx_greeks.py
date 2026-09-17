"""Black-76 IV + Greeks for options-on-futures (spec §16).
MCX options are on futures, so we use Black-76, not vanilla Black-Scholes.
"""
import math


def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def black76(F, K, T, r, sigma, option_type="CE"):
    """Returns dict with price, delta, gamma, vega, theta."""
    if T <= 0 or F <= 0 or K <= 0 or sigma <= 0:
        return None
    try:
        d1 = (math.log(F / K) + 0.5 * sigma * sigma * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        disc = math.exp(-r * T)

        if option_type == "CE":
            price = disc * (F * _norm_cdf(d1) - K * _norm_cdf(d2))
            delta = disc * _norm_cdf(d1)
        else:
            price = disc * (K * _norm_cdf(-d2) - F * _norm_cdf(-d1))
            delta = -disc * _norm_cdf(-d1)

        gamma = disc * _norm_pdf(d1) / (F * sigma * math.sqrt(T))
        vega = disc * F * _norm_pdf(d1) * math.sqrt(T) / 100  # per 1% IV
        # Theta per day (approx — futures version)
        theta = -(disc * F * _norm_pdf(d1) * sigma) / (2 * math.sqrt(T)) / 365
        return {
            "price": round(price, 4), "delta": round(delta, 4),
            "gamma": round(gamma, 6), "vega": round(vega, 4),
            "theta": round(theta, 4), "d1": round(d1, 4), "d2": round(d2, 4),
        }
    except Exception:
        return None


def implied_vol(F, K, T, r, market_price, option_type="CE",
                low=0.01, high=3.0, tol=1e-4, max_iter=60):
    """Bisection solve for IV."""
    if T <= 0 or F <= 0 or K <= 0 or market_price <= 0:
        return None
    for _ in range(max_iter):
        mid = (low + high) / 2
        res = black76(F, K, T, r, mid, option_type)
        if not res:
            return None
        diff = res["price"] - market_price
        if abs(diff) < tol:
            return round(mid, 4)
        if diff > 0:
            high = mid
        else:
            low = mid
    return round((low + high) / 2, 4)


def analyze_option(F, K, T, r, market_ltp, option_type="CE"):
    """Full analytic block for one option."""
    iv = implied_vol(F, K, T, r, market_ltp, option_type)
    if iv is None:
        return {"status": "IV_SOLVE_FAILED"}
    g = black76(F, K, T, r, iv, option_type)
    if not g:
        return {"status": "GREEKS_FAILED"}
    intrinsic = max(0, F - K) if option_type == "CE" else max(0, K - F)
    return {
        "status": "OK",
        "iv": iv,
        "iv_pct": round(iv * 100, 2),
        "delta": g["delta"], "gamma": g["gamma"],
        "vega": g["vega"], "theta": g["theta"],
        "model_price": g["price"], "market_ltp": market_ltp,
        "intrinsic": round(intrinsic, 2),
        "time_value": round(market_ltp - intrinsic, 2),
    }


if __name__ == "__main__":
    # Live test using data from earlier check: F=9481, K=9500, CE ltp=332.15
    # T = 6/365, r = 0.07 (Indian 10Y approx)
    F, K = 9481.0, 9500.0
    T = 6 / 365.0
    r = 0.07
    ce_ltp = 332.15
    pe_ltp = 347.65

    print("CE analysis:")
    print(analyze_option(F, K, T, r, ce_ltp, "CE"))
    print("\nPE analysis:")
    print(analyze_option(F, K, T, r, pe_ltp, "PE"))
