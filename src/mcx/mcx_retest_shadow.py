"""R18D CRUDE breakout/retest shadow instrumentation.

Observation only. The tracker consumes data already produced by the MCX PAPER
cycle. It has no provider client, order authority, PAPER-state authority, or
certification authority.
"""

SCHEMA_VERSION = "r18d.crude_retest_shadow.v1"


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _one_minute_bar(mtf):
    one = ((mtf or {}).get("timeframes") or {}).get("1m") or {}
    if one.get("status") != "OK":
        return {}
    return {
        "timestamp": one.get("last_bar_timestamp"),
        "open": _number(one.get("last_open")),
        "high": _number(one.get("last_high")),
        "low": _number(one.get("last_low")),
        "close": _number(one.get("last_close")),
    }


def _breakout_direction(regime_name):
    if regime_name == "BREAKOUT_DOWN":
        return "BEARISH"
    if regime_name == "BREAKOUT_UP":
        return "BULLISH"
    return None


def _five_minute_boundary(structure, direction):
    five = ((structure or {}).get("timeframes") or {}).get("5m") or {}
    key = "swing_low" if direction == "BEARISH" else "swing_high"
    return _number(five.get(key))


def _distance(a, b):
    if a is None or b is None:
        return None
    return abs(float(a) - float(b))


