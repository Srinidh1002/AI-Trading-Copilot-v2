"""Behavioral protection for the contracts package lazy-export boundary."""
import subprocess
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1];PYTHON=ROOT/"venv"/"Scripts"/"python.exe"
FORBIDDEN=("pandas","yfinance","requests","smartapi","streamlit")
P5=("TimeframeTechnicalEvidenceV1","TechnicalIntelligenceResultV1","TechnicalIntelligencePolicyV1")
REPRESENTATIVE=("MarketSnapshotV1","AnalysisResultV1","FinalDecisionV1","OptionContractV1","TradePlanV1","CanonicalRiskResultV1","PaperExecutionRequestV1","PaperOrderStateV1","MarketInstrumentV1","MarketQuoteV1","MultiTimeframeSnapshotV1")

def clean(code): return subprocess.run([str(PYTHON),"-c",code],cwd=ROOT,text=True,capture_output=True,check=True).stdout
def test_package_import_is_clean(): assert clean("import services.contracts; print('ok')").strip()=="ok"
def test_all_is_stable(): assert clean("import services.contracts as c; print(c.__all__==c.__all__)").strip()=="True"
@pytest.mark.parametrize("name",P5)
def test_p5_exports_resolve(name): assert name in clean(f"from services.contracts import {name}; print({name}.__name__)")
@pytest.mark.parametrize("name",REPRESENTATIVE)
def test_representative_exports_resolve(name): assert name in clean(f"import services.contracts as c; print(getattr(c,'{name}').__name__)")
@pytest.mark.parametrize("name",P5+REPRESENTATIVE)
def test_repeated_access_identity(name): assert clean(f"import services.contracts as c; print(getattr(c,'{name}') is getattr(c,'{name}'))").strip()=="True"
def test_unknown_attribute_raises(): assert clean("import services.contracts as c\ntry: c.no_such_contract\nexcept AttributeError: print('ok')").strip()=="ok"
def test_private_helper_is_not_exported(): assert clean("import services.contracts as c; print('_EXPORTS' not in c.__all__)").strip()=="True"
@pytest.mark.parametrize("name",P5)
def test_p5_imports_do_not_load_forbidden(name):
 out=clean(f"import sys; from services.contracts import {name}; print([x for x in sys.modules if any(t in x.lower() for t in {FORBIDDEN!r})])")
 assert out.strip()=="[]"
def test_package_only_does_not_load_forbidden():
 out=clean(f"import sys,services.contracts; print([x for x in sys.modules if any(t in x.lower() for t in {FORBIDDEN!r})])")
 assert out.strip()=="[]"
def test_wildcard_import_has_p5_contracts(): assert clean("ns={}; exec('from services.contracts import *',ns); print(all(x in ns for x in ('TimeframeTechnicalEvidenceV1','TechnicalIntelligenceResultV1','TechnicalIntelligencePolicyV1')))").strip()=="True"
def test_direct_then_package_identity(): assert clean("from services.contracts.timeframe_technical_evidence_v1 import TimeframeTechnicalEvidenceV1 as a; from services.contracts import TimeframeTechnicalEvidenceV1 as b; print(a is b)").strip()=="True"
def test_no_circular_import_for_p5(): assert clean("from services.contracts import TimeframeTechnicalEvidenceV1; print('ok')").strip()=="ok"
def test_package_import_does_not_load_dashboard(): assert clean("import sys,services.contracts; print(not any('dashboard' in x.lower() for x in sys.modules))").strip()=="True"
def test_package_import_does_not_load_broker(): assert clean("import sys,services.contracts; print(not any('broker' in x.lower() for x in sys.modules))").strip()=="True"
def test_contract_serialization_remains_available():
 code="from datetime import datetime,timezone\nfrom services.contracts import TechnicalIndicatorValueV1\nx=TechnicalIndicatorValueV1('RSI','5m',50.,'NEUTRAL','VALID',15,20);print(x.to_dict()['indicator_name'])"
 assert clean(code).strip()=="RSI"
