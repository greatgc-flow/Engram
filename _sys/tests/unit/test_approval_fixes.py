"""Regression tests for the push-approval review (cc.deepthink BLOCK_PUSH, ag.pro follow-ups;
ratified in docs/design/engram-env-resilience-design-2026-10-02.md).
"""
import datetime
import json
import sys
from pathlib import Path

import pytest

from _sys.core.root import find_root

sys.path.insert(0, str(find_root(__file__)))
from core import backups, env_lock, tidy_temp, venv_manager  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
BOOTSTRAP = (REPO_ROOT / "_sys" / "core" / "bootstrap.bat").read_text(encoding="utf-8")


def _idx(needle, start=0):
    i = BOOTSTRAP.find(needle, start)
    assert i >= 0, needle
    return i


# ---- BLOCKER: a failed/garbage download must never become a "verified" cache -------------------------

def test_python_download_fails_on_http_errors():
    # curl without -f exits 0 on a 404/503/captive-portal page
    assert 'curl -fL "!PY_URL!"' in BOOTSTRAP
    assert 'curl -L "!PY_URL!"' not in BOOTSTRAP


def test_sha_record_is_written_only_after_the_zip_extracted_successfully():
    extract = _idx("Expand-Archive")
    record = _idx('>"!SHA_PATH!" echo')
    assert record > extract, "the .sha256 record must not exist before extraction succeeded"


def test_failed_extraction_removes_the_zip_and_its_record():
    extract = _idx("Expand-Archive")
    window = BOOTSTRAP[extract:extract + 700]
    assert 'del /q "!ZIP_PATH!"' in window and 'del /q "!SHA_PATH!"' in window


def test_declared_hash_also_gates_a_cached_zip():
    start = _idx('set "_CACHE_OK=0"')
    end = _idx("Using the verified cached Python zip")
    region = BOOTSTRAP[start:end]
    assert "PY_SHA256" in region and 'set "_CACHE_OK=0"' in region[region.index("PY_SHA256") - 200:]


def test_bootstrap_never_bumps_away_from_the_validated_pin():
    assert "_PY_BUMP" not in BOOTSTRAP
    assert "runtimes.python.version=" not in BOOTSTRAP


# ---- doctor semantics ------------------------------------------------------------------------------------

def test_doctor_comment_names_the_real_hard_gates():
    text = (REPO_ROOT / "_sys" / "core" / "doctor.py").read_text(encoding="utf-8")
    assert "venv" in text[text.index("environment-resilience checks"):text.index("def check_env_manifest")].lower()
    assert "hard gate" in text.lower()


# ---- sanitize_url ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "https://host/pkg.whl?access_token=abc",
    "https://host/pkg.whl?api_key=abc",
    "https://host/pkg.whl?private_token=abc",
    "https://host/pkg.whl?X-Amz-Security-Token=abc",
    "https://host/pkg.whl?client_secret=abc&x=1",
    "https://host/pkg.whl?sig=1&PASSWORD=abc",
])
def test_sanitize_url_drops_credential_style_query_params(url):
    out = venv_manager.sanitize_url(url)
    assert "abc" not in out and "?" not in out


def test_sanitize_url_keeps_harmless_queries():
    assert venv_manager.sanitize_url("https://host/p?version=1&arch=x64") == "https://host/p?version=1&arch=x64"


def test_sanitize_url_still_strips_userinfo():
    assert venv_manager.sanitize_url("https://user:tok@host/p") == "https://host/p"


# ---- malformed BACKUP.json timestamps must not crash tidy ------------------------------------------------------

@pytest.fixture
def sys_dir(tmp_path):
    d = tmp_path / "Engram" / "_sys"
    (d / "data" / "state").mkdir(parents=True)
    (d / "env").mkdir(parents=True)
    return d


def _src(tmp_path, name):
    d = tmp_path / "src" / name
    d.mkdir(parents=True)
    (d / "f.txt").write_text("x", encoding="utf-8")
    return d


def test_marker_with_an_unparsable_timestamp_is_reported_invalid_not_valid(sys_dir, tmp_path):
    ref = backups.create(sys_dir, "venv", _src(tmp_path, "a"), reason="r", op_id="o", label="l",
                         now="2026-10-01T00:00:00Z")
    meta = json.loads((ref.path / backups.MARKER).read_text(encoding="utf-8"))
    meta["created_at"] = "yesterday-ish"
    (ref.path / backups.MARKER).write_text(json.dumps(meta), encoding="utf-8")
    res = backups.scan(sys_dir)
    assert res.valid == [] and [p.name for p in res.invalid] == [ref.path.name]


