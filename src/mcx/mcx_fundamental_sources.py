"""Fundamental source adapters — Section 5.3, 5.4, 5.8, 5.12, 5.14, 5.19, 5.20, 5.21.
Fixture-default. Live disabled. No fabrication.
"""
import hashlib
import json
import os
from datetime import datetime, timezone


class SourceResult:
    def __init__(self, status, payload=None, reason=None, source=None,
                 source_url=None, raw_hash=None, fetched_at=None):
        self.status = status
        self.payload = payload
        self.reason = reason
        self.source = source
        self.source_url = source_url
        self.raw_hash = raw_hash
        self.fetched_at = fetched_at or datetime.now(timezone.utc).isoformat()

    def to_dict(self):
        return {"status": self.status, "payload": self.payload, "reason": self.reason,
                "source": self.source, "source_url": self.source_url,
                "raw_hash": self.raw_hash, "fetched_at": self.fetched_at}


def _load(path, source):
    if not os.path.exists(path):
        return SourceResult("SOURCE_UNAVAILABLE", reason=f"missing fixture {path}", source=source)
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        h = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return SourceResult("FIXTURE_LOADED", payload=payload, source=source,
                            source_url=path, raw_hash=h)
    except Exception as e:
        return SourceResult("PARSE_FAILED", reason=str(e)[:80], source=source)


# --- CRUDE ---

def fetch_eia_petroleum(reference_week, live=False):
    """Weekly Petroleum Status Report — crude/Cushing/gasoline/distillate/refinery/production."""
    if not live:
        return _load(f"data/fundamentals/fixtures/eia_wpsr_{reference_week}.json", "EIA")
    return SourceResult("SOURCE_UNAVAILABLE", reason="live EIA fetch not enabled",
                        source="EIA", source_url="https://www.eia.gov/petroleum/supply/weekly/")


def fetch_opec_decision(live=False):
    if not live:
        return _load("data/fundamentals/fixtures/opec_decisions_2026.json", "OPEC")
    return SourceResult("SOURCE_UNAVAILABLE", reason="live OPEC fetch not enabled",
                        source="OPEC", source_url="https://www.opec.org/")


def fetch_wti_brent_structure(live=False):
    if not live:
        return _load("data/fundamentals/fixtures/wti_brent_2026_09_11.json", "yfinance")
    return SourceResult("SOURCE_UNAVAILABLE", reason="live price fetch not enabled",
                        source="yfinance")


def fetch_china_crude_demand(live=False):
    return SourceResult("SOURCE_UNAVAILABLE", reason="China demand source not configured",
                        source="UNCONFIGURED")


# --- NATGAS ---

def fetch_eia_natgas_storage(reference_week, live=False):
    """Weekly Natural Gas Storage Report."""
    if not live:
        return _load(f"data/fundamentals/fixtures/eia_natgas_storage_{reference_week}.json", "EIA")
    return SourceResult("SOURCE_UNAVAILABLE", reason="live EIA fetch not enabled",
                        source="EIA", source_url="https://www.eia.gov/naturalgas/storage/")


def fetch_weather_hdd_cdd(live=False):
    """NOAA/NWS HDD/CDD forecast."""
    if not live:
        return _load("data/fundamentals/fixtures/noaa_hdd_cdd_2026_09_11.json", "NOAA")
    return SourceResult("SOURCE_UNAVAILABLE", reason="live weather fetch not enabled",
                        source="NOAA", source_url="https://www.cpc.ncep.noaa.gov/")


def fetch_lng_feedgas(live=False):
    if not live:
        return _load("data/fundamentals/fixtures/lng_feedgas_2026_09_11.json", "UNCONFIGURED")
    return SourceResult("SOURCE_UNAVAILABLE", reason="LNG source not configured",
                        source="UNCONFIGURED")


def fetch_natgas_production(live=False):
    if not live:
        return _load("data/fundamentals/fixtures/natgas_production_2026_09_11.json", "EIA")
    return SourceResult("SOURCE_UNAVAILABLE", reason="live production fetch not enabled",
                        source="EIA")


def fetch_pipeline_status(live=False):
    return SourceResult("SOURCE_UNAVAILABLE", reason="pipeline status source not configured",
                        source="UNCONFIGURED")


# --- GOLD ---

def fetch_real_yields(live=False):
    """US real (inflation-protected) yields — from FRED/Treasury."""
    if not live:
        return _load("data/fundamentals/fixtures/real_yields_2026_09_11.json", "Treasury")
    return SourceResult("SOURCE_UNAVAILABLE", reason="live real-yield fetch not enabled",
                        source="Treasury", source_url="https://home.treasury.gov/")


def fetch_dxy(live=False):
    if not live:
        return _load("data/fundamentals/fixtures/dxy_2026_09_11.json", "yfinance")
    return SourceResult("SOURCE_UNAVAILABLE", reason="live DXY fetch not enabled",
                        source="yfinance")


def fetch_usdinr(live=False):
    if not live:
        return _load("data/fundamentals/fixtures/usdinr_2026_09_11.json", "yfinance")
    return SourceResult("SOURCE_UNAVAILABLE", reason="live USDINR fetch not enabled",
                        source="yfinance")


def fetch_gold_etf_flows(live=False):
    if not live:
        return _load("data/fundamentals/fixtures/gold_etf_flows_2026_09.json", "UNCONFIGURED")
    return SourceResult("SOURCE_UNAVAILABLE", reason="ETF provider not configured",
                        source="UNCONFIGURED")


def fetch_central_bank_gold(live=False):
    if not live:
        return _load("data/fundamentals/fixtures/central_bank_gold_2026_09.json", "IMF")
    return SourceResult("SOURCE_UNAVAILABLE", reason="central-bank source not configured",
                        source="UNCONFIGURED")


def fetch_physical_gold_demand(live=False):
    return SourceResult("SOURCE_UNAVAILABLE", reason="physical demand source not configured",
                        source="UNCONFIGURED")


# SOURCE MATRIX — Section 5.3
SOURCE_MATRIX = {
    ("CRUDEOILM", "EIA_PETROLEUM"):   fetch_eia_petroleum,
    ("CRUDEOILM", "OPEC"):            fetch_opec_decision,
    ("CRUDEOILM", "WTI_BRENT"):       fetch_wti_brent_structure,
    ("CRUDEOILM", "CHINA_DEMAND"):    fetch_china_crude_demand,
    ("NATGASMINI", "EIA_STORAGE"):    fetch_eia_natgas_storage,
    ("NATGASMINI", "WEATHER"):        fetch_weather_hdd_cdd,
    ("NATGASMINI", "LNG"):            fetch_lng_feedgas,
    ("NATGASMINI", "PRODUCTION"):     fetch_natgas_production,
    ("NATGASMINI", "PIPELINE"):       fetch_pipeline_status,
    ("GOLDM", "REAL_YIELDS"):         fetch_real_yields,
    ("GOLDM", "DXY"):                 fetch_dxy,
    ("GOLDM", "USDINR"):              fetch_usdinr,
    ("GOLDM", "ETF_FLOWS"):           fetch_gold_etf_flows,
    ("GOLDM", "CENTRAL_BANKS"):       fetch_central_bank_gold,
    ("GOLDM", "PHYSICAL_DEMAND"):     fetch_physical_gold_demand,
}


if __name__ == "__main__":
    print("SOURCE_MATRIX entries:", len(SOURCE_MATRIX))
    print("Sample EIA:", fetch_eia_petroleum("2026-W36").status)
