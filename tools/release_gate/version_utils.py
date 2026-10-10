"""Shared numeric release version comparison."""


def parse_version(v: str | None) -> tuple[int, ...]:
    """Parse semver-like version string into a tuple of ints for comparison."""
    if not v:
        return ()
    s = str(v).strip()
    if s.startswith("v") or s.startswith("V"):
        s = s[1:]
    import re
    parts = []
    for part in s.split("."):
        m = re.match(r"^(\d+)", part)
        if m:
            parts.append(int(m.group(1)))
        else:
            break
    return tuple(parts)

