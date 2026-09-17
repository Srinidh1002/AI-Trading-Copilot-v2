import ast
from pathlib import Path
def test_fixture_sources_have_no_clock_uuid_or_random_calls():
 root=Path(__file__).resolve().parent/'fixtures'/'p5_12'
 banned={'now','utcnow','today','uuid4','random','choice'}
 for path in root.glob('*.py'):
  calls={node.func.attr for node in ast.walk(ast.parse(path.read_text())) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)}
  assert not calls & banned
