"""Regression test: saturation_scan.py's EXCLUDE_DIRS used a plain "tmp" entry
that never matched codex's actual cache dir name ".tmp" (leading dot), and had
no exclusion at all for the antigravity/claude skill-marketplace and plugin
caches. This inflated a real scan from 18 genuine findings to 1021, almost all
noise from vendored third-party content this project doesn't own."""
import sys
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parent.parent.parent  # _sys/
sys.path.insert(0, str(SYS_DIR / "checks"))
import saturation_scan as sat  # noqa: E402


def _make_vendor_tree(tmp_path: Path) -> Path:
    sys_root = tmp_path / "_sys"
    # A genuinely-oversized file that SHOULD be flagged.
    real = sys_root / "core" / "big.py"
    real.parent.mkdir(parents=True)
    real.write_text("\n" * 700, encoding="utf-8")

    # Vendor content that should NOT be flagged.
    (sys_root / "codex" / "config" / ".tmp" / "plugins").mkdir(parents=True)
    (sys_root / "codex" / "config" / ".tmp" / "plugins" / "vendor.py").write_text(
        "\n" * 700, encoding="utf-8"
    )
    (sys_root / "antigravity" / "config" / "skills" / "some-skill").mkdir(parents=True)
    (sys_root / "antigravity" / "config" / "skills" / "some-skill" / "SKILL.md").write_text(
        "\n" * 500, encoding="utf-8"
    )
    (sys_root / "claude" / "config").mkdir(parents=True)
    (sys_root / "claude" / "config" / ".claude.json").write_text(
        "{" + "\n" * 1200 + "}", encoding="utf-8"
    )
    return sys_root


def test_vendor_content_excluded_real_code_flagged(tmp_path):
    sys_root = _make_vendor_tree(tmp_path)

    findings = sat.scan_lines(sys_root)

    paths = {f.path for f in findings}
    assert any("big.py" in p for p in paths)
    assert not any("vendor.py" in p for p in paths)
    assert not any("SKILL.md" in p for p in paths)
    assert not any(".claude.json" in p for p in paths)
