"""General/core dispatch must not branch on peer identity."""
import ast
from pathlib import Path

HUB_PATH = Path(__file__).parents[2] / "core" / "hub.py"
PEER_IDS = frozenset({"ag", "cc", "cx", "gc"})

# Exact dispatch/execution boundary. Config loaders, maps, health management,
# CLI parsing, defaults, and parity sets are intentionally outside this scope.
DISPATCH_FUNCTIONS = frozenset({
    "_select_ask_profile",
    "_strip_ansi",
    "_decode_output",
    "_classify_ask_failure",
    "_ask_health_precheck",
    "_record_ask_success",
    "_record_ask_failure",
    "_build_ask_query_with_context",
    "_ask_with_pty",
    "_append_ask_history",
    "_session_state_path",
    "_load_session_state",
    "_save_session_state",
    "_get_active_session",
    "_set_active_session",
    "_retire_session",
    "_clear_peer_sessions",
    "_compute_scope_key",
    "_classify_resume_failure",
    "_session_reuse_enabled",
    "_is_ephemeral_query_file",
    "_thin_forward_envelope",
    "action_ask",
    "action_ask_all",
    "action_ask_coordinator",
})


def _peer_literals(node: ast.AST) -> set[str]:
    return {
        item.value
        for item in ast.walk(node)
        if isinstance(item, ast.Constant)
        and isinstance(item.value, str)
        and item.value in PEER_IDS
    }


def _identity_violations(function: ast.FunctionDef, source: str) -> list[str]:
    violations: dict[tuple[int, int], str] = {}

    for node in ast.walk(function):
        candidates: list[ast.AST] = []

        # Catches assigned predicates such as:
        # is_ag = root_peer == "ag"
        if isinstance(node, (ast.Compare, ast.MatchValue)):
            candidates.append(node)

        # Also catches non-comparison predicates such as peer.startswith("ag").
        if isinstance(node, (ast.If, ast.IfExp, ast.While, ast.Assert)):
            candidates.append(node.test)
        elif isinstance(node, ast.comprehension):
            candidates.extend(node.ifs)
        elif isinstance(node, ast.match_case):
            candidates.append(node.pattern)
            if node.guard is not None:
                candidates.append(node.guard)

        for candidate in candidates:
            literals = _peer_literals(candidate)
            if not literals:
                continue
            key = (
                getattr(candidate, "lineno", function.lineno),
                getattr(candidate, "col_offset", 0),
            )
            expression = ast.get_source_segment(source, candidate) or ast.dump(candidate)
            violations[key] = (
                f"{function.name}:{key[0]}: peer identities "
                f"{sorted(literals)} in `{expression}`"
            )

    return list(violations.values())


def test_general_core_dispatch_has_no_peer_identity_branches():
    source = HUB_PATH.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }

    missing = DISPATCH_FUNCTIONS - functions.keys()
    assert not missing, f"Guard scope contains missing functions: {sorted(missing)}"

    violations = []
    for name in sorted(DISPATCH_FUNCTIONS):
        violations.extend(_identity_violations(functions[name], source))

    assert not violations, (
        "Peer-specific dispatch must use adapters/transports/capabilities:\n"
        + "\n".join(violations)
    )


def test_guard_allows_capability_and_adapter_dispatch():
    source = """
def action_ask(node, adapter):
    if node.get("requires_pty"):
        return adapter.parse_output("raw", node)
    if node.get("session_mode") == "reuse":
        return adapter.build_session_cmd(node, "query")
    return adapter.build_cmd(node, "query")
"""
    function = ast.parse(source).body[0]
    assert _identity_violations(function, source) == []