class BreakoutRetestShadowTracker:
    """Track ordered cycle/bar evidence without affecting trading decisions."""

    def __init__(self, product):
        self.product = str(product or "").upper()
        self.previous = None
        self.episode = None
        self.episode_counter = 0

    def _new_episode(self, timestamp, ltp, regime_name, structure, bar):
        direction = _breakout_direction(regime_name)
        if direction is None:
            return

        reference = None
        if self.previous:
            reference = _five_minute_boundary(
                self.previous.get("structure"),
                direction,
            )
            if reference is None:
                reference = _number(self.previous.get("future_ltp"))

        if reference is None:
            reference = _five_minute_boundary(structure, direction)
        if reference is None:
            reference = ltp

        self.episode_counter += 1
        event_time = bar.get("timestamp") or timestamp
        self.episode = {
            "episode_id": f"{self.product}-{self.episode_counter}",
            "direction": direction,
            "breakout_reference": reference,
            "breakout_price": ltp,
            "breakout_at": event_time,
            "extension_observed": False,
            "extension_price": None,
            "extension_at": None,
            "retest_observed": False,
            "retest_price": None,
            "retest_at": None,
            "rejection_observed": False,
            "rejection_price": None,
            "rejection_at": None,
        }

    def _observe_bearish(self, timestamp, ltp, bar):
        episode = self.episode
        event_time = bar.get("timestamp") or timestamp
        low = bar.get("low")
        high = bar.get("high")
        extension_candidate = low if low is not None else ltp
        retest_candidate = high if high is not None else ltp

        if not episode["extension_observed"]:
            if (
                event_time != episode["breakout_at"]
                and extension_candidate is not None
                and extension_candidate < episode["breakout_price"]
            ):
                episode["extension_observed"] = True
                episode["extension_price"] = extension_candidate
                episode["extension_at"] = event_time
            return

        if not episode["retest_observed"]:
            if event_time == episode["extension_at"]:
                return
            extension_distance = _distance(
                episode["breakout_reference"],
                episode["extension_price"],
            )
            retest_distance = _distance(
                episode["breakout_reference"],
                retest_candidate,
            )
            if (
                retest_candidate is not None
                and episode["extension_price"] is not None
                and retest_candidate > episode["extension_price"]
                and extension_distance is not None
                and retest_distance is not None
                and retest_distance < extension_distance
            ):
                episode["retest_observed"] = True
                episode["retest_price"] = retest_candidate
                episode["retest_at"] = event_time
            return

        if not episode["rejection_observed"]:
            if event_time == episode["retest_at"]:
                return
            rejection_candidate = low if low is not None else ltp
            retest_distance = _distance(
                episode["breakout_reference"],
                episode["retest_price"],
            )
            rejection_distance = _distance(
                episode["breakout_reference"],
                rejection_candidate,
            )
            if (
                rejection_candidate is not None
                and episode["retest_price"] is not None
                and rejection_candidate < episode["retest_price"]
                and retest_distance is not None
                and rejection_distance is not None
                and rejection_distance > retest_distance
            ):
                episode["rejection_observed"] = True
                episode["rejection_price"] = rejection_candidate
                episode["rejection_at"] = event_time

    def _observe_bullish(self, timestamp, ltp, bar):
        episode = self.episode
        event_time = bar.get("timestamp") or timestamp
        high = bar.get("high")
        low = bar.get("low")
        extension_candidate = high if high is not None else ltp
        retest_candidate = low if low is not None else ltp

        if not episode["extension_observed"]:
            if (
                event_time != episode["breakout_at"]
                and extension_candidate is not None
                and extension_candidate > episode["breakout_price"]
            ):
                episode["extension_observed"] = True
                episode["extension_price"] = extension_candidate
                episode["extension_at"] = event_time
            return

        if not episode["retest_observed"]:
            if event_time == episode["extension_at"]:
                return
            extension_distance = _distance(
                episode["breakout_reference"],
                episode["extension_price"],
            )
            retest_distance = _distance(
                episode["breakout_reference"],
                retest_candidate,
            )
            if (
                retest_candidate is not None
                and episode["extension_price"] is not None
                and retest_candidate < episode["extension_price"]
                and extension_distance is not None
                and retest_distance is not None
                and retest_distance < extension_distance
            ):
                episode["retest_observed"] = True
                episode["retest_price"] = retest_candidate
                episode["retest_at"] = event_time
            return

        if not episode["rejection_observed"]:
            if event_time == episode["retest_at"]:
                return
            rejection_candidate = high if high is not None else ltp
            retest_distance = _distance(
                episode["breakout_reference"],
                episode["retest_price"],
            )
            rejection_distance = _distance(
                episode["breakout_reference"],
                rejection_candidate,
            )
            if (
                rejection_candidate is not None
                and episode["retest_price"] is not None
                and rejection_candidate > episode["retest_price"]
                and retest_distance is not None
                and rejection_distance is not None
                and rejection_distance > retest_distance
            ):
                episode["rejection_observed"] = True
                episode["rejection_price"] = rejection_candidate
                episode["rejection_at"] = event_time

    def observe(
        self,
        *,
        timestamp,
        future_ltp,
        regime,
        structure,
        mtf,
        decision,
        setup,
    ):
        ltp = _number(future_ltp)
        regime_name = str((regime or {}).get("regime") or "UNKNOWN")
        direction = _breakout_direction(regime_name)
        bar = _one_minute_bar(mtf)

        previous_regime = None
        if self.previous:
            previous_regime = self.previous.get("regime")

        if direction and previous_regime != regime_name:
            self._new_episode(timestamp, ltp, regime_name, structure, bar)

        if self.episode and direction == self.episode.get("direction"):
            if direction == "BEARISH":
                self._observe_bearish(timestamp, ltp, bar)
            else:
                self._observe_bullish(timestamp, ltp, bar)

        evidence = None
        if self.episode:
            evidence = {
                "breakout_observed": True,
                "extension_observed": bool(self.episode["extension_observed"]),
                "retest_observed": bool(self.episode["retest_observed"]),
                "rejection_observed": bool(self.episode["rejection_observed"]),
                "breakout_at": self.episode["breakout_at"],
                "extension_at": self.episode["extension_at"],
                "retest_at": self.episode["retest_at"],
                "rejection_at": self.episode["rejection_at"],
            }

        ordered_complete = bool(
            evidence
            and evidence["extension_observed"]
            and evidence["retest_observed"]
            and evidence["rejection_observed"]
        )

        record = {
            "schema_version": SCHEMA_VERSION,
            "mode": "SHADOW_ONLY",
            "product": self.product,
            "timestamp": timestamp,
            "provider_calls_added": 0,
            "trading_authority": False,
            "certification_countable": False,
            "future_ltp": ltp,
            "regime": regime_name,
            "decision_action": (decision or {}).get("action"),
            "production_setup": (setup or {}).get("setup"),
            "one_minute_bar": bar,
            "episode": dict(self.episode) if self.episode else None,
            "explicit_retest_evidence_detail": evidence,
            "ordered_sequence_complete": ordered_complete,
        }

        self.previous = {
            "timestamp": timestamp,
            "future_ltp": ltp,
            "regime": regime_name,
            "structure": structure,
        }
        return record
