"""Offline-only Task 9 completed-session evidence builder."""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, time
from pathlib import Path

from services.certification.task9_historical_certification_replay import (
    LIVE_ROOT,
    Task9HistoricalReplayError,
)
from services.certification.task9_market_session_evaluator import (
    evaluate_task9_market_session,
)
from services.contracts.task9_market_session_policy_v1 import (
    Task9MarketSegment,
    build_task9_market_session_policy,
)
from services.bse_holiday_calendar import get_bse_holiday_calendar
from services.nse_holiday_calendar import get_nse_holiday_calendar
from services.historical_data_cache import HistoricalDataCache
from services.market.task9_live_tick_stream import (
    IST,
    Task9LiveCandleAggregator,
    Task9LiveTickJournal,
)


TIMEFRAMES = ("5m", "15m", "1h", "1d")
MARKETS = (
    ("NIFTY", "NSE", "99926000"),
    ("SENSEX", "BSE", "99919000"),
)


def _forbidden(path: str | Path) -> bool:
    """Return True when a write target is the live Task 9 root or below it."""

    try:
        resolved_path = Path(path).resolve()
        resolved_live_root = LIVE_ROOT.resolve()
    except OSError:
        # Path resolution failure is safety-sensitive; fail closed.
        return True

    return (
        resolved_path == resolved_live_root
        or resolved_live_root in resolved_path.parents
    )


def build_offline_replay_evidence(
    *,
    trading_date: date,
    live_source_root,
    output_file,
    cache_reader=None,
    session_state_resolver=None,
):
    """Build JSON-safe evidence from read-only ticks plus local cache only."""

    if _forbidden(output_file):
        raise Task9HistoricalReplayError(
            "HISTORICAL_REPLAY_LIVE_ROOT_FORBIDDEN"
        )

    if cache_reader is not None and not callable(cache_reader):
        raise TypeError("cache_reader")

    if not callable(session_state_resolver):
        raise Task9HistoricalReplayError(
            "HISTORICAL_REPLAY_SESSION_AUTHORITY_REQUIRED"
        )

    journal = Task9LiveTickJournal(
        live_source_root,
        session_state_resolver=session_state_resolver,
    )
    aggregator = Task9LiveCandleAggregator(journal)

    cutoff = datetime.combine(
        trading_date,
        time(15, 30),
        IST,
    )

    output: dict[str, dict[str, list[list[object]]]] = {}

    for market, exchange, token in MARKETS:
        frames: dict[str, list[list[object]]] = {}

        for timeframe in TIMEFRAMES:
            if timeframe == "1d":
                rows = (
                    ()
                    if cache_reader is None
                    else tuple(
                        cache_reader(
                            exchange,
                            token,
                            timeframe,
                        )
                        or ()
                    )
                )

                try:
                    # Replay intraday decisions may only use daily sessions
                    # completed before this trading date (Friday for Monday,
                    # including exchange-holiday gaps).  No tick-derived 1d.
                    rows = tuple(
                        row for row in rows
                        if datetime.fromisoformat(row[0]).astimezone(IST).date()
                        < trading_date
                    )
                except (IndexError, TypeError, ValueError):
                    rows = ()
            else:
                rows = tuple(
                    (
                        item["start_at"],
                        item["open"],
                        item["high"],
                        item["low"],
                        item["close"],
                        0,
                    )
                    for item in aggregator.candles(
                        market=market,
                        trading_date=trading_date,
                        timeframe=timeframe,
                        as_of=cutoff,
                    )
                )

            if not rows:
                raise Task9HistoricalReplayError(
                    "HISTORICAL_REPLAY_REQUIRED_TIMEFRAME_MISSING_"
                    f"{market}_{timeframe}"
                )

            frames[timeframe] = [
                list(row)
                for row in rows
            ]

        output[market] = frames

    target = Path(output_file)

    # Defense in depth: re-check immediately before filesystem mutation.
    if _forbidden(target):
        raise Task9HistoricalReplayError(
            "HISTORICAL_REPLAY_LIVE_ROOT_FORBIDDEN"
        )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    target.write_text(
        json.dumps(
            output,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    return output


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Task9 offline replay evidence builder"
    )

    parser.add_argument(
        "--trading-date",
        required=True,
    )

    parser.add_argument(
        "--live-source-root",
        default=(
            "data/paper_trading/"
            "certified_runtime/task9/live_stream"
        ),
    )

    parser.add_argument(
        "--historical-cache-root",
        required=True,
    )

    parser.add_argument(
        "--output-file",
        required=True,
    )

    args = parser.parse_args(argv)

    trading_date = date.fromisoformat(args.trading_date)
    cache_path = Path(args.historical_cache_root)

    cache_file = (
        cache_path / "historical_data_cache.json"
        if cache_path.is_dir()
        else cache_path
    )

    cache = HistoricalDataCache(cache_file)

    def local_cache_reader(
        exchange,
        token,
        timeframe,
    ):
        candidate = cache.get_incremental_candidate(
            exchange,
            token,
            timeframe,
        )

        if candidate is None:
            return ()

        return candidate.get(
            "response",
            {},
        ).get(
            "data",
            (),
        )

    session_policy = build_task9_market_session_policy(
        policy_id="task9-offline-replay-cli-session-policy",
        policy_version="1",
        calendar_authority_ref="local-exchange-holiday-calendars",
        nfo_new_entry_cutoff=time(15, 30),
        bfo_new_entry_cutoff=time(15, 30),
    )

    expected_segments = {
        "NIFTY": Task9MarketSegment.NFO_OPTIONS,
        "SENSEX": Task9MarketSegment.BFO_OPTIONS,
    }

    def offline_session_state_resolver(
        *,
        market,
        evaluated_at,
        market_date,
    ):
        if market not in expected_segments:
            raise ValueError("market")

        if market_date != trading_date:
            raise ValueError("market_date")

        if market_date.weekday() >= 5:
            calendar_state = "NON_TRADING_DAY"
        elif market == "NIFTY":
            calendar_state = (
                "NON_TRADING_DAY"
                if get_nse_holiday_calendar().is_holiday(market_date)
                else "TRADING_DAY"
            )
        else:
            calendar_state = (
                "NON_TRADING_DAY"
                if get_bse_holiday_calendar().is_holiday(market_date)
                else "TRADING_DAY"
            )

        aggregate = evaluate_task9_market_session(
            policy=session_policy,
            evaluated_at=evaluated_at,
            market_date=market_date,
            calendar_state=calendar_state,
        )

        expected_segment = expected_segments[market]

        return next(
            state
            for state in aggregate.states
            if state.segment is expected_segment
        )

    evidence = build_offline_replay_evidence(
        trading_date=trading_date,
        live_source_root=args.live_source_root,
        output_file=args.output_file,
        cache_reader=local_cache_reader,
        session_state_resolver=offline_session_state_resolver,
    )

    print(
        json.dumps(
            {
                "trading_date": args.trading_date,
                "row_counts": {
                    market: {
                        frame: len(rows)
                        for frame, rows in frames.items()
                    }
                    for market, frames in evidence.items()
                },
                "network_access_used": False,
            },
            sort_keys=True,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
