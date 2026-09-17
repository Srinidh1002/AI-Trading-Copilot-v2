import importlib.util
from datetime import datetime, timezone
from pathlib import Path


SCRIPT = Path("scripts/capture_india_vix_provider_contract.py")
SPEC = importlib.util.spec_from_file_location("vix_capture_cli", SCRIPT)
CLI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLI)


class Master:
    def __init__(self): self.calls = 0
    def fetch_instruments(self):
        self.calls += 1
        return [{"token": "99926017", "symbol": "India VIX", "name": "INDIA VIX", "exch_seg": "NSE", "instrumenttype": "AMXIDX"}]


class Client:
    def __init__(self): self.calls = 0
    def get_market_data(self, mode, exchange_tokens):
        self.calls += 1
        return {"status": True, "data": {"fetched": [{"ltp": 15, "previousClose": 14, "tradingSymbol": "India VIX", "symbolToken": "99926017", "exchange": "NSE", "exchFeedTime": "2026-08-02T10:00:00+00:00", "jwt": "hidden"}]}}


NOW = lambda: datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc)


def test_no_confirmation_means_no_provider_calls(capsys):
    master, client = Master(), Client()
    assert CLI.main([], master_factory=lambda: master, client_factory=lambda: client, clock=NOW) == 2
    assert master.calls == client.calls == 0
    assert "confirm-provider-read" in capsys.readouterr().err


def test_confirmed_manual_run_writes_safe_evidence(tmp_path, capsys):
    master, client, output = Master(), Client(), tmp_path / "vix.json"
    assert CLI.main(["--confirm-provider-read", "--output", str(output)], master_factory=lambda: master, client_factory=lambda: client, clock=NOW) == 1
    assert master.calls == client.calls == 1
    assert "jwt" not in output.read_text() and "DIAGNOSTIC ONLY" in capsys.readouterr().err


def test_provider_failure_is_safe_and_nonzero(tmp_path, capsys):
    class BrokenMaster:
        def fetch_instruments(self): raise RuntimeError("secret=not-visible")
    assert CLI.main(["--confirm-provider-read", "--output", str(tmp_path / "x.json")], master_factory=BrokenMaster, client_factory=Client, clock=NOW) == 1
    assert "secret" not in capsys.readouterr().err
