import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "services" / "paper_orchestration"
FORBIDDEN_MODULE_FRAGMENTS = (
    "paper_trading_engine",
    "live_market_engine",
    "order_executor",
    "order_manager",
)
FORBIDDEN_CALL_FRAGMENTS = (
    "place_order",
    "submit_order",
    "send_order",
    "execute_live_order",
)

def python_files():
    return tuple(sorted(PACKAGE.rglob("*.py")))

def imported_module_names(tree):
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    return tuple(names)

def referenced_names(tree):
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Attribute):
            names.append(node.attr)
    return tuple(names)

def called_names(tree):
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.append(node.func.attr)
    return tuple(names)

def test_p9_package_has_no_forbidden_runtime_imports():
    violations = []
    for path in python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for imported in imported_module_names(tree):
            lowered = imported.lower()
            if any(fragment in lowered for fragment in FORBIDDEN_MODULE_FRAGMENTS):
                violations.append(f"{path.relative_to(ROOT)} imports {imported}")
    assert violations == []

def test_p9_package_has_no_forbidden_execution_references():
    violations = []
    for path in python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for name in referenced_names(tree):
            lowered = name.lower()
            if any(fragment in lowered for fragment in FORBIDDEN_MODULE_FRAGMENTS):
                violations.append(f"{path.relative_to(ROOT)} references {name}")
    assert violations == []

def test_p9_package_has_no_broker_order_calls():
    violations = []
    for path in python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for name in called_names(tree):
            lowered = name.lower()
            if any(fragment in lowered for fragment in FORBIDDEN_CALL_FRAGMENTS):
                violations.append(f"{path.relative_to(ROOT)} calls {name}")
    assert violations == []

def test_p9_runtime_boundary_is_continuous_paper_runtime_only():
    source = (PACKAGE / "continuous_runtime_adapter.py").read_text(encoding="utf-8")
    assert "from services.continuous_paper_trading_runtime import" in source
    assert "ContinuousPaperTradingRuntime" in source