def test_unparsable_committed_at_is_invalid_too(sys_dir, tmp_path):
    ref = backups.create(sys_dir, "venv", _src(tmp_path, "a"), reason="r", op_id="o", label="l",
                         now="2026-10-01T00:00:00Z")
    backups.commit(ref, now="2026-10-01T00:00:00Z")
    meta = json.loads((ref.path / backups.MARKER).read_text(encoding="utf-8"))
    meta["committed_at"] = "garbage"
    (ref.path / backups.MARKER).write_text(json.dumps(meta), encoding="utf-8")
    assert backups.scan(sys_dir).valid == []


def test_plan_retention_survives_a_ref_with_a_bad_timestamp(sys_dir, tmp_path):
    ref = backups.create(sys_dir, "venv", _src(tmp_path, "a"), reason="r", op_id="o", label="l",
                         now="2026-10-01T00:00:00Z")
    backups.commit(ref, now="2026-10-01T00:00:00Z")
    ref.meta["committed_at"] = "garbage"          # bypasses scan (e.g. a caller holding a stale ref)
    plan = backups.plan_retention([ref], now="2026-12-01T00:00:00Z")
    assert plan.delete == []
    assert any("timestamp" in reason for _, reason in plan.keep)


# ---- tidy: holds the env lock while it mutates backups; adopted dirs are not evicted in the same run -----------

@pytest.fixture
def tidy_env(sys_dir):
    base = sys_dir.parent
    saved = (tidy_temp.ROOT, tidy_temp._SYS_DIR)
    tidy_temp.configure_paths(root=base, sys_dir=sys_dir, explicit_sys_dir=True)
    yield base, sys_dir
    tidy_temp.configure_paths(root=saved[0], sys_dir=saved[1], explicit_sys_dir=False)


def _iso(days):
    t = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", ["tidy_temp.py", *argv])
    rc = tidy_temp.main()
    return rc, capsys.readouterr().out


def test_tidy_holds_the_env_lock_while_deleting_backups(tidy_env, tmp_path, monkeypatch, capsys):
    base, sys_dir = tidy_env
    old = backups.create(sys_dir, "venv", _src(tmp_path, "o"), reason="r", op_id="o", label="old", now=_iso(30))
    backups.commit(old, now=_iso(30))
    new = backups.create(sys_dir, "venv", _src(tmp_path, "n"), reason="r", op_id="o", label="new", now=_iso(1))
    backups.commit(new, now=_iso(1))
    seen = {}
    real_rm = tidy_temp._rm

    def spy(path, apply):
        if "backups" in str(path):
            seen["locked"] = env_lock.lock_path(sys_dir).exists()
        return real_rm(path, apply)

    monkeypatch.setattr(tidy_temp, "_rm", spy)
    _run(monkeypatch, capsys, "--only", "backups", "--apply")
    assert seen.get("locked") is True
    assert not env_lock.lock_path(sys_dir).exists()       # released afterwards
    assert not old.path.exists()


def test_tidy_dry_run_does_not_take_the_lock(tidy_env, tmp_path, monkeypatch, capsys):
    base, sys_dir = tidy_env
    seen = {}
    real_inspect = env_lock.inspect
    _run(monkeypatch, capsys, "--only", "backups")
    assert not env_lock.lock_path(sys_dir).exists()


def test_adopted_legacy_dirs_survive_the_size_cap_of_the_same_run(tidy_env, monkeypatch, capsys):
    base, sys_dir = tidy_env
    old = sys_dir / "env" / "git_old"
    (old / "cmd").mkdir(parents=True)
    (old / "cmd" / "git.exe").write_text("x" * 5000, encoding="utf-8")
    _run(monkeypatch, capsys, "--only", "backups", "--adopt-legacy", "--apply", "--max-size-gb", "0.0000001")
    kinds = [r.kind for r in backups.scan(sys_dir).valid]
    assert kinds == ["legacy-old"], "a dir adopted in this run must not be evicted by the same run's cap"
