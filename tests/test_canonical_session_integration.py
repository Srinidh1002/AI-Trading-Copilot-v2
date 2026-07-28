from datetime import datetime
from zoneinfo import ZoneInfo
from services.canonical.pipeline import CanonicalPipelineDependencies,run_canonical_pipeline
from services.contracts.market_snapshot_v1 import MarketSnapshotV1
def test_enabled_session_validation_blocks_pre_open_without_analysis():
    zone=ZoneInfo("Asia/Kolkata"); moment=datetime(2026,7,27,9,0,tzinfo=zone); snapshot=MarketSnapshotV1(symbol="NIFTY",exchange="NSE",instrument_type="INDEX",captured_at=moment,market_timestamp=moment,ltp=25000)
    decision=run_canonical_pipeline(snapshot,dependencies=CanonicalPipelineDependencies(session_validation_enabled=True,session_clock=lambda:moment))
    assert decision.action == "WAIT" and decision.authorization_status == "BLOCKED"
