import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from _sys.core.root import find_root

SYSTEM = find_root(__file__)
FIXTURES = SYSTEM / "tests/fixtures/optional-pack"
sys.path.insert(0, str(SYSTEM))
sys.path.insert(0, str(SYSTEM.parent / "tools/feasibility"))
from core import cli_help

SLOTS = {"ai": "AI", "contentflow": "ContentFlow"}
PIN = {
    "ai": "2b9cf838e2c83b4197716f89a443a5f3fe0595d51e954fe7a9b0f19beb5cdaf9",
    "cf": "bdd97e31d52c96917f966c2cb4c5f996beda0b5f4a98ec8f312cd328c2dd4798",
    "gamma": "7e7a48c6b301dd6e139b2697b5da934d016a6ff32591bbccd51546cdc3984cab",
}


def fixture(stem):
    return (FIXTURES / (stem + ".descriptor.json")).read_bytes()


def test_frozen_cross_repo_bytes_and_all_three_packages():
    from hashlib import sha256
    from optional_pack_catalog import read_catalog
    for stem, expected in PIN.items():
        assert sha256(fixture(stem)).hexdigest() == expected
    for names in ([], ["ai"], ["cf"], ["ai", "cf"], list(PIN)):
        catalog = read_catalog([fixture(n) for n in names], SLOTS, cli_help.verbs())
        assert sorted(d.package_id for d in catalog) == sorted(
            json.loads(fixture(n))["package_id"] for n in names)


def variant(**changes):
    return json.dumps(json.loads(fixture("gamma")) | changes).encode()


@pytest.mark.parametrize("change", [
    {"fixture_only": 1}, {"schema_version": "2.0"}, {"unknown": True},
    {"slot_rel": "AI"}, {"slot_rel": "packages/../gamma"}, {"slot_rel": "packages/GAMMA"},
    {"aliases": ["help"]}, {"aliases": ["update"]}, {"aliases": ["con"]},
    {"aliases": ["x", "x"]}, {"aliases": ["X"]}, {"package_id": "nul", "slot_rel": "packages/nul"},
    {"default_profile": "full"}, {"protocol_max": "2.0"}, {"adapter_operations": ["exec"]},
    {"trust_key_ids": []}, {"aliases": {}}, {"host": "any"}, {"display_name": ""},
])
def test_reject_invalid_descriptor(change):
    from optional_pack_catalog import read_catalog
    with pytest.raises(ValueError):
        read_catalog([variant(**change)], SLOTS, cli_help.verbs())


@pytest.mark.parametrize("change", [
    {"id": "BAD"}, {"requires_packages": ["ai"]},
    {"requires_capabilities": ["python-latest"]}, {"extra": "hook"},
    {"requires_capabilities": ["ffmpeg"], "optional_capabilities": ["ffmpeg"]},
])
def test_reject_invalid_profile(change):
    from optional_pack_catalog import read_catalog
    doc = json.loads(fixture("gamma"))
    doc["profiles"][0].update(change)
    with pytest.raises(ValueError):
        read_catalog([json.dumps(doc).encode()], SLOTS, cli_help.verbs())


def test_catalog_wide_namespace_and_unique_profiles():
    from optional_pack_catalog import read_catalog
    profile = json.loads(fixture("gamma"))["profiles"][0]
    for raw in ([fixture("ai")] * 2, [variant(aliases=["ai"]), fixture("ai")],
                [fixture("ai"), variant(aliases=["ai"])], [variant(profiles=[profile, profile])],
                [variant(aliases=["ai", "contentflow"]), fixture("cf")]):
        with pytest.raises(ValueError):
            read_catalog(raw, SLOTS, cli_help.verbs())


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'\xef\xbb\xbf{}', b'x'*1048577,
                                  b'['*1500+b']'*1500, b'{}\x00'])
def test_reject_bad_wire(raw):
    from optional_pack_catalog import read_catalog
    with pytest.raises(ValueError):
        read_catalog([raw], SLOTS, cli_help.verbs())


def test_read_only_probe_across_mixed_slots(tmp_path):
    from optional_pack_catalog import read_catalog, observe_slots
    root = tmp_path / "renamed system"
    root.mkdir()
    catalog = read_catalog([fixture(n) for n in PIN], SLOTS, cli_help.verbs())
    assert set(observe_slots(root, catalog).values()) == {"ABSENT"}
    assert list(root.iterdir()) == []
    (root / "AI").mkdir()
    sentinel = root / "AI" / "keep.bin"
    sentinel.write_bytes(b"retained?")
    assert observe_slots(root, catalog) == {"ai": "UNKNOWN", "contentflow": "ABSENT", "gamma": "ABSENT"}
    registry = root / "data/state/package-registry.json"
    registry.parent.mkdir(parents=True)
    registry.write_bytes(b"{torn")
    assert set(observe_slots(root, catalog).values()) == {"UNKNOWN"}
    assert sentinel.read_bytes() == b"retained?" and registry.read_bytes() == b"{torn"


def test_unknown_root_is_never_empty_installation(tmp_path):
    from optional_pack_catalog import observe_slots, read_catalog
    with pytest.raises(ValueError):
        observe_slots(tmp_path / "missing", read_catalog([fixture("gamma")], SLOTS, cli_help.verbs()))


def test_feasibility_cli_from_unrelated_cwd(tmp_path):
    root = tmp_path / "system"
    root.mkdir()
    p = subprocess.run([sys.executable, "-B", str(SYSTEM.parent / "tools/feasibility/pack_catalog.py"),
                        str(root), *map(str, sorted(FIXTURES.glob("*.json")))], cwd=tmp_path,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout) == {"ai": "ABSENT", "contentflow": "ABSENT", "gamma": "ABSENT"}
    assert list(root.iterdir()) == []


@pytest.mark.parametrize("borrowed", ["contentflow", "ai", "python", "git", "node"])
def test_alias_does_not_claim_an_absent_reserved_identity(borrowed):
    from optional_pack_catalog import read_catalog
    with pytest.raises(ValueError):
        read_catalog([variant(aliases=[borrowed])], SLOTS, cli_help.verbs())


def test_folded_slots_and_linked_parents_are_unknown(tmp_path):
    from optional_pack_catalog import observe_slots, read_catalog
    catalog = read_catalog([fixture(n) for n in PIN], SLOTS, cli_help.verbs())
    (tmp_path / "aI").mkdir()
    assert observe_slots(tmp_path, catalog)["ai"] == "UNKNOWN"
    link = tmp_path / "packages"
    try:
        link.symlink_to(tmp_path / "missing", target_is_directory=True)
    except OSError:
        pytest.skip("creating a symlink requires OS permission")
    assert observe_slots(tmp_path, catalog)["gamma"] == "UNKNOWN"


def test_existing_tool_alias_blocks_generic_entry(tmp_path):
    doc = tmp_path / "gamma.json"
    doc.write_bytes(variant(aliases=["cc"]))
    run = subprocess.run([sys.executable, "-B", str(SYSTEM.parent / "tools/feasibility/pack_catalog.py"),
                          str(tmp_path), str(doc)], text=True, capture_output=True)
    assert run.returncode == 2
    assert "alias" in run.stderr
