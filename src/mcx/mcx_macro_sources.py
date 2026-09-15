"""Source adapters — Section 4.4, 4.5, 4.24.
Real interfaces for BLS/BEA/Fed/MoSPI/RBI. Fixture loading for tests.
NO fabrication. Unavailable → SOURCE_UNAVAILABLE.
"""
import json
import os
from datetime import datetime, timezone

IST = timezone.utc  # placeholder; use ZoneInfo


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
        return {
            "status": self.status, "payload": self.payload, "reason": self.reason,
            "source": self.source, "source_url": self.source_url,
            "raw_hash": self.raw_hash, "fetched_at": self.fetched_at,
        }


def load_fixture(fixture_path):
    """Load a fixture file. Fixtures are always tagged FIXTURE in _fixture_note."""
    if not os.path.exists(fixture_path):
        return SourceResult("SOURCE_UNAVAILABLE", reason=f"missing fixture {fixture_path}",
                            source="FIXTURE")
    try:
        with open(fixture_path, encoding="utf-8") as f:
            payload = json.load(f)
        import hashlib
        h = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return SourceResult("FIXTURE_LOADED", payload=payload, source="FIXTURE",
                            source_url=fixture_path, raw_hash=h)
    except Exception as e:
        return SourceResult("SOURCE_UNAVAILABLE", reason=str(e)[:80], source="FIXTURE")


def fetch_bls_cpi(reference_period, live=False):
    """Real BLS CPI fetch — requires internet. Returns SOURCE_UNAVAILABLE offline."""
    if not live:
        # Fixture mode (default for tests)
        path = f"data/macro_events/fixtures/bls_cpi_{reference_period.replace('-', '_')}.json"
        return load_fixture(path)
    # Live path — would call https://api.bls.gov/publicAPI/v2/timeseries/data/
    return SourceResult("SOURCE_UNAVAILABLE", reason="live fetch not enabled in Section 4",
                        source="BLS",
                        source_url="https://api.bls.gov/publicAPI/v2/timeseries/data/")


def fetch_bls_ppi(reference_period, live=False):
    if not live:
        path = f"data/macro_events/fixtures/bls_ppi_{reference_period.replace('-', '_')}.json"
        return load_fixture(path)
    return SourceResult("SOURCE_UNAVAILABLE", reason="live fetch not enabled",
                        source="BLS", source_url="https://api.bls.gov/")


def fetch_bea_pce(reference_period, live=False):
    if not live:
        path = f"data/macro_events/fixtures/bea_pce_{reference_period.replace('-', '_')}.json"
        return load_fixture(path)
    return SourceResult("SOURCE_UNAVAILABLE", reason="live fetch not enabled",
                        source="BEA", source_url="https://apps.bea.gov/api/")


def fetch_fed_fomc_schedule(live=False):
    if not live:
        return load_fixture("data/macro_events/fixtures/fomc_2026_schedule.json")
    return SourceResult("SOURCE_UNAVAILABLE", reason="live fetch not enabled",
                        source="Fed", source_url="https://www.federalreserve.gov/")


def fetch_india_mospi_cpi(reference_period, live=False):
    return SourceResult("SOURCE_UNAVAILABLE",
                        reason="India CPI live fetch not configured in Section 4",
                        source="MoSPI")


def fetch_rbi_mpc_schedule(live=False):
    return SourceResult("SOURCE_UNAVAILABLE",
                        reason="RBI MPC live fetch not configured",
                        source="RBI")


# Adapter registry: (source_agency, event_type) -> callable
SOURCE_MATRIX = {
    ("BLS", "US_CPI"): fetch_bls_cpi,
    ("BLS", "US_CORE_CPI"): fetch_bls_cpi,
    ("BLS", "US_PPI"): fetch_bls_ppi,
    ("BEA", "US_PCE"): fetch_bea_pce,
    ("BEA", "US_CORE_PCE"): fetch_bea_pce,
    ("Federal Reserve", "US_FOMC_STATEMENT"): fetch_fed_fomc_schedule,
    ("Federal Reserve", "US_FOMC_RATE"): fetch_fed_fomc_schedule,
    ("MoSPI", "INDIA_CPI"): fetch_india_mospi_cpi,
    ("RBI", "INDIA_RBI_MPC"): fetch_rbi_mpc_schedule,
}


def source_for(event_type, source_agency):
    return SOURCE_MATRIX.get((source_agency, event_type))


if __name__ == "__main__":
    print(fetch_bls_cpi("2026-08").to_dict())
    print(fetch_bls_cpi("2026-07").to_dict()["status"])
