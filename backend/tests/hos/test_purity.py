"""AST check that services/hos imports no django, rest_framework, requests or datetime."""
import ast
from pathlib import Path

HOS_DIR = Path(__file__).resolve().parents[2] / "trips" / "services" / "hos"
FORBIDDEN = frozenset({"django", "rest_framework", "requests", "datetime"})


def _forbidden_imports(path):
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names = [node.module]
        else:
            continue
        for name in names:
            if name.split(".")[0] in FORBIDDEN:
                yield f"{path.relative_to(HOS_DIR.parent)}:{node.lineno} imports {name}"


def test_hos_package_is_pure():
    files = sorted(HOS_DIR.rglob("*.py"))
    assert files, f"no modules found under {HOS_DIR}"

    offenders = [line for path in files for line in _forbidden_imports(path)]

    assert not offenders, "impure imports in services/hos:\n" + "\n".join(offenders)
