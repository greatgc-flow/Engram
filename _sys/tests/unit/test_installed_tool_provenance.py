"""Synthetic offline tests for Engram's read-only installed provenance audit."""
import json

from _sys.checks import audit_installed_tool_provenance as evidence


def _make_installed(tmp_path):
    sys_dir = tmp_path / "_sys"
    (sys_dir / "defaults").mkdir(parents=True)
    config = json.loads(evidence.DEFAULTS.read_text(encoding="utf-8"))
    (sys_dir / "defaults" / "runtimes.json").write_text(
        json.dumps(config), encoding="utf-8"
    )
    for name in evidence.PINNED_TOOLS:
        spec = config["tools"][name]
        folder = sys_dir / "tools" / name
        folder.mkdir(parents=True)
        (folder / spec["bin"]).write_bytes(b"synthetic, not real executable bytes")
        manifest = {
            "tool": name,
            "declared_version": spec["version"],
            "url": spec["url"],
            "checksum_algo": "sha256",
            "checksum_value": spec["sha256"],
            "checksum_source": "declared",
            "checksum_verified": True,
            "source_config_hash": evidence._source_hash(spec),
        }
        (folder / ".install_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
    return sys_dir


def test_recorded_provenance_checks_eight_default_tools(tmp_path):
    root = _make_installed(tmp_path)
    result = evidence.audit(root)
    assert result["overall"] == "PASS_RECORDED"
    assert result["recorded_pass"] == 8
    assert result["holds"] == 0
    assert "not executable byte attestation" in result["scope"]


def test_missing_tool_binary_holds(tmp_path):
    root = _make_installed(tmp_path)
    (root / "tools" / "gh" / "gh.exe").unlink()
    result = evidence.audit(root)
    assert result["overall"] == "HOLD"
    assert result["items"]["gh"]["reason"] == "installed executable absent or symbolic link"


def test_unverified_tls_manifest_holds(tmp_path):
    root = _make_installed(tmp_path)
    path = root / "tools" / "ripgrep" / ".install_manifest.json"
    obj = json.loads(path.read_text(encoding="utf-8"))
    obj["checksum_source"] = "computed_tls_trust"
    obj["checksum_verified"] = False
    path.write_text(json.dumps(obj), encoding="utf-8")
    assert evidence.audit(root)["items"]["ripgrep"]["status"] == "HOLD"


def test_stale_effective_configuration_holds(tmp_path):
    root = _make_installed(tmp_path)
    path = root / "defaults" / "runtimes.json"
    obj = json.loads(path.read_text(encoding="utf-8"))
    obj["tools"]["bat"]["sha256"] = "f" * 64
    path.write_text(json.dumps(obj), encoding="utf-8")
    result = evidence.audit(root)
    assert result["items"]["bat"]["status"] == "HOLD"
    assert result["items"]["bat"]["reason"] == "effective configuration differs from pinned default"


def test_corrupted_manifest_and_missing_directory_hold(tmp_path):
    root = _make_installed(tmp_path)
    path = root / "tools" / "jq" / ".install_manifest.json"
    path.write_text("{bad", encoding="utf-8")
    (root / "tools" / "fd" / ".install_manifest.json").unlink()
    result = evidence.audit(root)
    assert result["items"]["jq"]["reason"] == "installed manifest unreadable"
    assert result["items"]["fd"]["reason"] == "installed manifest missing"


def test_bad_derived_config_hash_holds(tmp_path):
    root = _make_installed(tmp_path)
    path = root / "tools" / "fzf" / ".install_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["source_config_hash"] = "0" * 64
    path.write_text(json.dumps(data), encoding="utf-8")
    assert evidence.audit(root)["items"]["fzf"]["status"] == "HOLD"


def test_console_and_evidence_are_identical(tmp_path, capsys):
    root = _make_installed(tmp_path)
    target = tmp_path / "results" / "audit.json"
    assert evidence.main(["--sys-dir", str(root), "--evidence", str(target)]) == 0
    assert target.read_bytes() == capsys.readouterr().out.encode("utf-8")
    assert json.loads(target.read_text(encoding="utf-8"))["recorded_pass"] == 8


def test_holding_configuration_has_nonzero_cli_status(tmp_path, capsys):
    root = _make_installed(tmp_path)
    (root / "tools" / "ripgrep" / "rg.exe").unlink()
    assert evidence.main(["--sys-dir", str(root)]) == 2
    output = json.loads(capsys.readouterr().out)
    assert output["overall"] == "HOLD"
    assert output["holds"] == 1
