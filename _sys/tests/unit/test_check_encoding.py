"""check_encoding._check_one — the UTF-8 / mojibake guard core (CHK-ENC).

Proves the guard catches the 2026-07-07 incident class (unicode destroyed into
literal '?') via git-HEAD regression, catches lossy U+FFFD re-saves, and does
NOT false-positive on a legitimately added question mark.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # _sys/
GUARD = ROOT / "checks" / "check_encoding.py"


def _mod():
    spec = importlib.util.spec_from_file_location("check_encoding_under_test", GUARD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_clean_edit_passes():
    m = _mod()
    base = "# Title — Section §1\nBullet • item → next\n".encode("utf-8")
    new = "# Title — Section §1\nBullet • item → next, extended.\n".encode("utf-8")
    assert m._check_one("f.md", new, base) == []


def test_mojibake_regression_flagged():
    m = _mod()
    base = "# Title — Section §1\nBullet • item → next × end\n".encode("utf-8")
    # every non-ASCII char destroyed into '?'
    new = "# Title ? Section ?1\nBullet ? item ? next ? end\n".encode("utf-8")
    violations = m._check_one("f.md", new, base)
    assert len(violations) == 1
    assert "mojibake regression" in violations[0]


def test_legit_question_mark_not_flagged():
    m = _mod()
    base = "# Title — Section §1\n".encode("utf-8")
    new = "# Title — Section §1\nIs this ok? Yes it is.\n".encode("utf-8")
    assert m._check_one("f.md", new, base) == []


def test_ufffd_replacement_char_flagged():
    m = _mod()
    new = "# Title � broken re-save\n".encode("utf-8")
    violations = m._check_one("f.md", new, base_bytes=None)
    assert len(violations) == 1
    assert "U+FFFD" in violations[0]


def test_new_file_ascii_qmark_allowed():
    # No HEAD base -> regression check skipped; plain ASCII with '?' is fine.
    m = _mod()
    new = "brand new file with a question? sure.\n".encode("utf-8")
    assert m._check_one("new.md", new, base_bytes=None) == []


def test_invalid_utf8_flagged():
    m = _mod()
    new = b"# Title \xff\xfe not utf-8\n"
    violations = m._check_one("f.md", new, base_bytes=None)
    assert len(violations) == 1
    assert "not valid UTF-8" in violations[0]
