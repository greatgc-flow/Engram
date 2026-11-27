"""Cross-package isolation with the actual development interpreter and disposable environments."""
import json
from pathlib import Path
import subprocess
import sys

from _sys.core.root import find_root

SYSTEM = find_root(__file__)
FIXTURES = SYSTEM / "tests/fixtures/optional-pack"


def test_three_local_consumers_share_only_the_base(tmp_path):
    fixture_paths = sorted(FIXTURES.glob("*.descriptor.json"))
    probe = SYSTEM.parent / "tools/feasibility/pack_environments.py"
    run = subprocess.run([sys.executable, "-B", str(probe), *map(str, fixture_paths)],
                         cwd=tmp_path, text=True, capture_output=True, timeout=120)
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert list(result) == ["ai", "contentflow", "gamma"]
    assert {row["base_prefix"] for row in result.values()} == {str(Path(sys.base_prefix).resolve())}
    assert len({row["environment"] for row in result.values()}) == 3
    for package, row in result.items():
        assert row["visible"] == [package]
        assert row["version"] == sys.version.split()[0]
        assert row["fixture_data_unchanged"] is True
    assert list(tmp_path.iterdir()) == []
