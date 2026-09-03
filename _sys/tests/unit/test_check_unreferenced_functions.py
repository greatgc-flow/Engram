"""Tests for the S2 unreferenced-function wiring checker."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from _sys.checks import check_unreferenced_functions as checker
from _sys.checks import _common


class MemoryView:
    def __init__(self, files: dict[str, str]) -> None:
        self.files = {
            path.replace("\\", "/"): content
            for path, content in files.items()
        }

    def list_files(self, prefix: str = "", suffix: str = "") -> list[str]:
        return sorted(
            path
            for path in self.files
            if (not prefix or path.startswith(prefix))
            and (not suffix or path.endswith(suffix))
        )

    def exists(self, rel_path: str) -> bool:
        return rel_path.replace("\\", "/") in self.files

    def read_text(self, rel_path: str) -> str:
        return self.files[rel_path.replace("\\", "/")]


def _analyze(
    files: dict[str, str],
    *,
    changed_ranges: dict[str, list[tuple[int, int]]] | None = None,
):
    view = MemoryView(files)
    paths = [
        path for path in files
        if checker.is_production_python(path)
    ]
    return checker.analyze_functions(
        view,
        paths,
        all_production_paths=paths,
        changed_ranges=changed_ranges,
    )


def _unreferenced(findings):
    return {
        (finding.path, finding.name)
        for finding in findings
        if finding.code == "UNREFERENCED_FUNCTION"
    }


def test_changed_range_limits_gate_candidates_to_changed_top_level_function():
    path = "_sys/core/example.py"
    source = (
        "def changed():\n"
        "    return 1\n"
        "\n"
        "def unchanged():\n"
        "    return 2\n"
    )
    candidates, findings, _ = _analyze(
        {path: source},
        changed_ranges={path: [(1, 2)]},
    )
    assert [candidate.name for candidate in candidates] == ["changed"]
    assert _unreferenced(findings) == {(path, "changed")}


def test_staged_diff_ranges_use_one_patch_and_keep_deletion_anchor(monkeypatch):
    patch = (
        "diff --git a/_sys/core/space name.py b/_sys/core/space name.py\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/_sys/core/space name.py\n"
        "@@ -0,0 +1,3 @@\n"
        "+def new_fn():\n"
        "+    return 1\n"
        "+\n"
        "diff --git a/_sys/core/existing.py b/_sys/core/existing.py\n"
        "--- a/_sys/core/existing.py\n"
        "+++ b/_sys/core/existing.py\n"
        "@@ -10,2 +9,0 @@\n"
        "-old\n"
        "-lines\n"
    )
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=patch.encode(),
            stderr=b"",
        )

    monkeypatch.setattr(checker.subprocess, "run", fake_run)
    ranges = checker.staged_changed_line_ranges(Path("repo"))
    assert ranges == {
        "_sys/core/space name.py": [(1, 3)],
        "_sys/core/existing.py": [(9, 9)],
    }
    assert len(calls) == 1


def test_index_view_batch_reads_and_caches_staged_blobs(monkeypatch, tmp_path):
    oid_a = "a" * 40
    oid_b = "b" * 40
    payload = (
        f"{oid_a} blob 3\n".encode()
        + b"one\n"
        + f"{oid_b} blob 3\n".encode()
        + b"two\n"
    )
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs.get("input")))
        return subprocess.CompletedProcess(command, 0, stdout=payload, stderr=b"")

    monkeypatch.setattr(_common.subprocess, "run", fake_run)
    view = _common.IndexView.__new__(_common.IndexView)
    view.root = tmp_path
    view._staged_map = {
        "_sys/core/a.py": oid_a,
        "_sys/core/b.py": oid_b,
    }
    view._text_cache = {}

    loaded = view.read_many_text(["_sys/core/a.py", "_sys/core/b.py"])
    assert loaded == {
        "_sys/core/a.py": "one",
        "_sys/core/b.py": "two",
    }
    assert view.read_text("_sys/core/a.py") == "one"
    assert len(calls) == 1


def test_direct_name_reference_counts_but_self_recursion_does_not():
    path = "_sys/core/example.py"
    source = (
        "def wired():\n"
        "    return 1\n"
        "\n"
        "def recursive_only():\n"
        "    return recursive_only()\n"
        "\n"
        "def caller():\n"
        "    return wired()\n"
    )
    _, findings, edges = _analyze({path: source})
    assert edges[(path, "wired")]
    assert not edges[(path, "recursive_only")]
    assert (path, "wired") not in _unreferenced(findings)
    assert (path, "recursive_only") in _unreferenced(findings)


def test_importfrom_and_attribute_calls_resolve_module_specific_edges():
    target = "_sys/core/target_mod.py"
    files = {
        target: "def imported():\n    return 1\n\ndef attributed():\n    return 2\n",
        "_sys/core/import_caller.py": "from core.target_mod import imported\n",
        "_sys/core/attribute_caller.py": (
            "from core import target_mod as tm\n"
            "\n"
            "def call():\n"
            "    return tm.attributed()\n"
        ),
    }
    _, findings, edges = _analyze(files)
    assert edges[(target, "imported")]
    assert edges[(target, "attributed")]
    assert (target, "imported") not in _unreferenced(findings)
    assert (target, "attributed") not in _unreferenced(findings)


def test_invoked_registry_counts_stored_function_but_dead_registry_does_not():
    path = "_sys/checks/registry.py"
    source = (
        "def wired():\n"
        "    return 1\n"
        "\n"
        "def unwired():\n"
        "    return 2\n"
        "\n"
        "def run():\n"
        "    check_map = {'wired': wired}\n"
        "    dead_map = {'unwired': unwired}\n"
        "    fn = check_map.get('wired')\n"
        "    return fn()\n"
    )
    _, findings, edges = _analyze({path: source})
    assert any("registry" in edge for edge in edges[(path, "wired")])
    assert not edges[(path, "unwired")]
    assert (path, "unwired") in _unreferenced(findings)


def test_registry_invocation_in_another_local_scope_does_not_wire_dead_map():
    path = "_sys/checks/registry_scope.py"
    source = (
        "def target():\n"
        "    return 1\n"
        "\n"
        "def stores_only():\n"
        "    check_map = {'target': target}\n"
        "    return check_map\n"
        "\n"
        "def invokes_different_map():\n"
        "    check_map = {'other': lambda: 2}\n"
        "    fn = check_map.get('other')\n"
        "    return fn()\n"
    )
    _, findings, edges = _analyze({path: source})
    assert not edges[(path, "target")]
    assert (path, "target") in _unreferenced(findings)


def test_literal_getattr_counts_and_broad_reflection_does_not():
    target = "_sys/core/target_mod.py"
    source = "def exact_target():\n    return 1\n\ndef reflected_only():\n    return 2\n"
    caller = (
        "import core.target_mod as module\n"
        "\n"
        "def dispatch(name):\n"
        "    getattr(module, 'exact_target')()\n"
        "    return getattr(module, name)\n"
    )
    _, findings, edges = _analyze(
        {
            target: source,
            "_sys/core/caller.py": caller,
        }
    )
    assert any(
        "literal_getattr" in edge
        for edge in edges[(target, "exact_target")]
    )
    assert not edges[(target, "reflected_only")]
    assert (target, "reflected_only") in _unreferenced(findings)


def test_dispatch_json_module_method_pair_is_a_root():
    target = "_sys/core/provisioner.py"
    dispatch = {
        "operations": {
            "provision.deploy": {
                "module": "core.provisioner",
                "method": "deploy",
            }
        }
    }
    files = {
        target: "def deploy(ctx):\n    return ctx\n",
        "_sys/dispatch.json": json.dumps(dispatch),
    }
    _, findings, edges = _analyze(files)
    assert edges[(target, "deploy")] == [
        "_sys/dispatch.json:dispatch_root"
    ]
    assert not _unreferenced(findings)


def test_wiring_exempt_requires_valid_category_reason_and_placement():
    path = "_sys/core/api.py"
    source = (
        '# WIRING-EXEMPT: EXPORTED_API reason="public import contract"\n'
        "def exported():\n"
        "    return 1\n"
        "\n"
        "# WIRING-EXEMPT: BACKCOMPAT_API\n"
        "def bare():\n"
        "    return 2\n"
        "\n"
        '# WIRING-EXEMPT: DYNAMIC_ENTRYPOINT reason="orphan comment"\n'
        "VALUE = 3\n"
    )
    candidates, findings, _ = _analyze({path: source})
    by_name = {candidate.name: candidate for candidate in candidates}
    assert by_name["exported"].exempt is True
    assert by_name["bare"].exempt is False
    invalid = [
        finding
        for finding in findings
        if finding.code == "INVALID_WIRING_EXEMPT"
    ]
    assert len(invalid) == 2
    assert (path, "exported") not in _unreferenced(findings)
    assert (path, "bare") in _unreferenced(findings)


def test_tag_like_text_inside_string_is_not_linted():
    path = "_sys/core/text.py"
    source = (
        "TAG = '# WIRING-EXEMPT: EXPORTED_API reason=\"text\"'\n"
        "\n"
        "def dead():\n"
        "    return TAG\n"
    )
    _, findings, _ = _analyze({path: source})
    assert not [
        finding
        for finding in findings
        if finding.code == "INVALID_WIRING_EXEMPT"
    ]


def test_baseline_round_trip_uses_path_and_function_name_identity():
    findings = [
        checker.Finding(
            "UNREFERENCED_FUNCTION",
            "_sys/core/a.py",
            10,
            "old_api",
            "zero callers",
        )
    ]
    baseline = checker.build_baseline(findings)
    view = MemoryView(
        {
            checker._BASELINE_REL: json.dumps(baseline),
        }
    )
    keys, errors = checker.load_baseline(view)
    assert errors == []
    assert keys == {("_sys/core/a.py", "old_api")}


def test_full_tree_main_is_advisory_even_with_findings(monkeypatch, capsys):
    view = MemoryView(
        {
            "_sys/core/dead.py": "def dead():\n    return 1\n",
        }
    )
    monkeypatch.setattr(checker, "WorktreeView", lambda _root: view)
    assert checker.main(["--full-tree", "--source", "worktree"]) == 0
    assert "advisory=true exit=0" in capsys.readouterr().out


def test_context_ack_is_absent_and_apply_security_semantics_is_current_debt():
    root = Path(__file__).resolve().parents[3]
    view = checker.WorktreeView(root)
    paths = checker.production_python_paths(view)
    candidates, findings, edges = checker.analyze_functions(
        view,
        paths,
        all_production_paths=paths,
    )
    names = {(candidate.path, candidate.name) for candidate in candidates}
    assert not any(name == "context_ack" for _, name in names)
    # _sys/cli/peer_console.py was deleted in the Engram Diet Increment A
    # (see docs/design/2026-09-02_engram-diet-plan-v8.md); its
    # apply_security_semantics debt entry can no longer appear in a live
    # scan since the file itself is gone. _sys/ai/unreferenced_functions_
    # baseline.json still records the historical entry until Increment D
    # cleans up _sys/ai/**, which is expected and load_baseline() below
    # does not validate path existence against the live tree.
    assert (
        "_sys/cli/peer_console.py",
        "apply_security_semantics",
    ) not in _unreferenced(findings)

    baseline, baseline_errors = checker.load_baseline(view)
    assert baseline_errors == []
    assert _unreferenced(findings) == baseline

    dispatch = json.loads(view.read_text("_sys/dispatch.json"))
    for operation in dispatch["operations"].values():
        module = operation["module"]
        method = operation["method"]
        if module.startswith("core."):
            target_path = "_sys/core/" + module.split(".", 1)[1] + ".py"
        else:
            raise AssertionError(f"unexpected live dispatch module: {module}")
        assert "_sys/dispatch.json:dispatch_root" in edges[(target_path, method)]

    registry_edges = edges[
        ("_sys/checks/saturation_scan.py", "scan_lines")
    ]
    assert any(edge.endswith(":registry") for edge in registry_edges)
