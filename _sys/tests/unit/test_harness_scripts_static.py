"""Static contracts for the canonical source-only test harnesses."""

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]

HARNESS_SCRIPTS = (
    "_sys/checks/saturation-scan.bat",
    "_sys/tests/run-tests.bat",
    "_sys/tests/run-sandbox-test.bat",
    "_sys/tests/wsb-entry.bat",
)

RESOLVABLE_REFERENCES = (
    ("_sys/checks/saturation-scan.bat", "_sys/checks/saturation_scan.py"),
    ("_sys/tests/run-tests.bat", "_sys/tests/unit"),
    (
        "_sys/tests/run-tests.bat",
        "_sys/tests/unit/test_system_lifecycle.py",
    ),
    (
        "_sys/tests/run-tests.bat",
        "_sys/tests/unit/test_path_scenarios.py",
    ),
    (
        "_sys/tests/run-sandbox-test.bat",
        "_sys/tests/sandbox-unit-test.wsb",
    ),
    ("_sys/tests/wsb-entry.bat", "_sys/core/bootstrap.bat"),
    ("_sys/tests/wsb-entry.bat", "requirements-dev.txt"),
    ("_sys/tests/wsb-entry.bat", "_sys/tests/unit"),
)


@pytest.mark.parametrize("script_rel", HARNESS_SCRIPTS)
def test_harness_script_exists_and_non_empty(script_rel: str) -> None:
    script_path = REPO_ROOT / script_rel
    assert script_path.is_file(), script_rel
    assert script_path.stat().st_size > 0, script_rel


@pytest.mark.parametrize(("script_rel", "target_rel"), RESOLVABLE_REFERENCES)
def test_harness_references_existing_targets(
    script_rel: str, target_rel: str
) -> None:
    script_path = REPO_ROOT / script_rel
    target_path = REPO_ROOT / target_rel
    assert target_path.exists(), target_rel
    content = script_path.read_text(encoding="utf-8", errors="replace")
    assert target_path.name.lower() in content.lower(), (
        f"{script_rel} does not mention {target_path.name}"
    )


def test_wsb_template_routes_to_the_canonical_guest_entrypoint() -> None:
    template = (
        REPO_ROOT / "_sys/tests/sandbox-unit-test.wsb"
    ).read_text(encoding="utf-8")
    assert "__PORTABLE_ROOT__" in template
    assert "_sys\\tests\\wsb-entry.bat" in template


def test_retired_harnesses_are_not_reintroduced() -> None:
    retired = {
        "host-test.ps1",
        "integration-test.ps1",
        "launch-wsbtest.ps1",
        "test-runner.ps1",
        "local-test.bat",
        "lifecycle_tester.py",
        "sandbox-test.bat",
    }
    existing = {path.name for path in (REPO_ROOT / "_sys/tests").iterdir()}
    assert retired.isdisjoint(existing)


def test_active_harnesses_have_no_legacy_drive_or_subst_contract() -> None:
    for script_rel in HARNESS_SCRIPTS:
        content = (REPO_ROOT / script_rel).read_text(
            encoding="utf-8", errors="replace"
        )
        assert "P:\\" not in content, script_rel
        assert "subst" not in content.lower(), script_rel
