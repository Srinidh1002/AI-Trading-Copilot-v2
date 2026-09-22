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
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

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


@dataclass
class WorkerRuntimeV2:
    spec: WorkerSpecV2
    process: Optional[subprocess.Popen] = None
    last_start_ist: Optional[datetime] = None
    last_stop_ist: Optional[datetime] = None
    last_analysis_date: Optional[date] = None
    exit_history: list = field(default_factory=list)


class AutomatedPaperSupervisorV2:
    def __init__(
        self,
        *,
        repo_root: str,
        python_exe: str,
        dry_run: bool = False,
        log_dir: str = "logs/supervisor",
        clock=None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.python_exe = python_exe
        self.dry_run = dry_run
        self.log_dir = self.repo_root / log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.clock = clock or (lambda: datetime.now(IST))
        self.workers = {spec.name: WorkerRuntimeV2(spec=spec) for spec in WORKERS_V2}

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
        if self.dry_run:
            self._log(f"[DRY_RUN] would start {spec.name}: {spec.script} {spec.args}")
            return None
        stdout_path = self.log_dir / f"{spec.name}_stdout.log"
        stderr_path = self.log_dir / f"{spec.name}_stderr.log"
        args = [self.python_exe, "-u", spec.script, *spec.args]
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONUTF8"] = "1"
        out_f = open(stdout_path, "a", encoding="utf-8", errors="replace")
        err_f = open(stderr_path, "a", encoding="utf-8", errors="replace")
        try:
            proc = subprocess.Popen(args, cwd=str(self.repo_root),
                                    stdout=out_f, stderr=err_f, env=env)
        except Exception as exc:
            out_f.close(); err_f.close()
            self._log(f"[{spec.name}] START_FAILED: {type(exc).__name__}: {exc}")
            return None
        self._log(f"[{spec.name}] started pid={proc.pid}")
        return proc

    def _stop_worker(self, spec, grace_seconds=30.0):
        rt = self.workers[spec.name]
        proc = rt.process
        if proc is None or proc.poll() is not None:
            return
        if self.dry_run:
            self._log(f"[DRY_RUN] would stop {spec.name} pid={proc.pid}")
            return
        self._log(f"[{spec.name}] sending terminate pid={proc.pid}")
        try:
            proc.terminate()
        except Exception as exc:
            self._log(f"[{spec.name}] terminate failed: {exc}")
        deadline = time.monotonic() + grace_seconds
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            time.sleep(0.5)
        if proc.poll() is None:
            self._log(f"[{spec.name}] did not stop; killing pid={proc.pid}")
            try:
                proc.kill()
            except Exception as exc:
                self._log(f"[{spec.name}] kill failed: {exc}")
        self._log(f"[{spec.name}] stopped rc={proc.poll()}")

    def _classify_exit(self, spec, rc):
        if rc is None:
            return "STILL_RUNNING"
        if rc == 0:
            return "NORMAL_EXIT"
        if rc in (1, 2):
            return "FAILED_STARTUP"
        return f"NONZERO_{rc}"

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
        now = self._now_ist()
        day = now.date()
        self._log(f"tick at {now.isoformat()}")
        for spec in WORKERS_V2:
            rt = self.workers[spec.name]
            if self._is_weekend(day):
                if rt.process is not None and rt.process.poll() is None:
                    self._stop_worker(spec)
                continue
            session_active = self._is_session_active(spec, now)
            session_done = self._is_session_done_today(spec, now)

            if session_active:
                if rt.process is None or rt.process.poll() is not None:
                    if rt.process is not None:
                        rc = rt.process.poll()
                        status = self._classify_exit(spec, rc)
                        rt.exit_history.append((day, rc, status))
                        self._log(f"[{spec.name}] prior exit rc={rc} classified={status}")
                    proc = self._start_worker(spec)
                    if proc is not None:
                        rt.process = proc
                        rt.last_start_ist = now

            elif session_done and rt.process is not None and rt.process.poll() is None:
                self._stop_worker(spec)
                rt.last_stop_ist = now
                if rt.last_analysis_date != day:
                    self._run_analysis_once(spec, day)
                    rt.last_analysis_date = day

            else:
                if (session_done
                        and rt.process is not None
                        and rt.process.poll() is not None
                        and rt.last_analysis_date != day):
                    rc = rt.process.poll()
                    status = self._classify_exit(spec, rc)
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
            for spec in WORKERS_V2:
                self._stop_worker(spec)
            self._log("supervisor stopped")

    def _log(self, message):
        print(message)
        stamp = self._now_ist().strftime("%Y-%m-%d %H:%M:%S")
        log_path = self.log_dir / f"supervisor_{self._now_ist().date().isoformat()}.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {message}\n")


def _main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--poll-seconds", type=float, default=30.0)
    ap.add_argument("--python-exe", default=sys.executable)
    ap.add_argument("--repo-root",
                    default=str(Path(__file__).resolve().parents[2]))
    args = ap.parse_args()
    sup = AutomatedPaperSupervisorV2(
        repo_root=args.repo_root,
        python_exe=args.python_exe,
        dry_run=args.dry_run,
    )
    if args.once:
        sup.tick()
        return 0
    sup.run_forever(poll_seconds=args.poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
