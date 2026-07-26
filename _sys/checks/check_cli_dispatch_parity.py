"""Verify hub CLI action choices and real dispatch branches are in parity.

This checker compares literal argparse choices with control-flow or invoked
dict-dispatch keys. It deliberately does not derive handler names from
hyphenated action strings because the live hub does not follow one reliable
name-conversion convention.
"""
from __future__ import annotations

import argparse
import ast
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

_CHECKS_DIR = Path(__file__).resolve().parent
_SYS_DIR = _CHECKS_DIR.parent
_ROOT = _SYS_DIR.parent
_HUB_REL = "_sys/core/hub.py"

sys.path.insert(0, str(_CHECKS_DIR))
from _common import IndexView, WorktreeView  # noqa: E402


class FileView(Protocol):
    def exists(self, rel_path: str) -> bool: ...
    def read_text(self, rel_path: str) -> str: ...


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    line: int
    message: str

    def render(self) -> str:
        return f"[{self.code}] {self.path}:{self.line} - {self.message}"


def _main_function(tree: ast.Module) -> ast.FunctionDef | ast.AsyncFunctionDef:
    mains = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "main"
    ]
    if len(mains) != 1:
        raise ValueError(f"expected exactly one top-level main(), found {len(mains)}")
    return mains[0]


def _literal_strings(node: ast.AST) -> set[str] | None:
    if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return None
    values: set[str] = set()
    for item in node.elts:
        if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
            return None
        values.add(item.value)
    return values


def extract_action_choices(
    main_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[set[str], int]:
    declarations: list[tuple[set[str], int]] = []
    for node in ast.walk(main_node):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_argument"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "action"
        ):
            continue
        choices_node = next(
            (keyword.value for keyword in node.keywords if keyword.arg == "choices"),
            None,
        )
        if choices_node is None:
            raise ValueError("the 'action' argument has no choices declaration")
        choices = _literal_strings(choices_node)
        if choices is None:
            raise ValueError("action choices must be a literal string list/tuple/set")
        declarations.append((choices, int(node.lineno)))
    if len(declarations) != 1:
        raise ValueError(
            f"expected exactly one argparse 'action' declaration, found {len(declarations)}"
        )
    return declarations[0]


def _is_args_action(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "action"
        and isinstance(node.value, ast.Name)
        and node.value.id == "args"
    )


def _assigned_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for item in node.elts:
            names.update(_assigned_names(item))
        return names
    return set()


def _action_aliases(
    main_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    aliases: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in ast.walk(main_node):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if not (
                _is_args_action(value)
                or isinstance(value, ast.Name)
                and value.id in aliases
            ):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for name in _assigned_names(target):
                    if name not in aliases:
                        aliases.add(name)
                        changed = True
    return aliases


def _is_action_expr(node: ast.AST, aliases: set[str]) -> bool:
    return _is_args_action(node) or (
        isinstance(node, ast.Name) and node.id in aliases
    )


def _equality_dispatch_values(
    test: ast.AST,
    aliases: set[str],
) -> set[str]:
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return set()
    operator = test.ops[0]
    if len(test.comparators) != 1:
        return set()
    left = test.left
    right = test.comparators[0]
    if isinstance(operator, ast.Eq):
        if _is_action_expr(left, aliases) and isinstance(right, ast.Constant):
            return {right.value} if isinstance(right.value, str) else set()
        if _is_action_expr(right, aliases) and isinstance(left, ast.Constant):
            return {left.value} if isinstance(left.value, str) else set()
    if isinstance(operator, ast.In) and _is_action_expr(left, aliases):
        return _literal_strings(right) or set()
    return set()


def _dict_dispatch_keys(
    main_node: ast.FunctionDef | ast.AsyncFunctionDef,
    aliases: set[str],
) -> set[str]:
    registries: dict[str, set[str]] = {}
    for node in ast.walk(main_node):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not isinstance(value, ast.Dict):
            continue
        keys: set[str] = set()
        valid = True
        for key in value.keys:
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                valid = False
                break
            keys.add(key.value)
        if not valid:
            continue
        for target in targets:
            for name in _assigned_names(target):
                registries[name] = keys

    invoked: set[str] = set()
    derived_handlers: dict[str, str] = {}
    for node in ast.walk(main_node):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            registry_name: str | None = None
            key_expr: ast.AST | None = None
            if (
                isinstance(value, ast.Subscript)
                and isinstance(value.value, ast.Name)
            ):
                registry_name = value.value.id
                key_expr = value.slice
            elif (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Attribute)
                and isinstance(value.func.value, ast.Name)
                and value.func.attr == "get"
                and value.args
            ):
                registry_name = value.func.value.id
                key_expr = value.args[0]
            if (
                registry_name in registries
                and key_expr is not None
                and _is_action_expr(key_expr, aliases)
            ):
                for target in targets:
                    for name in _assigned_names(target):
                        derived_handlers[name] = registry_name

    for node in ast.walk(main_node):
        if not isinstance(node, ast.Call):
            continue
        registry_name: str | None = None
        key_expr: ast.AST | None = None
        if isinstance(node.func, ast.Subscript) and isinstance(node.func.value, ast.Name):
            registry_name = node.func.value.id
            key_expr = node.func.slice
        elif (
            isinstance(node.func, ast.Call)
            and isinstance(node.func.func, ast.Attribute)
            and isinstance(node.func.func.value, ast.Name)
            and node.func.func.attr == "get"
            and node.func.args
        ):
            registry_name = node.func.func.value.id
            key_expr = node.func.args[0]
        elif isinstance(node.func, ast.Name):
            registry_name = derived_handlers.get(node.func.id)
            if registry_name:
                invoked.add(registry_name)
        if (
            registry_name in registries
            and key_expr is not None
            and _is_action_expr(key_expr, aliases)
        ):
            invoked.add(registry_name)

    keys: set[str] = set()
    for registry_name in invoked:
        keys.update(registries[registry_name])
    return keys


