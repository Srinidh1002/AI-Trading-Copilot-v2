from pathlib import Path
def test_state_contract_has_no_runtime_or_calculation_dependencies():
 source=Path('services/contracts/paper_trade_lifecycle_state_v1.py').read_text().lower()
 assert not [word for word in ('broker','provider','order','portfolio','database','pandas','numpy','yfinance','random','uuid','datetime.now','date.today','p&l') if word in source]
def test_state_fresh_import():
 import subprocess,sys
 assert subprocess.run([sys.executable,'-c','from services.contracts import PaperTradeLifecycleStateV1,is_legal_paper_trade_lifecycle_transition'],check=False).returncode==0
