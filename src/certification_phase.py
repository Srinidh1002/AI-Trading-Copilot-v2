"""Certification session-phase classifier - equity-only, neutral.

Subdivides the CONTINUOUS entry window into three equal deterministic
buckets used ONLY as certification diversity evidence. Does NOT modify
entry eligibility. market_phase.can_enter() remains the sole authority.

Boundaries are derived mathematically from MarketPhaseEngine.CONTINUOUS_START
and MarketPhaseEngine.NEW_ENTRY_CUTOFF. No independent hardcoded clock
strings in policy code.

Not imported by MCX. Equity-only.
"""
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
    _IST = ZoneInfo("Asia/Kolkata")
except Exception:
    _IST = None

from market_phase import MarketPhaseEngine


CERT_PHASE_EARLY   = "EARLY_CONTINUOUS"
CERT_PHASE_MID     = "MID_CONTINUOUS"
CERT_PHASE_LATE    = "LATE_CONTINUOUS"
CERT_PHASE_UNKNOWN = "UNKNOWN"

CERT_PHASES_VALID = (CERT_PHASE_EARLY, CERT_PHASE_MID, CERT_PHASE_LATE)


def _to_minutes(t):
    return t.hour * 60 + t.minute


_CONTINUOUS_START = MarketPhaseEngine.CONTINUOUS_START
_ENTRY_CUTOFF     = MarketPhaseEngine.NEW_ENTRY_CUTOFF

_WINDOW_MINUTES = _to_minutes(_ENTRY_CUTOFF) - _to_minutes(_CONTINUOUS_START)

assert _WINDOW_MINUTES > 0, (
    "certification_phase: non-positive continuous window (%d)" % _WINDOW_MINUTES
)
assert _WINDOW_MINUTES % 3 == 0, (
    "certification_phase: continuous window %d min does not divide into 3"
    % _WINDOW_MINUTES
)

_THIRD_MIN = _WINDOW_MINUTES // 3


def _add_minutes(t, minutes):
    base = datetime(2000, 1, 1, t.hour, t.minute)
    return (base + timedelta(minutes=minutes)).time()


_B1_START = _CONTINUOUS_START
_B1_END   = _add_minutes(_CONTINUOUS_START, _THIRD_MIN)
_B2_START = _B1_END
_B2_END   = _add_minutes(_CONTINUOUS_START, _THIRD_MIN * 2)
_B3_START = _B2_END
_B3_END   = _ENTRY_CUTOFF

PHASE_BOUNDARIES = {
    CERT_PHASE_EARLY: (_B1_START, _B1_END),
    CERT_PHASE_MID:   (_B2_START, _B2_END),
    CERT_PHASE_LATE:  (_B3_START, _B3_END),
}


def _resolve_now_ist():
    if _IST is not None:
        return datetime.now(_IST)
    return datetime.now()


def _normalize_dt(dt):
    if dt is None:
        return _resolve_now_ist()
    if dt.tzinfo is None:
        return dt
    if _IST is not None:
        return dt.astimezone(_IST)
    return dt


def classify_certification_session_phase(dt=None, engine=None):
    """Return the certification session-phase bucket for a given time.

    Returns one of CERT_PHASES_VALID inside the CONTINUOUS window.
    Returns CERT_PHASE_UNKNOWN outside that window (pre-open, close-drain,
    weekend, holiday, after-hours).

    Does NOT modify entry eligibility; engine.can_enter() remains the
    sole authority.

    dt: explicit datetime (naive treated as IST wall clock; aware
        converted to Asia/Kolkata for classification). When omitted,
        current Asia/Kolkata time is used.
    engine: optional MarketPhaseEngine instance. If None, a NIFTY engine
        is used for weekend/holiday checks.
    """
    d = _normalize_dt(dt)
    if engine is None:
        engine = MarketPhaseEngine("NIFTY")
    try:
        if not engine.can_enter(d):
            return CERT_PHASE_UNKNOWN
    except Exception:
        return CERT_PHASE_UNKNOWN
    t = d.time()
    for name in CERT_PHASES_VALID:
        start, end = PHASE_BOUNDARIES[name]
        if start <= t < end:
            return name
    return CERT_PHASE_UNKNOWN
