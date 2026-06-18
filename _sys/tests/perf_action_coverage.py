"""Benchmark E — Hub action × test coverage MECE matrix.

Extracts all hub.py CLI actions, maps each to unit/integration test coverage.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

SYS = Path(__file__).parent.parent
HUB_PY = SYS / "core" / "hub.py"
TEST_DIR = SYS / "tests"


def extract_hub_actions(hub_path: Path) -> list[str]:
    """Extract all action names registered in hub.py's argparse setup."""
    text = hub_path.read_text(encoding="utf-8")
    # Pattern 1: add_argument("action", choices=[...]) — hub.py's flat choices list
    choices_match = re.search(
        r'add_argument\s*\(\s*["\']action["\'].*?choices\s*=\s*\[([^\]]+)\]',
        text, re.DOTALL
    )
    actions: list[str] = []
    if choices_match:
        raw = choices_match.group(1)
        actions = re.findall(r'["\']([a-z][a-z0-9\-]+)["\']', raw)
    # Pattern 2: subparser add_parser fallback
    actions += re.findall(r'add_parser\s*\(\s*["\']([a-z][a-z0-9\-]+)["\']', text)
    # Deduplicate, preserve order
    seen: set[str] = set()
    result: list[str] = []
    for a in actions:
        if a not in seen:
            seen.add(a)
            result.append(a)
    return sorted(result)


def scan_test_coverage(action: str, test_dir: Path) -> dict[str, bool]:
    """Check if action name appears in unit and integration test files."""
    action_variants = [
        action,
        action.replace("-", "_"),
        action.replace("-", ""),
    ]

    unit_files = list((test_dir / "unit").glob("*.py")) if (test_dir / "unit").exists() else []
    integ_files = list((test_dir / "integration").glob("*.py")) if (test_dir / "integration").exists() else []
    all_test_files = list(test_dir.glob("test_*.py")) + list(test_dir.glob("*_test.py"))

    def hits(files: list[Path]) -> bool:
        for f in files:
            try:
                txt = f.read_text(encoding="utf-8", errors="ignore")
                if any(v in txt for v in action_variants):
                    return True
            except Exception:
                pass
        return False

    return {
        "unit":        hits(unit_files),
        "integration": hits(integ_files),
        "any_test":    hits(unit_files + integ_files + all_test_files),
    }


def classify(cov: dict[str, bool]) -> str:
    if cov["unit"] and cov["integration"]:
        return "FULL"
    if cov["unit"]:
        return "UNIT"
    if cov["integration"]:
        return "INTG"
    if cov["any_test"]:
        return "MISC"
    return "NONE"


# ── Main ─────────────────────────────────────────────────────────────────────

actions = extract_hub_actions(HUB_PY)
results = []
for action in actions:
    cov = scan_test_coverage(action, TEST_DIR)
    cls = classify(cov)
    results.append((action, cov, cls))

by_class = {"FULL": [], "UNIT": [], "INTG": [], "MISC": [], "NONE": []}
for action, cov, cls in results:
    by_class[cls].append(action)

print("=" * 70)
print(f"  BENCHMARK E — Hub action × test coverage matrix")
print(f"  hub.py: {HUB_PY}")
print(f"  Total actions found: {len(actions)}")
print("=" * 70)
print()
print(f"  {'Action':<30}  {'Unit':>5}  {'Intg':>5}  {'Status':>6}")
print("-" * 56)

for action, cov, cls in results:
    u = "YES" if cov["unit"] else "---"
    i = "YES" if cov["integration"] else "---"
    marker = "  !!!" if cls == "NONE" else ""
    print(f"  {action:<30}  {u:>5}  {i:>5}  {cls:>6}{marker}")

print()
print("=" * 70)
print("  SUMMARY")
print("=" * 70)
total = len(results)
for cls, items in by_class.items():
    pct = len(items) / total * 100 if total else 0
    bar = "#" * int(pct / 2)
    print(f"  {cls:>4} ({len(items):>3} actions, {pct:>5.1f}%)  |{bar}")

print()
print(f"  Coverage rate (any test) : {sum(1 for _,c,_ in results if c['any_test'])}/{total} = "
      f"{sum(1 for _,c,_ in results if c['any_test'])/total*100:.1f}%")
print(f"  UNTESTED actions ({len(by_class['NONE'])}):  {', '.join(by_class['NONE']) or 'none'}")
print()
print("  Done.")
