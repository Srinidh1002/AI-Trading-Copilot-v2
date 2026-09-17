import ast
from pathlib import Path
def test_target_contract_is_standalone():
    tree=ast.parse((Path(__file__).parents[1]/'services/contracts/trade_plan_target_v1.py').read_text())
    names={a.name.split('.')[0] for node in ast.walk(tree) if isinstance(node,ast.Import) for a in node.names}
    assert not names & {'requests','httpx','pandas','numpy','streamlit','uuid','random','socket','execution','broker','dashboard','openai'}
