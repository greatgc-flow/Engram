"""Extra-download verification, promotion, cleanup, and extraction guards."""
import hashlib
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SYS_DIR = Path(__file__).resolve().parent.parent.parent  # _sys/
sys.path.insert(0, str(SYS_DIR / "core"))
import provisioner as pv  # noqa: E402


def _make_zip(path: Path, content: bytes = b"fixture") -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("file.txt", content)


def test_install_extra_uses_secure_download_not_bare_download(monkeypatch, tmp_path):
    calls = []
    targets = []
    def fake_secure(url, dest):
        calls.append(url)
        targets.append(dest)
        _make_zip(dest)
    monkeypatch.setattr(pv, "_secure_download", fake_secure)
    monkeypatch.setattr(pv, "_download", MagicMock(side_effect=AssertionError("must not use unguarded _download")))

    dest_dir = tmp_path / "dest"
    setup_dir = tmp_path / "setup"
    setup_dir.mkdir()

    probe = setup_dir / "probe.zip"
    _make_zip(probe)
    digest = hashlib.sha256(probe.read_bytes()).hexdigest()
    probe.unlink()
    pv._install_extra("mytool", {
        "url": "https://github.com/x/y/releases/download/v1/extra.zip",
        "type": "zip", "dest": "extra", "sha256": digest,
    }, dest_dir, setup_dir)

    assert calls == ["https://github.com/x/y/releases/download/v1/extra.zip"]
    assert targets[0].suffix == ".part"
    assert (dest_dir / "extra" / "file.txt").exists()


def test_install_extra_rejects_checksum_mismatch(monkeypatch, tmp_path):
    monkeypatch.setattr(pv, "_secure_download", lambda url, dest: _make_zip(dest))

    dest_dir = tmp_path / "dest"
    setup_dir = tmp_path / "setup"
    setup_dir.mkdir()

    try:
        pv._install_extra(
            "mytool",
            {"url": "https://x/extra.zip", "type": "zip", "dest": "extra", "sha256": "0" * 64},
            dest_dir, setup_dir,
        )
        assert False, "expected ValueError on checksum mismatch"
    except ValueError as exc:
        assert "checksum mismatch" in str(exc)
    assert not (dest_dir / "extra" / "file.txt").exists()


def test_install_extra_accepts_matching_checksum(monkeypatch, tmp_path):
    monkeypatch.setattr(pv, "_secure_download", lambda url, dest: _make_zip(dest))

    dest_dir = tmp_path / "dest"
    setup_dir = tmp_path / "setup"
    setup_dir.mkdir()

    # Compute what _make_zip's output actually hashes to by writing one first.
    probe = setup_dir / "probe.zip"
    _make_zip(probe)
    real_hash = hashlib.sha256(probe.read_bytes()).hexdigest()
    probe.unlink()

    pv._install_extra(
        "mytool",
        {"url": "https://x/extra.zip", "type": "zip", "dest": "extra", "sha256": real_hash},
        dest_dir, setup_dir,
    )
    assert (dest_dir / "extra" / "file.txt").exists()


def test_install_extra_promotes_verified_name_before_staged_extract(
    monkeypatch, tmp_path
):
    setup_dir = tmp_path / "setup"
    setup_dir.mkdir()
    probe = setup_dir / "probe.zip"
    _make_zip(probe)
    real_hash = hashlib.sha256(probe.read_bytes()).hexdigest()
    probe.unlink()

    monkeypatch.setattr(pv, "_secure_download", lambda url, dest: _make_zip(dest))
    real_extract = pv._extract
    observed = {}

    def checked_extract(archive, dest):
        observed["archive"] = archive
        observed["dest"] = dest
        assert archive.name == "mytool-extra-extra.zip"
        assert archive.exists()
        assert dest.name.endswith(".extracting")
        assert not list(setup_dir.glob("*.part"))
        real_extract(archive, dest)

    monkeypatch.setattr(pv, "_extract", checked_extract)
    pv._install_extra(
        "mytool",
        {
            "url": "https://x/extra.zip", "type": "zip", "dest": "extra",
            "sha256": real_hash,
        },
        tmp_path / "dest",
        setup_dir,
    )
    assert observed


def test_install_extra_requires_declared_digest_before_download(monkeypatch, tmp_path):
    download = MagicMock()
    monkeypatch.setattr(pv, "_secure_download", download)
    with pytest.raises(ValueError, match="declared digest"):
        pv._install_extra(
            "mytool",
            {"url": "https://x/extra.zip", "type": "zip", "dest": "extra"},
            tmp_path / "dest",
            tmp_path / "setup",
        )
    download.assert_not_called()


def test_install_extra_validates_length_before_extract(monkeypatch, tmp_path):
    monkeypatch.setattr(
        pv,
        "_secure_download",
        lambda url, dest: (_make_zip(dest), {"expected_length": 1})[1],
    )
    extract = MagicMock()
    monkeypatch.setattr(pv, "_extract", extract)
    with pytest.raises(ValueError, match="length mismatch"):
        pv._install_extra(
            "mytool",
            {
                "url": "https://x/extra.zip", "type": "zip", "dest": "extra",
                "sha256": "0" * 64,
            },
            tmp_path / "dest",
            tmp_path / "setup",
        )
    extract.assert_not_called()
    assert not list((tmp_path / "setup").glob("*.part"))


def test_extract_rejects_archive_path_traversal(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escaped.txt", b"no")
    with pytest.raises(ValueError, match="escapes extraction root"):
        pv._extract(archive, tmp_path / "stage")
    assert not (tmp_path / "escaped.txt").exists()
