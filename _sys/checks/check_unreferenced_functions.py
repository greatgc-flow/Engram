"""Detect newly unwired top-level Python functions.

The default mode is a staged-index pre-commit gate. It inspects only
top-level functions whose staged definition spans changed lines, then resolves
production references from the staged index. ``--full-tree`` is advisory and
always exits zero so legacy debt cannot block unrelated work.

This check intentionally does not detect write-only artifacts, ignored return
values, or missing schedulers. Those are separate producer/consumer contract
shapes.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import time
import tokenize
from io import StringIO
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

_CHECKS_DIR = Path(__file__).resolve().parent
_SYS_DIR = _CHECKS_DIR.parent
_ROOT = _SYS_DIR.parent
_BASELINE_REL = "_sys/checks/unreferenced_functions_baseline.json"
_DISPATCH_REL = "_sys/dispatch.json"
_PRODUCTION_PREFIXES = (
    "_sys/checks/",
    "_sys/cli/",
    "_sys/core/",
    "_sys/hooks/",
)
_EXCLUDED_PARTS = {
    "test",
    "tests",
    "env",
    "tools",
    "vendor",
    "third_party",
    "__pycache__",
}
_TAG_MARKER = "WIRING-EXEMPT:"
_VALID_TAG_RE = re.compile(
    r'#\s*WIRING-EXEMPT:\s*'
    r'(EXPORTED_API|DYNAMIC_ENTRYPOINT|BACKCOMPAT_API)'
    r'\s+reason="([^"\r\n]+)"\s*$'
)
_HUNK_RE = re.compile(
    r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@"
)

sys.path.insert(0, str(_CHECKS_DIR))
from _common import IndexView, WorktreeView  # noqa: E402


class FileView(Protocol):
    def list_files(self, prefix: str = "", suffix: str = "") -> list[str]: ...
    def exists(self, rel_path: str) -> bool: ...
    def read_text(self, rel_path: str) -> str: ...


FunctionKey = tuple[str, str]


@dataclass
class FunctionInfo:
    path: str
    name: str
    line: int
    end_line: int
    start_line: int
    exempt: bool = False

    @property
    def key(self) -> FunctionKey:
        return (self.path, self.name)


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    line: int
    name: str
    message: str
    baselined: bool = False

    def render(self) -> str:
        baseline = " [BASELINED]" if self.baselined else ""
        subject = f" {self.name}" if self.name else ""
        return (
            f"[{self.code}]{baseline} {self.path}:{self.line}"
            f"{subject} - {self.message}"
        )


def _clean_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("/")


def is_production_python(path: str) -> bool:
    clean = _clean_path(path)
    if not clean.endswith(".py"):
        return False
    parts = clean.split("/")
    if any(part.lower() in _EXCLUDED_PARTS for part in parts[:-1]):
        return False
    return not parts[-1].startswith("test_")


def production_python_paths(view: FileView) -> list[str]:
    """Return the real production Python surface represented by ``view``."""
    if isinstance(view, IndexView):
        paths = view.list_files(suffix=".py")
    else:
        paths: list[str] = []
        for prefix in _PRODUCTION_PREFIXES:
            paths.extend(view.list_files(prefix, suffix=".py"))
    return sorted({_clean_path(path) for path in paths if is_production_python(path)})


def _preload_view_texts(view: FileView, paths: list[str]) -> None:
    reader = getattr(view, "read_many_text", None)
    if not callable(reader):
        return
    existing = [
        path
        for path in dict.fromkeys(_clean_path(item) for item in paths)
        if view.exists(path)
    ]
    if existing:
        reader(existing)


def staged_changed_line_ranges(
    root: Path,
    *,
    suffix: str = ".py",
) -> dict[str, list[tuple[int, int]]]:
    """Return staged new-file line ranges, including deletion anchor points."""
    try:
        diff = subprocess.run(
            [
                "git",
                "-c",
                "core.quotepath=false",
                "diff",
                "--cached",
                "--diff-filter=AMR",
                "--unified=0",
                "--no-color",
                "--no-ext-diff",
                "--",
                f"*{suffix}",
            ],
            cwd=str(root),
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"staged diff inventory failed: {exc}") from exc

    changed: dict[str, list[tuple[int, int]]] = {}
    current_path: str | None = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            marker = line[4:]
            if marker == "/dev/null":
                current_path = None
            elif marker.startswith("b/"):
                current_path = _clean_path(marker[2:])
            else:
                current_path = _clean_path(marker)
            continue
        match = _HUNK_RE.match(line)
        if not match or current_path is None:
            continue
        start = int(match.group(1))
        count = int(match.group(2)) if match.group(2) is not None else 1
        end = start + max(count, 1) - 1
        changed.setdefault(current_path, []).append((start, end))
    return changed


def _range_overlaps(
    ranges: list[tuple[int, int]],
    start: int,
    end: int,
) -> bool:
    return any(range_start <= end and start <= range_end for range_start, range_end in ranges)


def _top_level_functions(path: str, tree: ast.Module) -> list[FunctionInfo]:
    infos: list[FunctionInfo] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        decorator_lines = [
            int(decorator.lineno)
            for decorator in node.decorator_list
            if getattr(decorator, "lineno", None)
        ]
        start_line = min([int(node.lineno), *decorator_lines])
        infos.append(
            FunctionInfo(
                path=path,
                name=node.name,
                line=int(node.lineno),
                end_line=int(getattr(node, "end_lineno", node.lineno)),
                start_line=max(1, start_line - 1),
            )
        )
    return infos


def _parse_source(
    view: FileView,
    path: str,
) -> tuple[str | None, ast.Module | None, Finding | None]:
    try:
        source = view.read_text(path)
        return source, ast.parse(source, filename=path), None
    except (OSError, UnicodeError, SyntaxError, RuntimeError) as exc:
        line = int(getattr(exc, "lineno", 0) or 0)
        finding = Finding(
            "WIRING_ANALYSIS_ERROR",
            path,
            line,
            "",
            f"could not parse production source: {exc}",
        )
        return None, None, finding


def _tag_inventory(
    sources: dict[str, str],
    infos_by_path: dict[str, list[FunctionInfo]],
    changed_ranges: dict[str, list[tuple[int, int]]] | None,
) -> tuple[set[FunctionKey], list[Finding]]:
    valid_keys: set[FunctionKey] = set()
    findings: list[Finding] = []

    for path, source in sources.items():
        if _TAG_MARKER not in source:
            continue
        lines = source.splitlines()
        infos = infos_by_path.get(path, [])
        attachments: dict[int, list[FunctionInfo]] = {}
        for info in infos:
            attachments.setdefault(info.line, []).append(info)
            if info.line > 1:
                attachments.setdefault(info.line - 1, []).append(info)

        try:
            comments = {
                token.start[0]: token.string
                for token in tokenize.generate_tokens(StringIO(source).readline)
                if token.type == tokenize.COMMENT and _TAG_MARKER in token.string
            }
        except (IndentationError, tokenize.TokenError):
            comments = {}

        for line_number, comment in comments.items():
            line = lines[line_number - 1]
            if _TAG_MARKER not in comment:
                continue
            if changed_ranges is not None:
                path_ranges = changed_ranges.get(path, [])
                if not _range_overlaps(path_ranges, line_number, line_number):
                    continue

            attached = attachments.get(line_number, [])
            match = _VALID_TAG_RE.fullmatch(comment)
            valid = bool(match and match.group(2).strip())
            if not attached:
                findings.append(
                    Finding(
                        "INVALID_WIRING_EXEMPT",
                        path,
                        line_number,
                        "",
                        "tag must be on a top-level def line or immediately above it",
                    )
                )
                continue
            if not valid:
                findings.append(
                    Finding(
                        "INVALID_WIRING_EXEMPT",
                        path,
                        line_number,
                        attached[0].name,
                        "expected '# WIRING-EXEMPT: "
                        "EXPORTED_API|DYNAMIC_ENTRYPOINT|BACKCOMPAT_API "
                        'reason=\"...\"',
                    )
                )
                continue
            for info in attached:
                valid_keys.add(info.key)

    return valid_keys, findings


def discover_changed_candidates(
    view: FileView,
    changed_paths: list[str],
    changed_ranges: dict[str, list[tuple[int, int]]],
) -> tuple[list[FunctionInfo], list[Finding]]:
    """Parse changed files only; defer reference inventory to the narrowed pass."""
    sources: dict[str, str] = {}
    infos_by_path: dict[str, list[FunctionInfo]] = {}
    findings: list[Finding] = []
    for path in changed_paths:
        source, tree, parse_finding = _parse_source(view, path)
        if parse_finding:
            findings.append(parse_finding)
            continue
        assert source is not None and tree is not None
        sources[path] = source
        infos_by_path[path] = _top_level_functions(path, tree)

    valid_tags, tag_findings = _tag_inventory(
        sources,
        infos_by_path,
        changed_ranges,
    )
    findings.extend(tag_findings)
    candidates: list[FunctionInfo] = []
    for path, infos in infos_by_path.items():
        path_ranges = changed_ranges.get(path, [])
        for info in infos:
            info.exempt = info.key in valid_tags
            if _range_overlaps(path_ranges, info.start_line, info.end_line):
                candidates.append(info)
    return candidates, findings


class ModuleIndex:
    def __init__(self, paths: list[str]) -> None:
        self.paths = sorted({_clean_path(path) for path in paths})
        self._by_module: dict[str, set[str]] = {}
        self._canonical: dict[str, str] = {}
        for path in self.paths:
            for name in self._module_names(path):
                self._by_module.setdefault(name, set()).add(path)
            self._canonical[path] = self._full_module(path)

    @staticmethod
    def _full_module(path: str) -> str:
        clean = _clean_path(path)
        module = clean[:-3].replace("/", ".")
        if module.endswith(".__init__"):
            module = module[: -len(".__init__")]
        return module

    @classmethod
    def _module_names(cls, path: str) -> set[str]:
        full = cls._full_module(path)
        names = {full}
        if full.startswith("_sys."):
            names.add(full[len("_sys.") :])
        if "." in full:
            names.add(full.rsplit(".", 1)[-1])
        return names

    def canonical(self, path: str) -> str:
        return self._canonical[_clean_path(path)]

    def import_base(
        self,
        current_path: str,
        module: str | None,
        level: int,
    ) -> str:
        if level <= 0:
            return module or ""
        current = self.canonical(current_path)
        current_path_clean = _clean_path(current_path)
        package = current if current_path_clean.endswith("/__init__.py") else current.rsplit(".", 1)[0]
        parts = package.split(".") if package else []
        trim = max(0, level - 1)
        if trim:
            parts = parts[:-trim] if trim <= len(parts) else []
        if module:
            parts.extend(module.split("."))
        return ".".join(parts)

    def resolve(self, module: str) -> set[str]:
        if not module:
            return set()
        direct = self._by_module.get(module)
        if direct:
            return set(direct)
        matches: set[str] = set()
        suffix = "." + module
        for known, paths in self._by_module.items():
            if known.endswith(suffix):
                matches.update(paths)
        return matches


def _function_keys_for(
    module_index: ModuleIndex,
    functions_by_path: dict[str, dict[str, FunctionInfo]],
    module: str,
    name: str,
) -> set[FunctionKey]:
    keys: set[FunctionKey] = set()
    for path in module_index.resolve(module):
        if name in functions_by_path.get(path, {}):
            keys.add((path, name))
    return keys


def _flatten_attribute(node: ast.AST) -> list[str] | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return list(reversed(parts))


@dataclass
class ImportInventory:
    module_bindings: dict[str, set[str]]
    imported_keys: set[FunctionKey]


def _imports_for_module(
    path: str,
    tree: ast.Module,
    module_index: ModuleIndex,
    functions_by_path: dict[str, dict[str, FunctionInfo]],
) -> ImportInventory:
    module_bindings: dict[str, set[str]] = {}
    imported_keys: set[FunctionKey] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    module_bindings.setdefault(alias.asname, set()).add(alias.name)
                else:
                    root_name = alias.name.split(".", 1)[0]
                    module_bindings.setdefault(root_name, set()).add(root_name)
        elif isinstance(node, ast.ImportFrom):
            base = module_index.import_base(path, node.module, node.level)
            for alias in node.names:
                if alias.name == "*":
                    for target_path in module_index.resolve(base):
                        imported_keys.update(
                            (target_path, name)
                            for name in functions_by_path.get(target_path, {})
                        )
                    continue
                candidate_module = ".".join(
                    part for part in (base, alias.name) if part
                )
                binding = alias.asname or alias.name
                if module_index.resolve(candidate_module):
                    module_bindings.setdefault(binding, set()).add(candidate_module)
                imported_keys.update(
                    _function_keys_for(
                        module_index,
                        functions_by_path,
                        base,
                        alias.name,
                    )
                )

    return ImportInventory(module_bindings, imported_keys)


def _attribute_targets(
    node: ast.AST,
    imports: ImportInventory,
    module_index: ModuleIndex,
    functions_by_path: dict[str, dict[str, FunctionInfo]],
) -> set[FunctionKey]:
    parts = _flatten_attribute(node)
    if not parts or len(parts) < 2:
        return set()
    bases = imports.module_bindings.get(parts[0])
    if not bases:
        return set()
    function_name = parts[-1]
    middle = parts[1:-1]
    targets: set[FunctionKey] = set()
    for base in bases:
        module = ".".join([base, *middle]) if middle else base
        targets.update(
            _function_keys_for(
                module_index,
                functions_by_path,
                module,
                function_name,
            )
        )
    return targets


def _simple_assignment_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        names: list[str] = []
        for item in node.elts:
            names.extend(_simple_assignment_names(item))
        return names
    return []


def _registry_source_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        return node.value.id
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.attr in {"get", "pop", "__getitem__"}
    ):
        return node.func.value.id
    return None


def _registry_for_iter(node: ast.AST) -> tuple[str | None, str]:
    if isinstance(node, ast.Name):
        return node.id, "sequence"
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.attr in {"values", "items"}
    ):
        return node.func.value.id, node.func.attr
    return None, ""


def _registry_references(
    path: str,
    tree: ast.Module,
    imports: ImportInventory,
    module_index: ModuleIndex,
    functions_by_path: dict[str, dict[str, FunctionInfo]],
    top_nodes: dict[int, FunctionKey],
) -> tuple[set[int], list[tuple[FunctionKey, int, FunctionKey | None]]]:
    deferred_nodes: set[int] = set()
    resolved: list[tuple[FunctionKey, int, FunctionKey | None]] = []
    local_functions = functions_by_path.get(path, {})

    def stored_function_nodes(container: ast.AST) -> list[ast.AST]:
        values: list[ast.AST] = []
        if isinstance(container, ast.Dict):
            values.extend(key for key in container.keys if key is not None)
            values.extend(container.values)
        elif isinstance(container, (ast.List, ast.Tuple, ast.Set)):
            values.extend(container.elts)
        result: list[ast.AST] = []
        for value_node in values:
            if isinstance(value_node, (ast.Name, ast.Attribute)):
                result.append(value_node)
            elif isinstance(value_node, (ast.Dict, ast.List, ast.Tuple, ast.Set)):
                result.extend(stored_function_nodes(value_node))
        return result

    assignments: list[tuple[ast.AST, ast.Name, ast.AST]] = []
    for assignment in ast.walk(tree):
        target: ast.AST | None = None
        value: ast.AST | None = None
        if isinstance(assignment, (ast.Assign, ast.AnnAssign)):
            value = assignment.value
            if isinstance(assignment, ast.Assign) and len(assignment.targets) == 1:
                target = assignment.targets[0]
            elif isinstance(assignment, ast.AnnAssign):
                target = assignment.target
        if (
            not isinstance(target, ast.Name)
            or not isinstance(value, (ast.Dict, ast.List, ast.Tuple, ast.Set))
        ):
            continue
        if stored_function_nodes(value):
            assignments.append((assignment, target, value))

    if not assignments:
        return deferred_nodes, resolved

    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent

    def nearest_scope(node: ast.AST) -> ast.AST:
        current: ast.AST = node
        while id(current) in parents:
            current = parents[id(current)]
            if isinstance(
                current,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.Lambda,
                    ast.ClassDef,
                    ast.Module,
                ),
            ):
                return current
        return tree

    def top_owner(node: ast.AST) -> FunctionKey | None:
        current: ast.AST = node
        while True:
            owner = top_nodes.get(id(current))
            if owner is not None:
                return owner
            parent = parents.get(id(current))
            if parent is None:
                return None
            current = parent

    for assignment, target, value in assignments:

        registry_name = target.id
        stored: list[tuple[FunctionKey, int, FunctionKey | None]] = []
        for item in stored_function_nodes(value):
            item_targets: set[FunctionKey] = set()
            if isinstance(item, ast.Name) and item.id in local_functions:
                item_targets.add((path, item.id))
            elif isinstance(item, ast.Attribute):
                item_targets.update(
                    _attribute_targets(
                        item,
                        imports,
                        module_index,
                        functions_by_path,
                    )
                )
            if item_targets:
                deferred_nodes.add(id(item))
                stored.extend(
                    (
                        key,
                        int(getattr(item, "lineno", assignment.lineno)),
                        top_owner(item),
                    )
                    for key in item_targets
                )
        if not stored:
            continue

        search_root = nearest_scope(assignment)
        aliases: set[str] = set()
        changed = True
        while changed:
            changed = False
            for node in ast.walk(search_root):
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    node_value = node.value
                    targets = (
                        node.targets
                        if isinstance(node, ast.Assign)
                        else [node.target]
                    )
                    source = _registry_source_name(node_value)
                    source_is_alias = (
                        isinstance(node_value, ast.Name)
                        and node_value.id in aliases
                    )
                    if source == registry_name or source_is_alias:
                        for node_target in targets:
                            for name in _simple_assignment_names(node_target):
                                if name not in aliases:
                                    aliases.add(name)
                                    changed = True
                elif isinstance(node, (ast.For, ast.AsyncFor)):
                    source, kind = _registry_for_iter(node.iter)
                    if source != registry_name:
                        continue
                    target_names = _simple_assignment_names(node.target)
                    if kind == "items" and len(target_names) >= 2:
                        target_names = target_names[1:]
                    for name in target_names:
                        if name not in aliases:
                            aliases.add(name)
                            changed = True

        invoked = False
        for call in (
            node for node in ast.walk(search_root) if isinstance(node, ast.Call)
        ):
            if _registry_source_name(call.func) == registry_name:
                invoked = True
                break
            if isinstance(call.func, ast.Name) and call.func.id in aliases:
                invoked = True
                break
        if invoked:
            resolved.extend(stored)

    return deferred_nodes, resolved


class _LocalBindingCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.bound: set[str] = set()
        self.globals: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.bound.add(node.id)

    def visit_arg(self, node: ast.arg) -> None:
        self.bound.add(node.arg)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.bound.add(alias.asname or alias.name.split(".", 1)[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name != "*":
                self.bound.add(alias.asname or alias.name)

    def visit_Global(self, node: ast.Global) -> None:
        self.globals.update(node.names)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.bound.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.bound.add(node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.bound.add(node.name)


def _function_bindings(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[set[str], set[str]]:
    collector = _LocalBindingCollector()
    for arg in (
        list(node.args.posonlyargs)
        + list(node.args.args)
        + list(node.args.kwonlyargs)
    ):
        collector.visit(arg)
    if node.args.vararg:
        collector.visit(node.args.vararg)
    if node.args.kwarg:
        collector.visit(node.args.kwarg)
    for statement in node.body:
        collector.visit(statement)
    return collector.bound, collector.globals


class _ReferenceVisitor(ast.NodeVisitor):
    def __init__(
        self,
        *,
        path: str,
        local_functions: dict[str, FunctionInfo],
        imports: ImportInventory,
        module_index: ModuleIndex,
        functions_by_path: dict[str, dict[str, FunctionInfo]],
        candidate_keys: set[FunctionKey],
        top_nodes: dict[int, FunctionKey],
        deferred_nodes: set[int],
    ) -> None:
        self.path = path
        self.local_functions = local_functions
        self.imports = imports
        self.module_index = module_index
        self.functions_by_path = functions_by_path
        self.candidate_keys = candidate_keys
        self.top_nodes = top_nodes
        self.deferred_nodes = deferred_nodes
        self.owner: FunctionKey | None = None
        self.scopes: list[tuple[set[str], set[str]]] = []
        self.edges: list[tuple[FunctionKey, int, str]] = []

    def _record(self, key: FunctionKey, line: int, kind: str) -> None:
        if key not in self.candidate_keys or key == self.owner:
            return
        self.edges.append((key, line, kind))

    def _visit_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        for default in [*node.args.defaults, *node.args.kw_defaults]:
            if default is not None:
                self.visit(default)
        if node.returns:
            self.visit(node.returns)

        previous_owner = self.owner
        self.owner = self.top_nodes.get(id(node), self.owner)
        self.scopes.append(_function_bindings(node))
        for statement in node.body:
            self.visit(statement)
        self.scopes.pop()
        self.owner = previous_owner

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Name(self, node: ast.Name) -> None:
        if not isinstance(node.ctx, ast.Load) or id(node) in self.deferred_nodes:
            return
        if self.scopes:
            bound, globals_declared = self.scopes[-1]
            if node.id in bound and node.id not in globals_declared:
                return
        if node.id in self.local_functions:
            self._record((self.path, node.id), int(node.lineno), "name")

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute):
            for key in _attribute_targets(
                node.func,
                self.imports,
                self.module_index,
                self.functions_by_path,
            ):
                self._record(key, int(node.lineno), "attribute_call")
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ):
            function_name = node.args[1].value
            module_parts = _flatten_attribute(node.args[0])
            if isinstance(node.args[0], ast.Name):
                module_parts = [node.args[0].id]
            if module_parts:
                first = module_parts[0]
                for base in self.imports.module_bindings.get(first, set()):
                    middle = module_parts[1:]
                    module = ".".join([base, *middle]) if middle else base
                    for key in _function_keys_for(
                        self.module_index,
                        self.functions_by_path,
                        module,
                        function_name,
                    ):
                        self._record(key, int(node.lineno), "literal_getattr")
        self.generic_visit(node)


def _dispatch_roots(
    view: FileView,
    module_index: ModuleIndex,
    functions_by_path: dict[str, dict[str, FunctionInfo]],
) -> tuple[set[FunctionKey], list[Finding]]:
    if not view.exists(_DISPATCH_REL):
        return set(), []
    try:
        data = json.loads(view.read_text(_DISPATCH_REL))
        operations = data.get("operations", {})
        if not isinstance(operations, dict):
            raise ValueError("'operations' must be an object")
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return set(), [
            Finding(
                "WIRING_ANALYSIS_ERROR",
                _DISPATCH_REL,
                0,
                "",
                f"could not load dispatch roots: {exc}",
            )
        ]

    roots: set[FunctionKey] = set()
    for operation in operations.values():
        if not isinstance(operation, dict):
            continue
        module = operation.get("module")
        method = operation.get("method")
        if not isinstance(module, str) or not isinstance(method, str):
            continue
        roots.update(
            _function_keys_for(
                module_index,
                functions_by_path,
                module,
                method,
            )
        )
    return roots, []


def analyze_functions(
    view: FileView,
    paths: list[str],
    *,
    all_production_paths: list[str] | None = None,
    changed_ranges: dict[str, list[tuple[int, int]]] | None = None,
) -> tuple[list[FunctionInfo], list[Finding], dict[FunctionKey, list[str]]]:
    """Analyze ``paths`` and return candidates, findings, and reference edges."""
    clean_paths = sorted({_clean_path(path) for path in paths if is_production_python(path)})
    module_paths = all_production_paths or clean_paths
    module_index = ModuleIndex(module_paths)
    sources: dict[str, str] = {}
    trees: dict[str, ast.Module] = {}
    infos_by_path: dict[str, list[FunctionInfo]] = {}
    findings: list[Finding] = []

    for path in clean_paths:
        source, tree, parse_finding = _parse_source(view, path)
        if parse_finding:
            findings.append(parse_finding)
            continue
        assert source is not None and tree is not None
        sources[path] = source
        trees[path] = tree
        infos_by_path[path] = _top_level_functions(path, tree)

    valid_tags, tag_findings = _tag_inventory(
        sources,
        infos_by_path,
        changed_ranges,
    )
    findings.extend(tag_findings)
    for infos in infos_by_path.values():
        for info in infos:
            info.exempt = info.key in valid_tags

    candidates: list[FunctionInfo] = []
    for path, infos in infos_by_path.items():
        if changed_ranges is None:
            candidates.extend(infos)
            continue
        path_ranges = changed_ranges.get(path, [])
        for info in infos:
            if _range_overlaps(path_ranges, info.start_line, info.end_line):
                candidates.append(info)

    candidate_keys = {info.key for info in candidates}
    functions_by_path = {
        path: {info.name: info for info in infos}
        for path, infos in infos_by_path.items()
    }
    edges: dict[FunctionKey, list[str]] = {key: [] for key in candidate_keys}

    imports_by_path: dict[str, ImportInventory] = {}
    for path, tree in trees.items():
        inventory = _imports_for_module(
            path,
            tree,
            module_index,
            functions_by_path,
        )
        imports_by_path[path] = inventory
        for key in inventory.imported_keys & candidate_keys:
            edges[key].append(f"{path}:import_from")

    for path, tree in trees.items():
        local_functions = functions_by_path.get(path, {})
        top_nodes = {
            id(node): (path, node.name)
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        deferred, registry_edges = _registry_references(
            path,
            tree,
            imports_by_path[path],
            module_index,
            functions_by_path,
            top_nodes,
        )
        for key, line, owner in registry_edges:
            if key in candidate_keys and key != owner:
                edges[key].append(f"{path}:{line}:registry")

        visitor = _ReferenceVisitor(
            path=path,
            local_functions=local_functions,
            imports=imports_by_path[path],
            module_index=module_index,
            functions_by_path=functions_by_path,
            candidate_keys=candidate_keys,
            top_nodes=top_nodes,
            deferred_nodes=deferred,
        )
        visitor.visit(tree)
        for key, line, kind in visitor.edges:
            edges[key].append(f"{path}:{line}:{kind}")

    roots, root_findings = _dispatch_roots(
        view,
        module_index,
        functions_by_path,
    )
    findings.extend(root_findings)
    for key in roots & candidate_keys:
        edges[key].append(f"{_DISPATCH_REL}:dispatch_root")

    for info in candidates:
        if info.exempt or edges.get(info.key):
            continue
        findings.append(
            Finding(
                "UNREFERENCED_FUNCTION",
                info.path,
                info.line,
                info.name,
                "zero non-test production reference edges; add a real caller "
                "or a valid WIRING-EXEMPT tag",
            )
        )

    return candidates, findings, edges


def _candidate_reference_paths(
    root: Path,
    view: FileView,
    candidates: list[FunctionInfo],
    all_paths: list[str],
) -> list[str]:
    candidate_paths = {info.path for info in candidates}
    if not candidates:
        return []
    if not isinstance(view, IndexView):
        return sorted(set(all_paths) | candidate_paths)
    command = [
        "git",
        "grep",
        "--cached",
        "--fixed-strings",
        "-l",
        "-z",
    ]
    module_markers: set[str] = set()
    for path in candidate_paths:
        path_obj = Path(path)
        marker = path_obj.parent.name if path_obj.name == "__init__.py" else path_obj.stem
        if marker:
            module_markers.add(marker)
    for marker in sorted(module_markers):
        command.extend(["-e", marker])
    command.extend(["-e", "import *", "--", "*.py"])
    try:
        result = subprocess.run(
            command,
            cwd=str(root),
            capture_output=True,
        )
    except OSError as exc:
        raise RuntimeError(f"candidate reference search failed: {exc}") from exc
    if result.returncode not in (0, 1):
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"candidate reference search failed: {detail}")
    matches = {
        _clean_path(item.decode("utf-8", errors="replace"))
        for item in result.stdout.split(b"\0")
        if item
    }
    return sorted((matches | candidate_paths) & set(all_paths))


def load_baseline(view: FileView) -> tuple[set[FunctionKey], list[Finding]]:
    if not view.exists(_BASELINE_REL):
        return set(), []
    try:
        data = json.loads(view.read_text(_BASELINE_REL))
        entries = data.get("entries")
        if not isinstance(entries, list):
            raise ValueError("'entries' must be a list")
        keys: set[FunctionKey] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("every baseline entry must be an object")
            path = entry.get("path")
            name = entry.get("name")
            if not isinstance(path, str) or not isinstance(name, str):
                raise ValueError("every baseline entry requires string path/name")
            keys.add((_clean_path(path), name))
        return keys, []
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return set(), [
            Finding(
                "WIRING_ANALYSIS_ERROR",
                _BASELINE_REL,
                0,
                "",
                f"invalid baseline: {exc}",
            )
        ]


def build_baseline(findings: list[Finding]) -> dict[str, Any]:
    entries = [
        {
            "path": finding.path,
            "name": finding.name,
            "reason": "legacy_zero_production_callers",
        }
        for finding in sorted(
            findings,
            key=lambda item: (item.path, item.name),
        )
        if finding.code == "UNREFERENCED_FUNCTION"
    ]
    return {
        "version": 1,
        "identity": "path_and_top_level_function_name",
        "entries": entries,
    }


def _apply_baseline(
    findings: list[Finding],
    baseline: set[FunctionKey],
) -> list[Finding]:
    applied: list[Finding] = []
    for finding in findings:
        is_baselined = (
            finding.code == "UNREFERENCED_FUNCTION"
            and (finding.path, finding.name) in baseline
        )
        applied.append(
            Finding(
                finding.code,
                finding.path,
                finding.line,
                finding.name,
                finding.message,
                baselined=is_baselined,
            )
        )
    return applied


def _print_result(
    *,
    mode: str,
    elapsed_ms: float,
    candidates: list[FunctionInfo],
    findings: list[Finding],
    exit_code: int,
) -> None:
    active = [finding for finding in findings if not finding.baselined]
    print(
        f"[WIRING] mode={mode} candidates={len(candidates)} "
        f"findings={len(findings)} active={len(active)} "
        f"elapsed_ms={elapsed_ms:.1f}"
    )
    for finding in findings:
        print(finding.render())
    if mode == "full-tree":
        print("[WIRING] advisory=true exit=0")
    else:
        print(f"[WIRING] gate_exit={exit_code}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check staged or full-tree top-level function wiring",
    )
    parser.add_argument(
        "--full-tree",
        action="store_true",
        help="scan the production tree in advisory-only mode",
    )
    parser.add_argument(
        "--source",
        choices=["index", "worktree"],
        default=None,
        help="source view (default: index for gate, worktree for --full-tree)",
    )
    parser.add_argument(
        "--print-baseline",
        action="store_true",
        help="print generated baseline JSON after a --full-tree scan",
    )
    args = parser.parse_args(argv)
    started = time.perf_counter()
    full_tree = bool(args.full_tree)
    source = args.source or ("worktree" if full_tree else "index")

    try:
        view: FileView = (
            IndexView(_ROOT)
            if source == "index"
            else WorktreeView(_ROOT)
        )
        all_paths = production_python_paths(view)

        if full_tree:
            paths = all_paths
            changed_ranges = None
            candidates, findings, _ = analyze_functions(
                view,
                paths,
                all_production_paths=all_paths,
            )
        else:
            changed_ranges = staged_changed_line_ranges(_ROOT)
            changed_paths = sorted(
                path
                for path in changed_ranges
                if is_production_python(path) and view.exists(path)
            )
            _preload_view_texts(
                view,
                [*changed_paths, _DISPATCH_REL, _BASELINE_REL],
            )
            initial_candidates, initial_findings = discover_changed_candidates(
                view,
                changed_paths,
                changed_ranges,
            )
            reference_paths = _candidate_reference_paths(
                _ROOT,
                view,
                initial_candidates,
                all_paths,
            )
            _preload_view_texts(view, reference_paths)
            candidates, findings, _ = analyze_functions(
                view,
                reference_paths,
                all_production_paths=all_paths,
                changed_ranges=changed_ranges,
            )
            known = {
                (finding.code, finding.path, finding.line, finding.name)
                for finding in findings
            }
            findings.extend(
                finding
                for finding in initial_findings
                if (
                    finding.code,
                    finding.path,
                    finding.line,
                    finding.name,
                )
                not in known
            )

        baseline, baseline_findings = load_baseline(view)
        findings.extend(baseline_findings)
        findings = _apply_baseline(findings, baseline)
    except Exception as exc:
        candidates = []
        findings = [
            Finding(
                "WIRING_ANALYSIS_ERROR",
                "checker",
                0,
                "",
                str(exc),
            )
        ]

    elapsed_ms = (time.perf_counter() - started) * 1000
    active = [finding for finding in findings if not finding.baselined]
    exit_code = 0 if full_tree else (1 if active else 0)
    _print_result(
        mode="full-tree" if full_tree else "staged-index",
        elapsed_ms=elapsed_ms,
        candidates=candidates,
        findings=findings,
        exit_code=exit_code,
    )
    if args.print_baseline:
        if not full_tree:
            print("[WIRING] --print-baseline requires --full-tree", file=sys.stderr)
            return 2
        print(json.dumps(build_baseline(findings), indent=2))
    return 0 if full_tree else exit_code


if __name__ == "__main__":
    sys.exit(main())
