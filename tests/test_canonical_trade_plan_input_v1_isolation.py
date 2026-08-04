import ast
from pathlib import Path
def test_contract_has_no_runtime_dependency_or_nondeterminism():
 p=Path(__file__).parents[1]/'services/contracts/canonical_trade_plan_input_v1.py'; t=ast.parse(p.read_text())
 names={a.name.split('.')[0] for n in ast.walk(t) if isinstance(n,ast.Import) for a in n.names}|{n.module.split('.')[0] for n in ast.walk(t) if isinstance(n,ast.ImportFrom) and n.module}
 assert not names & {'requests','httpx','pandas','numpy','streamlit','uuid','random','socket','execution','broker','dashboard','openai'}
