from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent.parent

# P1-3 (commit 0048275) deleted _sys/core/virtualizer.py entirely. These two
# files each carried a leftover reference to it afterward (a dead-code import
# guarded by a swallowed exception in scrubber.py, and a stale docstring
# mention in manage.py) -- neither is a real functional bug on its own, but
# both are misleading: they read as if virtualizer.py still exists.
_FILES_MUST_NOT_MENTION_VIRTUALIZER = (
    "_sys/core/scrubber.py",
    "_sys/cli/manage.py",
)


def test_no_stale_virtualizer_references():
    failures = []
    for rel in _FILES_MUST_NOT_MENTION_VIRTUALIZER:
        path = _ROOT / rel
        content = path.read_text(encoding="utf-8")
        if "virtualizer" in content or "_get_subst_mappings" in content:
            failures.append(rel)

    assert not failures, (
        f"These files still reference the deleted virtualizer module "
        f"(removed in P1-3, commit 0048275): {failures}"
    )
