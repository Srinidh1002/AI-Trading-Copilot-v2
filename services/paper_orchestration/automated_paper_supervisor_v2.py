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

# ruff: noqa: E402, I001, F401, E501, E702, UP045

from __future__ import annotations

# _REPO_ROOT_BOOTSTRAP_SUP - make `services` and `src` importable when
# this module is launched via `python -m services.paper_orchestration....`
# from the repo root without PYTHONPATH. Required so child authorities
# (mcx.mcx_calendar, mcx.mcx_contracts, etc.) resolve inside the
# supervisor process.
import sys as _sys
from pathlib import Path as _Path

_REPO_ROOT_BOOTSTRAP_SUP = _Path(__file__).resolve().parents[2]
for _p in (str(_REPO_ROOT_BOOTSTRAP_SUP), str(_REPO_ROOT_BOOTSTRAP_SUP / "src")):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)
del _p

import json  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from datetime import date, datetime, timedelta  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Optional  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

from services.paper_orchestration.supervisor_lock_v2 import acquire as _acquire_lock  # noqa: E402
from services.paper_orchestration.worker_lock_v2 import market_worker_available  # noqa: E402
from services.paper_orchestration.certification_halt_v2 import (  # noqa: E402
    all_complete as _cert_all_complete,
    market_state as _cert_market_state,
)
from services.paper_orchestration.worker_session_authority_v2 import (  # noqa: E402
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


from typing import NamedTuple  # noqa: E402


class StartOutcome(NamedTuple):
    status: (
        str  # STARTED | DRY_RUN | START_OWNERSHIP_HOLD | START_ENV_FAILURE | START_SPAWN_FAILURE
    )
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
    # Phase F15-R1: process-generation exit accounting.
    generation_id: int = 0
    consumed_exit_count: int = 0
    last_exit_rc: Optional[int] = None
    last_exit_status: Optional[str] = None
    last_exit_at: Optional[datetime] = None
    runtime_session_date: Optional[date] = None
    # Phase F15-R1: worker liveness (Phase 6).
    last_heartbeat_age_seconds: Optional[float] = None
    recovery_required: bool = False


class AutomatedPaperSupervisorV2:
    MAX_RESTART_FAILURES = 3
    RESTART_WINDOW = timedelta(minutes=15)
    MAX_RESTART_BACKOFF_SECONDS = 300
    HEALTHY_PERIOD = timedelta(seconds=180)
    STOP_ACK_TIMEOUT_SECONDS = 5.0
    OWNERSHIP_HOLD_BACKOFF_SECONDS = 300
    POSITION_MANAGEMENT_EXTEND_SECONDS = 900
    STOP_POST_VALIDATION_ENABLED = True
    # Phase F15-R1: legitimate worker close window (relative to close_hhmm).
    # 25 min before covers MCX forced exit at close-20min and index forced
    # exit at close-2min. 5 min after covers any residual slow close.
    CLOSE_GRACE_BEFORE_SECONDS = 1500
    CLOSE_GRACE_AFTER_SECONDS = 300
    # Phase F15-R1: worker liveness (Phase 6).
    HEARTBEAT_MAX_AGE_SECONDS = 300.0
    HUNG_STOP_GRACE_SECONDS = 5.0

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
        # F15-R2 M9c: clear any stale cooperative-stop artifacts from a
        # previous session before spawning. A leftover .request file
        # would make the fresh worker exit immediately on startup as a
        # cooperative FLAT_ACK_EXIT, which the supervisor then
        # misclassifies as UNEXPECTED_EXIT_ZERO and enters a restart
        # backoff loop. Runs even in dry-run so repeated preflights do
        # not leave the state inconsistent.
        _stops = self.log_dir / "stops"
        try:
            _stops.mkdir(parents=True, exist_ok=True)
            (_stops / f"{spec.name}.request").unlink(missing_ok=True)
            (_stops / f"{spec.name}.ack").unlink(missing_ok=True)
        except OSError:
            pass
        if self.dry_run:
            self._log(f"[DRY_RUN] would start {spec.name}: {spec.script} {spec.args}")
            return StartOutcome("DRY_RUN")
        if not market_worker_available(spec.name):
            self._log(f"[{spec.name}] WORKER_OWNERSHIP_HOLD")
            return StartOutcome("START_OWNERSHIP_HOLD", note="lock held by another process")

        try:
            from services.broker.fyers_auth_v2 import (  # noqa: E402
                FyersAuthError as _FyersAuthError,
                build_fyers_child_env_v2 as _build_env,
            )
        except Exception as exc:
            self._log(f"[{spec.name}] START_FAILED: FYERS_ENV_IMPORT: {type(exc).__name__}")
            return StartOutcome("START_ENV_FAILURE", note=f"import:{type(exc).__name__}")

        try:
            env = _build_env(str(self.repo_root / ".env"))
        except _FyersAuthError as exc:
            self._log(
                f"[{spec.name}] START_FAILED: FYERS_ENV: "
                f"{getattr(exc, 'reason_code', 'AUTH_MISSING')}"
            )
            return StartOutcome(
                "START_ENV_FAILURE", note=getattr(exc, "reason_code", "AUTH_MISSING")
            )
        except Exception as exc:
            self._log(f"[{spec.name}] START_FAILED: FYERS_ENV: {type(exc).__name__}")
            return StartOutcome("START_ENV_FAILURE", note=type(exc).__name__)

        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONUTF8"] = "1"
        env["PAPER_STOP_REQUEST_FILE"] = str(self.log_dir / "stops" / f"{spec.name}.request")
        env["PAPER_STOP_ACK_FILE"] = str(self.log_dir / "stops" / f"{spec.name}.ack")

        stdout_path = self.log_dir / f"{spec.name}_stdout.log"
        stderr_path = self.log_dir / f"{spec.name}_stderr.log"
        args = [self.python_exe, "-u", spec.script, *spec.args]
        out_f = open(stdout_path, "a", encoding="utf-8", errors="replace")
        err_f = open(stderr_path, "a", encoding="utf-8", errors="replace")
        try:
            proc = subprocess.Popen(
                args, cwd=str(self.repo_root), stdout=out_f, stderr=err_f, env=env
            )
        except Exception as exc:
            out_f.close()
            err_f.close()
            self._log(f"[{spec.name}] START_FAILED: {type(exc).__name__}: {exc}")
            return StartOutcome("START_SPAWN_FAILURE", note=type(exc).__name__)
        self._log(f"[{spec.name}] started pid={proc.pid}")
        # Phase 9.8 - stagger worker starts so the first expiryData
        # probe of each market does not collide with FYERS per-second
        # rate limits. 2s between starts, ~10s to launch all five.
        time.sleep(2.0)
        return StartOutcome("STARTED", process=proc)

    def _stop_worker(self, spec, grace_seconds=30.0):
        """Cooperative stop with ACK-aware management window.

        Writes a stop request, waits for either ACK or exit. When the
        worker ACKs POSITION_MANAGEMENT_ACTIVE, extends the wait window
        by POSITION_MANAGEMENT_EXTEND_SECONDS so the worker can finish
        managing the PAPER position to terminal. Forced terminate/kill
        only fires if the total window is exhausted.
        """
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

        # Phase 1: wait for ACK or quick exit
        ack_payload = None
        ack_deadline = time.monotonic() + self.STOP_ACK_TIMEOUT_SECONDS
        while time.monotonic() < ack_deadline:
            if proc.poll() is not None:
                break
            if acknowledgement.exists():
                try:
                    ack_payload = json.loads(acknowledgement.read_text(encoding="utf-8"))
                except Exception:
                    ack_payload = None
                if isinstance(ack_payload, dict):
                    self._log(
                        f"[{spec.name}] STOP_ACK status={ack_payload.get('status')} "
                        f"active={ack_payload.get('has_active_position')}"
                    )
                    break
            time.sleep(0.2)

        # Phase 2: choose wait window based on ACK status
        total_window = grace_seconds
        status = (ack_payload or {}).get("status") if ack_payload else None
        if status == "POSITION_MANAGEMENT_ACTIVE":
            total_window += self.POSITION_MANAGEMENT_EXTEND_SECONDS
            self._log(f"[{spec.name}] POSITION_MANAGEMENT_WINDOW_EXTENDED total={total_window}s")
        elif status in ("FLAT_SAFE_TO_EXIT", "TERMINAL_RECONCILED"):
            self._log(f"[{spec.name}] SAFE_TO_EXIT status={status}")
        elif status == "STATE_HOLD":
            self._log(f"[{spec.name}] STATE_HOLD reported by worker")
        elif ack_payload is None:
            self._log(f"[{spec.name}] STOP_ACK_MISSING after {self.STOP_ACK_TIMEOUT_SECONDS}s")

        # Phase 3: wait for exit up to total window
        deadline = time.monotonic() + total_window
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            time.sleep(0.5)

        forced = False
        if proc.poll() is None:
            self._log(
                f"[{spec.name}] ABNORMAL_SHUTDOWN_TIMEOUT pid={proc.pid} "
                f"status={status} ack={ack_payload is not None}"
            )
            forced = True
            try:
                proc.terminate()
            except Exception as exc:
                self._log(f"[{spec.name}] forced terminate failed: {exc}")
        if proc.poll() is None:
            try:
                proc.kill()
            except Exception as exc:
                self._log(f"[{spec.name}] forced kill failed: {exc}")
        if forced:
            self._log(f"[{spec.name}] ABNORMAL_FORCED_STOP rc={proc.poll()}")

        # Phase 4: post-stop state validation
        if self.STOP_POST_VALIDATION_ENABLED and not self.dry_run:
            self._validate_post_stop_state(spec, forced=forced)

        request.unlink(missing_ok=True)
        acknowledgement.unlink(missing_ok=True)
        self._log(f"[{spec.name}] stopped rc={proc.poll()} ack={ack_payload is not None}")

    def _validate_post_stop_state(self, spec, *, forced):
        """Read-only state validation after a worker has stopped.

        Uses the shared state authority validator. If the state is not
        valid, logs STOP_STATE_HOLD and suppresses subsequent analysis
        for this market until the state is corrected manually.
        """
        try:
            from services.paper_orchestration.state_authority_readonly_v2 import (  # noqa: E402
                validate_market,
            )

            v = validate_market(self.repo_root, spec.name)
        except Exception as exc:
            self._log(f"[{spec.name}] STOP_STATE_VALIDATION_RAISED {type(exc).__name__}")
            return
        if v.ok:
            self._log(f"[{spec.name}] STOP_STATE_VALIDATED reason={v.reason}")
            if v.note:
                self._log(f"[{spec.name}] STOP_STATE_NOTE {v.note}")
        else:
            self._log(
                f"[{spec.name}] STOP_STATE_HOLD reason={v.reason} note={v.note} forced={forced}"
            )

    def _market_has_persisted_position(self, spec):
        """True when the market's persisted state shows an active position.

        Index state uses a list key `active_trades`; MCX state uses a
        single dict key `active_position`. Both shapes are handled here
        so the recovery path works for every market. F15-R2 M9: index
        parity added after a canary incident in which the liveness
        watchdog did not recognise a live index position as active.
        """
        if spec.name in ("NIFTY", "SENSEX"):
            path = (
                self.repo_root
                / "data"
                / "paper_trades"
                / f"{spec.name.lower()}_experimental.json"
            )
            try:
                st = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return False
            if not isinstance(st, dict):
                return False
            active = st.get("active_trades")
            if isinstance(active, list) and active:
                return True
            ap = st.get("active_position")
            return isinstance(ap, dict) and bool(ap.get("trade_id"))
        if spec.name in ("CRUDEOILM", "GOLDM", "NATGASMINI"):
            path = (
                self.repo_root
                / "data"
                / "paper_trades"
                / f"mcx_{spec.name.lower()}_experimental.json"
            )
            try:
                st = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return False
            if not isinstance(st, dict):
                return False
            ap = st.get("active_position")
            return isinstance(ap, dict) and bool(ap.get("trade_id"))
        return False

    def _check_worker_liveness(self, rt, spec, now):
        """Recycle or flag a stale worker. Returns True when the
        tick's normal processing for this spec should be skipped.
        """
        from services.paper_orchestration.worker_liveness_v2 import (  # noqa: E402
            classify as _classify_liveness,
        )

        # F15-R2 M9 fix: the liveness watchdog was designed for the
        # MCX pipeline hang (NATGAS stuck ~4.5h in a synchronous
        # provider call). Index workers (NIFTY/SENSEX) emit heartbeats
        # only at SESSION start and SLEEP end, NOT during active
        # trade management. A stale-looking index heartbeat while a
        # position is open is EXPECTED and must not trigger a recycle
        # that would abandon the position. Skip the liveness check
        # for index markets; their session-close authority already
        # governs lifecycle at 15:28.
        if spec.name in ("NIFTY", "SENSEX"):
            return False

        cls, hb, age = _classify_liveness(
            spec.name, now, max_age_seconds=self.HEARTBEAT_MAX_AGE_SECONDS
        )
        rt.last_heartbeat_age_seconds = age
        # F15-R2 M9c: ignore heartbeats written before the current
        # worker started. A fresh spawn has not had time to write its
        # first heartbeat yet; the previous session's file may still
        # be on disk and would otherwise be classified HEARTBEAT_STALE.
        if (
            cls == "HEARTBEAT_STALE"
            and rt.last_start_ist is not None
            and isinstance(hb, dict)
        ):
            try:
                from datetime import datetime as _dt_hb
                _hb_ts = _dt_hb.fromisoformat(str(hb.get("timestamp") or ""))
                if _hb_ts.tzinfo is None:
                    _hb_ts = _hb_ts.replace(tzinfo=rt.last_start_ist.tzinfo)
                if _hb_ts < rt.last_start_ist:
                    cls = "NO_HEARTBEAT"
            except (ValueError, TypeError):
                pass
        if cls != "HEARTBEAT_STALE":
            # NO_HEARTBEAT is treated as 'not yet emitting' — normal
            # during startup ticks before the first stage marker.
            return False

        stage = (hb or {}).get("stage", "?")
        has_pos = self._market_has_persisted_position(spec)
        tid = ((hb or {}).get("trade_id")) or None
        if has_pos:
            self._log(
                f"[{spec.name}] ACTIVE_POSITION_RECOVERY_REQUIRED "
                f"stage={stage} age={age:.1f}s trade_id={tid}"
            )
            rt.recovery_required = True
        else:
            self._log(
                f"[{spec.name}] HUNG_WORKER_DETECTED "
                f"stage={stage} age={age:.1f}s"
            )
            rt.recovery_required = False

        self._stop_worker(spec, grace_seconds=self.HUNG_STOP_GRACE_SECONDS)
        rt.last_stop_ist = now
        rt.last_expected_stop_ist = now
        return True

    def _classify_exit(self, spec, rc, *, expected_alive=True):
        if rc is None:
            return "STILL_RUNNING"
        if rc == 0:
            return "UNEXPECTED_EXIT_ZERO" if expected_alive else "CLEAN_SESSION_END"
        if rc in (1, 2):
            return "STARTUP_FAILURE"
        return "RUNTIME_FAILURE"

    def _in_close_grace(self, spec, now):
        """True when `now` falls inside the approved worker close window."""
        try:
            close_dt = datetime(
                now.year,
                now.month,
                now.day,
                spec.close_hhmm[0],
                spec.close_hhmm[1],
                tzinfo=IST,
            )
        except Exception:
            return False
        delta = (close_dt - now).total_seconds()
        return (
            -self.CLOSE_GRACE_AFTER_SECONDS
            <= delta
            <= self.CLOSE_GRACE_BEFORE_SECONDS
        )

    def _consume_exit(self, rt, spec, now, day, *, expected_alive):
        """Consume one process exit exactly once.

        Returns the classification string, or None if there was
        nothing to consume. On return, rt.process is None regardless
        of classification, so the same Popen cannot be re-consumed on
        a later tick.
        """
        proc = rt.process
        if proc is None:
            return None
        rc = proc.poll()
        if rc is None:
            return None
        # Close-window override: a legitimate voluntary end-of-session
        # exit inside the grace window is CLEAN_SESSION_END even if the
        # supervisor would otherwise have expected the worker alive.
        if rc == 0 and self._in_close_grace(spec, now):
            status = "CLEAN_SESSION_END"
        else:
            status = self._classify_exit(
                spec, rc, expected_alive=expected_alive
            )
        rt.exit_history.append((day, rc, status))
        rt.last_exit_rc = rc
        rt.last_exit_status = status
        rt.last_exit_at = now
        rt.consumed_exit_count += 1
        # Phase F15-R1: during a liveness recovery cycle, exit is
        # expected and must not be counted as a restart failure.
        in_recovery = bool(getattr(rt, "recovery_required", False))
        if status in (
            "STARTUP_FAILURE",
            "RUNTIME_FAILURE",
            "UNEXPECTED_EXIT_ZERO",
        ) and not in_recovery:
            self._record_failure(rt, now, rc)
        self._log(
            f"[{spec.name}] WORKER_EXIT rc={rc} classified={status} "
            f"generation={rt.generation_id} consumed={rt.consumed_exit_count}"
        )
        rt.process = None
        return status

    def _reset_session_authority_if_needed(self, rt, day):
        """When the authoritative trading day advances, reset per-day
        restart authority. Preserves exit_history for audit.
        """
        prev = getattr(rt, "runtime_session_date", None)
        if prev == day:
            return
        rt.runtime_session_date = day
        if rt.circuit_open:
            self._log(
                f"[{rt.spec.name}] SESSION_RESET day={day} "
                f"prior_circuit_open=True cleared"
            )
        rt.restart_failures = []
        rt.next_restart_ist = None
        rt.circuit_open = False
        rt.consecutive_healthy_ticks = 0

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
        # Phase F15-R1: during an active-position recovery cycle, the
        # circuit must not block restart — the position needs its
        # managing worker back online.
        if getattr(rt, "recovery_required", False):
            return True
        if rt.circuit_open:
            return False
        if rt.next_restart_ist is not None and now < rt.next_restart_ist:
            return False
        return True

    def _run_analysis_once(self, spec, day):
        """Run the daily analysis once. Returns ANALYSIS_SUCCESS,
        ANALYSIS_FAILURE, or ANALYSIS_DRY_RUN. Does not mutate runtime state.
        """
        if self.dry_run:
            self._log(f"[DRY_RUN] would run analysis for {spec.name} {day}")
            return "ANALYSIS_DRY_RUN"
        try:
            from services.paper_orchestration.campaign_analysis_v2 import (  # noqa: E402
                analyze_market_day,
                write_daily_report,
            )

            summary = analyze_market_day(market=spec.name, day=day, repo_root=str(self.repo_root))
            path = write_daily_report(summary, repo_root=str(self.repo_root))
            self._log(f"[{spec.name}] daily report -> {path}")
            return "ANALYSIS_SUCCESS"
        except Exception as exc:
            self._log(f"[{spec.name}] analysis failed: {type(exc).__name__}: {exc}")
            return "ANALYSIS_FAILURE"

    def _run_analysis_and_record(self, rt, spec, day):
        """Run the daily analysis and persist rt.last_analysis_date only on
        success. On failure the next tick retries because last_analysis_date
        is not advanced.
        """
        if rt.last_analysis_date == day:
            return "ALREADY_DONE"
        result = self._run_analysis_once(spec, day)
        if result == "ANALYSIS_SUCCESS":
            rt.last_analysis_date = day
            self._log(f"[{spec.name}] ANALYSIS_RECORDED day={day}")
        elif result == "ANALYSIS_FAILURE":
            self._log(f"[{spec.name}] ANALYSIS_RETRY_PENDING day={day}")
        # DRY_RUN does not advance last_analysis_date; the operator
        # controls when the real run happens.
        return result

    def tick(self):
        if _cert_all_complete():
            print("CERTIFICATION_COMPLETE: all markets at 100; supervisor idle")
            return
        now = self._now_ist()
        day = now.date()
        self._log(f"tick at {now.isoformat()}")
        for spec in self._enabled_specs():
            rt = self.workers[spec.name]

            # Phase F15-R1: per-day session authority reset.
            self._reset_session_authority_if_needed(rt, day)

            # Wave 0 - certification authority gate
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
                    self._log(
                        f"[{spec.name}] CERT_COMPLETE counter={ms.counter}; worker stopped"
                    )
                self._run_analysis_and_record(rt, spec, day)
                continue

            # Wave 1 - calendar authority
            auth = _session_authority_for(spec, now)
            if not auth.calendar_authoritative:
                self._log(
                    f"[{spec.name}] CALENDAR_HOLD status={auth.status} note={auth.note}"
                )
                continue

            if auth.session_open:
                # Consume any pending exit exactly once.
                if rt.process is not None:
                    rc = rt.process.poll()
                    if rc is None:
                        # Worker alive. Phase F15-R1: liveness check
                        # before declaring healthy.
                        if self._check_worker_liveness(rt, spec, now):
                            continue
                        self._record_healthy(rt, now)
                        continue
                    status = self._consume_exit(
                        rt, spec, now, day, expected_alive=True
                    )
                    if status == "CLEAN_SESSION_END":
                        # Legitimate close-window exit: no restart, run analysis.
                        self._run_analysis_and_record(rt, spec, day)
                        continue
                # rt.process is None. Respect backoff and try to start.
                if not self._may_start(rt, now):
                    continue
                outcome = self._start_worker(spec)
                if outcome.status == "STARTED":
                    rt.process = outcome.process
                    rt.last_start_ist = now
                    rt.generation_id += 1
                    rt.consecutive_healthy_ticks = 0
                    if getattr(rt, "recovery_required", False):
                        if not self._market_has_persisted_position(spec):
                            self._log(
                                f"[{spec.name}] RECOVERY_COMPLETE "
                                f"position_terminal_cleared flag"
                            )
                            rt.recovery_required = False
                elif outcome.status == "START_OWNERSHIP_HOLD":
                    self._record_ownership_hold(rt, now)
                elif outcome.status in (
                    "START_ENV_FAILURE",
                    "START_SPAWN_FAILURE",
                ):
                    self._record_failure(rt, now, -1)

            elif (
                auth.position_management_allowed
                and rt.process is not None
                and rt.process.poll() is None
            ):
                # CLOSE_BUFFER - leave the worker running; it manages the
                # existing position and will exit voluntarily.
                pass

            else:
                # Session not open.
                if rt.process is not None:
                    rc = rt.process.poll()
                    if rc is None:
                        # Live worker in closed session: stop it. Fall
                        # through to attempt analysis in the same tick;
                        # analysis reads ledgers, not the worker process,
                        # and will retry on later ticks if not yet ready.
                        self._stop_worker(spec)
                        rt.last_stop_ist = now
                        rt.last_expected_stop_ist = now
                    else:
                        self._consume_exit(
                            rt, spec, now, day, expected_alive=False
                        )
                self._run_analysis_and_record(rt, spec, day)

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
    import argparse  # noqa: E402

    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--poll-seconds", type=float, default=30.0)
    ap.add_argument("--python-exe", default=sys.executable)
    ap.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument(
        "--markets",
        default=None,
        help="Comma-separated subset of {NIFTY,SENSEX,CRUDEOILM,GOLDM,NATGASMINI}; default all five.",
    )
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
