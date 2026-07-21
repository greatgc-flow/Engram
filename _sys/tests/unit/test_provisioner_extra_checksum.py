"""_install_extra used to call the unguarded _download() (no redirect
governance, no checksum verification at all) while the main tool binary went
through _secure_download + hash check - a real bypass of the same governed
path (e.g. oh-my-posh's themes.zip). Now routes through _secure_download and
verifies a declared hash when present."""
import hashlib
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

SYS_DIR = Path(__file__).resolve().parent.parent.parent  # _sys/
sys.path.insert(0, str(SYS_DIR / "core"))
import provisioner as pv  # noqa: E402


def _make_zip(path: Path, content: bytes = b"fixture") -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("file.txt", content)


def test_install_extra_uses_secure_download_not_bare_download(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(pv, "_secure_download", lambda url, dest: (calls.append(url), _make_zip(dest))[-1])
    monkeypatch.setattr(pv, "_download", MagicMock(side_effect=AssertionError("must not use unguarded _download")))

    dest_dir = tmp_path / "dest"
    setup_dir = tmp_path / "setup"
    setup_dir.mkdir()

    pv._install_extra("mytool", {"url": "https://github.com/x/y/releases/download/v1/extra.zip", "type": "zip", "dest": "extra"}, dest_dir, setup_dir)

    assert calls == ["https://github.com/x/y/releases/download/v1/extra.zip"]
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
