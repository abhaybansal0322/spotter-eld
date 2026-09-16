"""AST check that only the three network modules import an HTTP client."""
import ast
from pathlib import Path

TRIPS_DIR = Path(__file__).resolve().parents[2] / "trips"
NETWORK_MODULES = frozenset({"services/http.py", "services/geocode.py", "services/routing.py"})
HTTP_CLIENTS = frozenset({"requests", "urllib3", "httpx", "urllib", "http"})


def _http_client_imports(path):
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names = [node.module]
        else:
            continue
        for name in names:
            if name.split(".")[0] in HTTP_CLIENTS:
                yield f"{path.relative_to(TRIPS_DIR)}:{node.lineno} imports {name}"


def test_only_network_modules_import_an_http_client():
    files = sorted(TRIPS_DIR.rglob("*.py"))
    assert any(path.relative_to(TRIPS_DIR).as_posix() == "services/http.py" for path in files)

    offenders = [
        line
        for path in files
        if path.relative_to(TRIPS_DIR).as_posix() not in NETWORK_MODULES
        for line in _http_client_imports(path)
    ]

    assert not offenders, "HTTP client imported outside the network layer:\n" + "\n".join(offenders)
