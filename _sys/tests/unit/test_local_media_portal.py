"""A local portal snapshot reuses the planner and displays bounded exception evidence."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from test_local_media_plan import TOOLS, inventory, receipt


def finding(**changes):
    return {"source": "inbox/회의.pptx", "source_sha256": "a" * 64,
            "capability": "office-structure", "locator": "Slide 3 / Chart 2",
            "reason": "fidelity-review", "detail": "Chart series has an external reference."} | changes


@pytest.fixture
def portal(monkeypatch):
    monkeypatch.syspath_prepend(str(TOOLS))
    import local_media_portal
    return local_media_portal


def test_snapshot_keeps_findings_separate_from_readiness(portal):
    host = inventory()
    host["receipts"] = [receipt("office-structure", "office-open-xml")]
    rows = [finding(), finding(locator="Slide 5", reason="missing-asset")]
    model = portal.snapshot(host, {"schema_version": 1, "findings": rows})
    assert model["budget"] == host["budget"]
    assert next(row for row in model["capabilities"] if row["capability"] == "office-structure")["status"] == "CPU_CANDIDATE"
    assert {row["locator"] for row in model["findings"]} == {"Slide 3 / Chart 2", "Slide 5"}
    assert all(row["next_action"] for row in model["findings"])


@pytest.mark.parametrize("changes", [
    {"source": "../elsewhere"}, {"source": "C:/data/file"}, {"source": "https://test.invalid/doc"},
    {"source": "input/CON.txt"}, {"locator": ""}, {"reason": "other"}, {"capability": "unknown"},
    {"source_sha256": "short"}, {"detail": "newline\n"},
])
def test_invalid_findings_are_rejected(portal, changes):
    with pytest.raises(ValueError):
        portal.snapshot(inventory(), {"schema_version": 1, "findings": [finding(**changes)]})


def test_duplicate_source_findings_and_conflicting_source_digests_fail(portal):
    for rows in ([finding(), finding(detail="changed")],
                 [finding(), finding(locator="Slide 4", source_sha256="b" * 64)]):
        with pytest.raises(ValueError):
            portal.snapshot(inventory(), {"schema_version": 1, "findings": rows})


def test_render_keeps_markup_as_text_and_contains_no_external_dependencies(portal):
    detail = '</script><img src="https://test.invalid/x" onerror="alert(1)">'
    model = portal.snapshot(inventory(), {"schema_version": 1, "findings": [finding(detail=detail)]})
    html = portal.render(model)
    assert detail not in html and "onerror" in html
    assert "connect-src 'none'" in html
    assert "src=\"http" not in html
    assert 'id="findings"' in html and 'id="capabilities"' in html


def test_cli_works_outside_checkout_and_preserves_existing_file(tmp_path):
    host = tmp_path / "host.json"
    host.write_text(json.dumps(inventory()), encoding="utf-8")
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"schema_version": 1, "findings": [finding()]}), encoding="utf-8")
    output = tmp_path / "local portal.html"
    args = [sys.executable, "-I", "-B", str(TOOLS / "local_media_portal.py"), str(host),
            "--findings", str(report), "--output", str(output)]
    r = subprocess.run(args, cwd=tmp_path, capture_output=True, timeout=15)
    assert r.returncode == 0, r.stderr
    original = output.read_bytes()
    assert "회의.pptx".encode() in original
    r = subprocess.run(args, cwd=tmp_path, capture_output=True, timeout=15)
    assert r.returncode == 2 and output.read_bytes() == original
