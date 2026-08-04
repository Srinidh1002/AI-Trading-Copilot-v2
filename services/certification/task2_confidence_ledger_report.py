"""Provider-free Task 2B shadow-ledger certification projection."""
import json
from dataclasses import dataclass
from services.contracts.market_analysis_confidence_ledger_v1 import MarketAnalysisConfidenceLedgerV1

@dataclass(frozen=True, slots=True)
class Task2ConfidenceLedgerReportV1:
    ledger: MarketAnalysisConfidenceLedgerV1
    legacy_confidence: float
    legacy_score: float
    schema_version: str = "task2_confidence_ledger_report.v1"
    def __post_init__(self):
        if type(self.ledger) is not MarketAnalysisConfidenceLedgerV1 or not 0 <= self.legacy_confidence <= 100 or not 0 <= self.legacy_score <= 100: raise ValueError("report")
    def to_dict(self):
        value=self.ledger.to_dict(); value.update({"schema_version":self.schema_version,"legacy_confidence":self.legacy_confidence,"legacy_score":self.legacy_score,"confidence_delta":self.ledger.final_confidence-self.legacy_confidence,"score_delta":self.ledger.final_score-self.legacy_score,"equivalence_status":"EQUIVALENT" if (self.ledger.final_confidence,self.ledger.final_score)==(self.legacy_confidence,self.legacy_score) else "DELTA_REPORTED"})
        return value
    def to_json(self): return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)

def build_task2_confidence_ledger_report(*, ledger: MarketAnalysisConfidenceLedgerV1, legacy_confidence: float, legacy_score: float) -> Task2ConfidenceLedgerReportV1:
    return Task2ConfidenceLedgerReportV1(ledger,legacy_confidence,legacy_score)
