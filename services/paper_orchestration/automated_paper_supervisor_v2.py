"""Automated PAPER supervisor for the five-market campaign.

Process supervision ONLY. Never:
  * submits broker orders
  * changes strategy
  * modifies certification counters
  * decides entries/exits

Responsibility:
  * start one worker process per market at the market open
  * stop it cleanly at the market close
  * prevent duplicate workers
  * classify worker exit codes for restart policy
  * run post-close analysis once per day per market
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from services.paper_orchestration.supervisor_lock_v2 import acquire as _acquire_lock
from services.paper_orchestration.worker_lock_v2 import market_worker_available
from services.paper_orchestration.certification_halt_v2 import (
    all_complete as _cert_all_complete,
    market_state as _cert_market_state,
)
from services.paper_orchestration.worker_session_authority_v2 import (
    authority_for as _session_authority_for,
)
IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True, slots=True)
class WorkerSpecV2:
    name: str
    script: str
    args: tuple
    market_type: str
    open_hhmm: tuple
    close_hhmm: tuple
    state_file: str
    predictions_file: str
    outcomes_file: str


WORKERS_V2: tuple = (
    WorkerSpecV2(
        name="NIFTY",
        script="run_nifty.py",
        args=(),
        market_type="INDEX",
        open_hhmm=(9, 15),
        close_hhmm=(15, 30),
        state_file="data/paper_trades/nifty_experimental.json",
        predictions_file="data/paper_trades/nifty_predictions.jsonl",
        outcomes_file="data/paper_trades/nifty_outcomes.jsonl",
    ),
    WorkerSpecV2(
        name="SENSEX",
        script="run_sensex.py",
        args=(),
        market_type="INDEX",
        open_hhmm=(9, 15),
        close_hhmm=(15, 30),
        state_file="data/paper_trades/sensex_experimental.json",
        predictions_file="data/paper_trades/sensex_predictions.jsonl",
        outcomes_file="data/paper_trades/sensex_outcomes.jsonl",
    ),
    WorkerSpecV2(
        name="CRUDEOILM",
        script=r"src\mcx\mcx_paper_bot.py",
        args=("--product", "CRUDEOILM"),
        market_type="COMMODITY",
        open_hhmm=(9, 0),
        close_hhmm=(23, 30),
        state_file="data/paper_trades/mcx_crudeoilm_experimental.json",
        predictions_file="data/paper_trades/mcx_crudeoilm_predictions.jsonl",
        outcomes_file="data/paper_trades/mcx_crudeoilm_outcomes.jsonl",
    ),
    WorkerSpecV2(
        name="GOLDM",
        script=r"src\mcx\mcx_paper_bot.py",
        args=("--product", "GOLDM"),
        market_type="COMMODITY",
        open_hhmm=(9, 0),
        close_hhmm=(23, 30),
        state_file="data/paper_trades/mcx_goldm_experimental.json",
        predictions_file="data/paper_trades/mcx_goldm_predictions.jsonl",
        outcomes_file="data/paper_trades/mcx_goldm_outcomes.jsonl",
    ),
    WorkerSpecV2(
        name="NATGASMINI",
        script=r"src\mcx\mcx_paper_bot.py",
        args=("--product", "NATGASMINI"),
        market_type="COMMODITY",
        open_hhmm=(9, 0),
        close_hhmm=(23, 30),
        state_file="data/paper_trades/mcx_natgasmini_experimental.json",
        predictions_file="data/paper_trades/mcx_natgasmini_predictions.jsonl",
        outcomes_file="data/paper_trades/mcx_natgasmini_outcomes.jsonl",
    ),
)


from typing import NamedTuple


class StartOutcome(NamedTuple):
    status: str  # STARTED | DRY_RUN | START_OWNERSHIP_HOLD | START_ENV_FAILURE | START_SPAWN_FAILURE
    process: object = None
    note: str = ""


@dataclass
class WorkerRuntimeV2:
    spec: WorkerSpecV2
    process: Optional[subprocess.Popen] = None
    last_start_ist: Optional[datetime] = None
    last_stop_ist: Optional[datetime] = None
    last_analysis_date: Optional[date] = None
    exit_history: list = field(default_factory=list)
    restart_failures: list = field(default_factory=list)
    next_restart_ist: Optional[datetime] = None
    circuit_open: bool = False
    last_healthy_ist: Optional[datetime] = None
    last_expected_stop_ist: Optional[datetime] = None
    consecutive_healthy_ticks: int = 0


class AutomatedPaperSupervisorV2:
    MAX_RESTART_FAILURES = 3
    RESTART_WINDOW = timedelta(minutes=15)
    MAX_RESTART_BACKOFF_SECONDS = 300
    HEALTHY_PERIOD = timedelta(seconds=180)
    STOP_ACK_TIMEOUT_SECONDS = 5.0
    OWNERSHIP_HOLD_BACKOFF_SECONDS = 300
    def __init__(
        self,
        *,
        repo_root: str,
        python_exe: str,
        dry_run: bool = False,
        log_dir: str = "logs/supervisor",
        clock=None,
        markets=None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.python_exe = python_exe
        self.dry_run = dry_run
        self.log_dir = self.repo_root / log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.clock = clock or (lambda: datetime.now(IST))
        self.markets = tuple(markets) if markets else None
        self.workers = {spec.name: WorkerRuntimeV2(spec=spec) for spec in WORKERS_V2}

    def _enabled_specs(self):
        if self.markets is None:
            return WORKERS_V2
        wanted = {m.upper() for m in self.markets}
        return tuple(s for s in WORKERS_V2 if s.name in wanted)

    def _now_ist(self):
        return self.clock()

    def _hhmm_to_dt(self, hhmm, day):
        return datetime(day.year, day.month, day.day, hhmm[0], hhmm[1], tzinfo=IST)

    def _is_session_active(self, spec, now):
        o = self._hhmm_to_dt(spec.open_hhmm, now.date())
        c = self._hhmm_to_dt(spec.close_hhmm, now.date())
        return o <= now < c

    def _is_session_done_today(self, spec, now):
        c = self._hhmm_to_dt(spec.close_hhmm, now.date())
        return now >= c

    def _is_weekend(self, day):
        return day.weekday() >= 5

    def _start_worker(self, spec):
        """Start one worker process.

        Returns StartOutcome. Callers route status into the per-market
        restart authority; None is never returned for a real start.
        """
        if self.dry_run:
            self._log(f"[DRY_RUN] would start {spec.name}: {spec.script} {spec.args}")
            return StartOutcome("DRY_RUN")
        if not market_worker_available(spec.name):
            self._log(f"[{spec.name}] WORKER_OWNERSHIP_HOLD")
            return StartOutcome("START_OWNERSHIP_HOLD", note="lock held by another process")

        try:
            from services.broker.fyers_auth_v2 import (
                FyersAuthError as _FyersAuthError,
                build_fyers_child_env_v2 as _build_env,
            )
        except Exception as exc:
            self._log(
                f"[{spec.name}] START_FAILED: FYERS_ENV_IMPORT: "
                f"{type(exc).__name__}"
            )
            return StartOutcome("START_ENV_FAILURE", note=f"import:{type(exc).__name__}")

        try:
            env = _build_env(str(self.repo_root / ".env"))
        except _FyersAuthError as exc:
            self._log(
                f"[{spec.name}] START_FAILED: FYERS_ENV: "
                f"{getattr(exc, 'reason_code', 'AUTH_MISSING')}"
            )
            return StartOutcome("START_ENV_FAILURE", note=getattr(exc, "reason_code", "AUTH_MISSING"))
        except Exception as exc:
            self._log(
                f"[{spec.name}] START_FAILED: FYERS_ENV: "
                f"{type(exc).__name__}"
            )
            return StartOutcome("START_ENV_FAILURE", note=type(exc).__name__)

        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONUTF8"] = "1"
        env["PAPER_STOP_REQUEST_FILE"] = str(
            self.log_dir / "stops" / f"{spec.name}.request"
        )
        env["PAPER_STOP_ACK_FILE"] = str(self.log_dir / "stops" / f"{spec.name}.ack")

        stdout_path = self.log_dir / f"{spec.name}_stdout.log"
        stderr_path = self.log_dir / f"{spec.name}_stderr.log"
        args = [self.python_exe, "-u", spec.script, *spec.args]
        out_f = open(stdout_path, "a", encoding="utf-8", errors="replace")
        err_f = open(stderr_path, "a", encoding="utf-8", errors="replace")
        try:
            proc = subprocess.Popen(args, cwd=str(self.repo_root),
                                    stdout=out_f, stderr=err_f, env=env)
        except Exception as exc:
            out_f.close(); err_f.close()
            self._log(f"[{spec.name}] START_FAILED: {type(exc).__name__}: {exc}")
            return StartOutcome("START_SPAWN_FAILURE", note=type(exc).__name__)
        self._log(f"[{spec.name}] started pid={proc.pid}")
        # Phase 9.8 - stagger worker starts so the first expiryData
        # probe of each market does not collide with FYERS per-second
        # rate limits. 2s between starts, ~10s to launch all five.
        time.sleep(2.0)
        return StartOutcome("STARTED", process=proc)

    def _stop_worker(self, spec, grace_seconds=30.0):
        rt = self.workers[spec.name]
        proc = rt.process
        if proc is None or proc.poll() is not None:
            return
        if self.dry_run:
            self._log(f"[DRY_RUN] would stop {spec.name} pid={proc.pid}")
            return
        stop_dir = self.log_dir / "stops"
        stop_dir.mkdir(parents=True, exist_ok=True)
        request = stop_dir / f"{spec.name}.request"
        acknowledgement = stop_dir / f"{spec.name}.ack"
        acknowledgement.unlink(missing_ok=True)
        request.write_text("STOP_NEW_ENTRIES", encoding="utf-8")
        self._log(f"[{spec.name}] cooperative stop requested pid={proc.pid}")

        # Step 1 — wait briefly for explicit ACK
        ack_observed = False
        ack_deadline = time.monotonic() + self.STOP_ACK_TIMEOUT_SECONDS
        while time.monotonic() < ack_deadline:
            if proc.poll() is not None:
                break
            if acknowledgement.exists():
                ack_observed = True
                self._log(f"[{spec.name}] STOP_ACK received")
                break
            time.sleep(0.2)

        # Step 2 — wait for exit up to grace_seconds total
        deadline = time.monotonic() + grace_seconds
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            time.sleep(0.5)
        if proc.poll() is None:
            self._log(f"[{spec.name}] ABNORMAL_SHUTDOWN_TIMEOUT pid={proc.pid} ack={ack_observed}")
            try:
                proc.terminate()
            except Exception as exc:
                self._log(f"[{spec.name}] forced terminate failed: {exc}")
        if proc.poll() is None:
            try:
                proc.kill()
            except Exception as exc:
                self._log(f"[{spec.name}] forced kill failed: {exc}")
        request.unlink(missing_ok=True)
        self._log(f"[{spec.name}] stopped rc={proc.poll()}")

    def _classify_exit(self, spec, rc, *, expected_alive=True):
        if rc is None:
            return "STILL_RUNNING"
        if rc == 0:
            return "UNEXPECTED_EXIT_ZERO" if expected_alive else "CLEAN_SESSION_END"
        if rc in (1, 2):
            return "STARTUP_FAILURE"
        return "RUNTIME_FAILURE"

    def _record_ownership_hold(self, rt, now):
        """Another process owns this market's worker lock. Push the
        next retry forward without incrementing restart_failures; contention
        is not a crash and must not open the circuit.
        """
        rt.next_restart_ist = now + timedelta(seconds=self.OWNERSHIP_HOLD_BACKOFF_SECONDS)
        self._log(
            f"[{rt.spec.name}] WORKER_OWNERSHIP_BACKOFF seconds={self.OWNERSHIP_HOLD_BACKOFF_SECONDS}"
        )

    def _record_healthy(self, rt, now):
        rt.last_healthy_ist = now
        rt.consecutive_healthy_ticks += 1
        if (
            rt.last_start_ist is not None
            and now - rt.last_start_ist >= self.HEALTHY_PERIOD
            and rt.restart_failures
        ):
            rt.restart_failures.clear()
            rt.next_restart_ist = None
            self._log(f"[{rt.spec.name}] WORKER_HEALTHY_PERIOD_CLEARED")

    def _record_failure(self, rt, now, rc):
        rt.restart_failures = [
            stamp for stamp in rt.restart_failures if stamp >= now - self.RESTART_WINDOW
        ]
        rt.restart_failures.append(now)
        if len(rt.restart_failures) >= self.MAX_RESTART_FAILURES:
            rt.circuit_open = True
            self._log(f"[{rt.spec.name}] WORKER_CIRCUIT_OPEN rc={rc}")
            return
        delay = min(2 ** (len(rt.restart_failures) - 1) * 30, self.MAX_RESTART_BACKOFF_SECONDS)
        rt.next_restart_ist = now + timedelta(seconds=delay)
        self._log(f"[{rt.spec.name}] WORKER_RESTART_BACKOFF seconds={delay} rc={rc}")

    def _may_start(self, rt, now):
        if rt.circuit_open:
            return False
        if rt.next_restart_ist is not None and now < rt.next_restart_ist:
            return False
        return True

    def _run_analysis_once(self, spec, day):
        if self.dry_run:
            self._log(f"[DRY_RUN] would run analysis for {spec.name} {day}")
            return
        try:
            from services.paper_orchestration.campaign_analysis_v2 import (
                analyze_market_day, write_daily_report,
            )
            summary = analyze_market_day(market=spec.name, day=day,
                                         repo_root=str(self.repo_root))
            path = write_daily_report(summary, repo_root=str(self.repo_root))
            self._log(f"[{spec.name}] daily report -> {path}")
        except Exception as exc:
            self._log(f"[{spec.name}] analysis failed: {type(exc).__name__}: {exc}")

    def tick(self):
        if _cert_all_complete():
            print("CERTIFICATION_COMPLETE: all markets at 100; supervisor idle")
            return
        now = self._now_ist()
        day = now.date()
        self._log(f"tick at {now.isoformat()}")
        for spec in self._enabled_specs():
            rt = self.workers[spec.name]

            # Wave 0 — certification authority gate
            ms = _cert_market_state(spec.name)
            if ms.status == "HOLD":
                self._log(f"[{spec.name}] CERT_AUTHORITY_HOLD reason={ms.reason}")
                if rt.process is not None and rt.process.poll() is None:
                    self._stop_worker(spec)
                    rt.last_expected_stop_ist = now
                continue
            if ms.status == "COMPLETE":
                if rt.process is not None and rt.process.poll() is None:
                    self._stop_worker(spec)
                    rt.last_expected_stop_ist = now
                    self._log(f"[{spec.name}] CERT_COMPLETE counter={ms.counter}; worker stopped")
                if rt.last_analysis_date != day:
                    self._run_analysis_once(spec, day)
                    rt.last_analysis_date = day
                    self._log(f"[{spec.name}] FINAL_ANALYSIS_DONE counter={ms.counter}")
                continue

            # Wave 1 — calendar authority
            auth = _session_authority_for(spec, now)
            if not auth.calendar_authoritative:
                self._log(
                    f"[{spec.name}] CALENDAR_HOLD status={auth.status} note={auth.note}"
                )
                # Do not start. Do not stop a running worker: it must be able to close positions.
                continue

            if auth.session_open:
                if rt.process is None or rt.process.poll() is not None:
                    if rt.process is not None:
                        rc = rt.process.poll()
                        expected_alive = not (
                            rt.last_expected_stop_ist is not None
                            and rt.last_start_ist is not None
                            and rt.last_expected_stop_ist >= rt.last_start_ist
                        )
                        status = self._classify_exit(spec, rc, expected_alive=expected_alive)
                        rt.exit_history.append((day, rc, status))
                        self._log(f"[{spec.name}] WORKER_EXIT rc={rc} classified={status}")
                        if status in ("STARTUP_FAILURE", "RUNTIME_FAILURE", "UNEXPECTED_EXIT_ZERO"):
                            self._record_failure(rt, now, rc)
                    if not self._may_start(rt, now):
                        continue
                    outcome = self._start_worker(spec)
                    if outcome.status == "STARTED":
                        rt.process = outcome.process
                        rt.last_start_ist = now
                        rt.consecutive_healthy_ticks = 0
                    elif outcome.status == "START_OWNERSHIP_HOLD":
                        self._record_ownership_hold(rt, now)
                    elif outcome.status in ("START_ENV_FAILURE", "START_SPAWN_FAILURE"):
                        self._record_failure(rt, now, -1)
                    # DRY_RUN: no-op
                else:
                    self._record_healthy(rt, now)

            elif (
                auth.position_management_allowed
                and rt.process is not None
                and rt.process.poll() is None
            ):
                # CLOSE_BUFFER — leave the worker running; it manages the existing position.
                pass

            else:
                if rt.process is not None and rt.process.poll() is None:
                    self._stop_worker(spec)
                    rt.last_stop_ist = now
                    rt.last_expected_stop_ist = now
                    if rt.last_analysis_date != day:
                        self._run_analysis_once(spec, day)
                        rt.last_analysis_date = day
                elif rt.process is not None and rt.process.poll() is not None:
                    if rt.last_analysis_date != day:
                        rc = rt.process.poll()
                        status = self._classify_exit(spec, rc, expected_alive=False)
                        rt.exit_history.append((day, rc, status))
                        self._log(f"[{spec.name}] auto-exit rc={rc} classified={status}")
                        self._run_analysis_once(spec, day)
                        rt.last_analysis_date = day

    def run_forever(self, poll_seconds=30.0):
        self._log(f"supervisor started (dry_run={self.dry_run})")
        try:
            while True:
                try:
                    self.tick()
                except Exception as exc:
                    self._log(f"tick error: {type(exc).__name__}: {exc}")
                time.sleep(poll_seconds)
        except KeyboardInterrupt:
            self._log("interrupt received; stopping workers")
            for spec in self._enabled_specs():
                self._stop_worker(spec)
            self._log("supervisor stopped")

    def _log(self, message):
        print(message)
        stamp = self._now_ist().strftime("%Y-%m-%d %H:%M:%S")
        log_path = self.log_dir / f"supervisor_{self._now_ist().date().isoformat()}.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {message}\n")


def _main():
    _acquire_lock()
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--poll-seconds", type=float, default=30.0)
    ap.add_argument("--python-exe", default=sys.executable)
    ap.add_argument("--repo-root",
                    default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--markets", default=None,
                    help="Comma-separated subset of {NIFTY,SENSEX,CRUDEOILM,GOLDM,NATGASMINI}; default all five.")
    args = ap.parse_args()
    markets = None
    if args.markets:
        _VALID = ("NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI")
        tokens = [t.strip().upper() for t in args.markets.split(",") if t.strip()]
        seen = set()
        deduped = []
        for t in tokens:
            if t not in seen:
                seen.add(t)
                deduped.append(t)
        bad = [t for t in deduped if t not in _VALID]
        if bad:
            print(f"--markets: unknown market(s): {', '.join(bad)}", file=sys.stderr)
            print(f"--markets: allowed values: {', '.join(_VALID)}", file=sys.stderr)
            return 2
        markets = tuple(deduped) if deduped else None
    sup = AutomatedPaperSupervisorV2(
        repo_root=args.repo_root,
        python_exe=args.python_exe,
        dry_run=args.dry_run,
        markets=markets,
    )
    if args.once:
        sup.tick()
        return 0
    sup.run_forever(poll_seconds=args.poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
