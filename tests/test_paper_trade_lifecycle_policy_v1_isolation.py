import ast
from pathlib import Path
def test_policy_contract_has_no_runtime_dependencies():
 source=Path('services/contracts/paper_trade_lifecycle_policy_v1.py').read_text();tree=ast.parse(source)
 forbidden=('broker','provider','order','execution','portfolio','database','pandas','numpy','yfinance','random','uuid')
 imports=[]
 for node in ast.walk(tree):
  if isinstance(node,ast.Import): imports.extend(alias.name.lower() for alias in node.names)
  if isinstance(node,ast.ImportFrom): imports.append((node.module or '').lower())
 assert not [name for name in imports for word in forbidden if word in name]
def test_policy_fresh_import():
 import subprocess,sys
 assert subprocess.run([sys.executable,'-c','from services.contracts import PaperTradeLifecyclePolicyV1'],check=False).returncode==0