def extract_dispatch_actions(
    main_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    aliases = _action_aliases(main_node)
    actions: set[str] = set()
    for node in ast.walk(main_node):
        if isinstance(node, (ast.If, ast.IfExp)):
            actions.update(_equality_dispatch_values(node.test, aliases))
    actions.update(_dict_dispatch_keys(main_node, aliases))
    return actions


def check_parity_source(
    source: str,
    *,
    path: str = _HUB_REL,
) -> list[Finding]:
    try:
        tree = ast.parse(source, filename=path)
        main_node = _main_function(tree)
        choices, choice_line = extract_action_choices(main_node)
        dispatch = extract_dispatch_actions(main_node)
    except (SyntaxError, TypeError, ValueError) as exc:
        return [
            Finding(
                "CLI_DISPATCH_PARITY_ERROR",
                path,
                int(getattr(exc, "lineno", 0) or 0),
                str(exc),
            )
        ]

    findings: list[Finding] = []
    for action in sorted(choices - dispatch):
        findings.append(
            Finding(
                "CLI_CHOICE_WITHOUT_DISPATCH",
                path,
                choice_line,
                f"argparse choice {action!r} has no real dispatch branch",
            )
        )
    for action in sorted(dispatch - choices):
        findings.append(
            Finding(
                "CLI_DISPATCH_WITHOUT_CHOICE",
                path,
                int(main_node.lineno),
                f"dispatch branch {action!r} has no declared argparse choice",
            )
        )
    return findings


def check_view(view: FileView) -> list[Finding]:
    if not view.exists(_HUB_REL):
        return [
            Finding(
                "CLI_DISPATCH_PARITY_ERROR",
                _HUB_REL,
                0,
                "hub.py is missing from the selected source view",
            )
        ]
    try:
        source = view.read_text(_HUB_REL)
    except (OSError, RuntimeError) as exc:
        return [
            Finding(
                "CLI_DISPATCH_PARITY_ERROR",
                _HUB_REL,
                0,
                f"could not read hub.py: {exc}",
            )
        ]
    return check_parity_source(source)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check hub argparse action/dispatch parity",
    )
    parser.add_argument(
        "--source",
        choices=["index", "worktree"],
        default="index",
        help="source view (default: staged index)",
    )
    args = parser.parse_args(argv)
    started = time.perf_counter()
    try:
        view: FileView = (
            IndexView(_ROOT)
            if args.source == "index"
            else WorktreeView(_ROOT)
        )
        findings = check_view(view)
    except Exception as exc:
        findings = [
            Finding(
                "CLI_DISPATCH_PARITY_ERROR",
                "checker",
                0,
                str(exc),
            )
        ]

    elapsed_ms = (time.perf_counter() - started) * 1000
    print(
        f"[CLI-PARITY] choices_vs_dispatch "
        f"findings={len(findings)} elapsed_ms={elapsed_ms:.1f}"
    )
    for finding in findings:
        print(finding.render())
    exit_code = 1 if findings else 0
    print(f"[CLI-PARITY] gate_exit={exit_code}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
