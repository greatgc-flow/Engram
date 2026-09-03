import ast
from pathlib import Path

_SYS_DIR = Path(__file__).resolve().parents[2]

# Forbidden paths that were removed in Increment A.
FORBIDDEN_MODULES = [
    "_sys.hooks",
    "hooks",
    "_sys.checks.check_contracts",
    "checks.check_contracts",
    "check_contracts"
]

def test_increment_a_deleted_paths_absent():
    """Ensure the files/directories removed in Increment A are actually absent."""
    hooks_dir = _SYS_DIR / "hooks"
    check_contracts = _SYS_DIR / "checks" / "check_contracts.py"
    
    assert not hooks_dir.exists(), f"{hooks_dir} should be deleted"
    assert not check_contracts.exists(), f"{check_contracts} should be deleted"
    
    cli_dir = _SYS_DIR / "cli"
    for wrapper in ["claude_entry.py", "codex_entry.py", "agy_entry.py", "console_runner.py", "peer_console.py"]:
        assert not (cli_dir / wrapper).exists(), f"Vendor wrapper {wrapper} should be deleted"

def test_no_forbidden_imports():
    """Ensure no remaining .py file under _sys/ imports forbidden modules."""
    violations = []
    
    for py_file in _SYS_DIR.rglob("*.py"):
        if py_file.name == "test_boundary_imports.py":
            continue
            
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
        except SyntaxError:
            continue
            
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in FORBIDDEN_MODULES:
                        if alias.name == forbidden or alias.name.startswith(forbidden + "."):
                            violations.append(f"{py_file.relative_to(_SYS_DIR)} imports {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for forbidden in FORBIDDEN_MODULES:
                        if node.module == forbidden or node.module.startswith(forbidden + "."):
                            violations.append(f"{py_file.relative_to(_SYS_DIR)} from-imports {node.module}")
            elif isinstance(node, ast.Call):
                # Best-effort check for importlib.import_module("...")
                if isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
                    if node.args and isinstance(node.args[0], ast.Constant):
                        mod_name = str(node.args[0].value)
                        for forbidden in FORBIDDEN_MODULES:
                            if mod_name == forbidden or mod_name.startswith(forbidden + "."):
                                violations.append(f"{py_file.relative_to(_SYS_DIR)} dynamically imports {mod_name}")
                                
    assert not violations, "Found forbidden imports:\n" + "\n".join(violations)
