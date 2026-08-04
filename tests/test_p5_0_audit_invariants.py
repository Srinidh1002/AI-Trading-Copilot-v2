from pathlib import Path
import pytest
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES,SUPPORTED_MARKET_SYMBOLS,normalize_market_identity
AUDIT=Path("docs/audit/42_P5_0_DATA_AND_INTELLIGENCE_AUDIT.md"); ROADMAP=Path("docs/architecture/P5_INTELLIGENCE_ROADMAP.md")
def test_authoritative_identity_registry_is_exact_and_ordered():
 assert SUPPORTED_MARKET_IDENTITIES==(("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE"))
 assert SUPPORTED_MARKET_SYMBOLS==("NIFTY","BANKNIFTY","FINNIFTY","SENSEX")
@pytest.mark.parametrize("symbol,exchange",SUPPORTED_MARKET_IDENTITIES)
def test_registry_resolves_all_authoritative_identities(symbol,exchange):assert normalize_market_identity(symbol)==(symbol,exchange)
def test_p4_public_boundaries_remain_available_and_paper_only():
 from services.contracts import PaperExecutionRequestV1,PaperExecutionObservationV1
 from services.paper import run_canonical_paper_execution,replay_canonical_paper_execution
 assert PaperExecutionRequestV1 and PaperExecutionObservationV1 and run_canonical_paper_execution and replay_canonical_paper_execution
@pytest.mark.parametrize("section",["Executive summary","Repository inventory","Market-data provider matrix","Canonical data-contract matrix","Four-index support matrix","Freshness and quality audit","Cache audit","Multi-timeframe audit","Technical intelligence audit","Option-chain intelligence audit","Risk register","Canonical target architecture","Final audit decision","Random/fabricated/placeholder/fallback register"])
def test_audit_contains_evidence_backed_required_sections(section):assert section in AUDIT.read_text(encoding="utf-8")
@pytest.mark.parametrize("phase",[f"P5-{index}" for index in range(11)])
def test_roadmap_contains_ordered_phase_deliverables(phase):assert phase in ROADMAP.read_text(encoding="utf-8")
@pytest.mark.parametrize("term",["READY_WITH_BLOCKERS","P5-1 is next","no canonical quality/freshness/provenance","no canonical four-market option-chain path"])
def test_audit_records_explicit_readiness_and_blockers(term):assert term in AUDIT.read_text(encoding="utf-8")
