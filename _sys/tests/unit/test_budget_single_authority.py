"""
Structural test for the budget single-authority invariant.
See _sys/docs-v2/ops/engram-refactor-blueprint-2026-07-20.md, section 4.

This test is intentionally a source-scanning structural test (not a runtime behavioral test).
Its failure message should point whoever breaks it at the blueprint doc's ledger-first
migration section before they add a second writer to canary_budget.json.
"""
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]


def test_single_authority_for_canary_budget():
    """
    Ensure only _sys/checks/canary_budget.py references canary_budget.json.
    """
    sys_dir = ROOT / "_sys"
    dirs_to_scan = ["core", "checks", "cli"]
    
    for d in dirs_to_scan:
        scan_dir = sys_dir / d
        if not scan_dir.exists():
            continue
            
        for py_file in scan_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            if "canary_budget.json" in content:
                if py_file.name != "canary_budget.py":
                    pytest.fail(
                        f"SINGLE AUTHORITY VIOLATION: '{py_file.relative_to(ROOT)}' contains 'canary_budget.json'.\n"
                        f"Only _sys/checks/canary_budget.py is allowed to reference the ledger.\n"
                        f"Please read the blueprint doc (_sys/docs-v2/ops/engram-refactor-blueprint-2026-07-20.md, section 4) "
                        f"before adding a second writer."
                    )


def test_no_rogue_writes_to_canary_budget():
    """
    Scan for open(), write_text(), or json.dump() referencing canary_budget.json.
    Although the first test ensures only canary_budget.py has the string, this is
    a secondary heuristic structural check as requested.
    """
    sys_dir = ROOT / "_sys"
    dirs_to_scan = ["core", "checks", "cli"]
    
    for d in dirs_to_scan:
        scan_dir = sys_dir / d
        if not scan_dir.exists():
            continue
            
        for py_file in scan_dir.rglob("*.py"):
            if py_file.name == "canary_budget.py":
                continue
                
            content = py_file.read_text(encoding="utf-8")
            
            if "canary_budget.json" in content:
                if "open(" in content or ".write_text(" in content or "json.dump(" in content:
                    pytest.fail(
                        f"ILLEGAL WRITE DETECTED: '{py_file.relative_to(ROOT)}' appears to write to 'canary_budget.json'.\n"
                        f"Only _sys/checks/canary_budget.py is allowed to write to this file.\n"
                        f"See _sys/docs-v2/ops/engram-refactor-blueprint-2026-07-20.md, section 4."
                    )
