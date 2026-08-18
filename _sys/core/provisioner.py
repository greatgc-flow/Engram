"""
provisioner.py - Binary installation for Portable Dev Environment.
All versions/URLs sourced from runtimes.json. No hardcoding.
"""
import datetime
import hashlib
import os
import re
import sys
import json
import shutil
import subprocess
import tarfile
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlparse


def _load_runtimes(sys_dir: Path) -> tuple[dict, dict, dict]:
    path = sys_dir / "runtimes.json"
    if not path.exists():
        raise FileNotFoundError(f"[Error] runtimes.json not found at {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"[Error] runtimes.json is not valid JSON: {exc}") from exc
    data = raw.get("runtimes", {})
    V = {
        "Python": data.get("python", {}).get("version", ""),
        "NodeJS": data.get("nodejs", {}).get("version", ""),
        "Git":    data.get("git",    {}).get("version", ""),
        "VSCode": data.get("vscode", {}).get("version", ""),
        "Pwsh":   data.get("pwsh",   {}).get("version", ""),
    }
    URLS = {
        "NodeJS": data.get("nodejs",  {}).get("url", ""),
        "Git":    data.get("git",     {}).get("url", ""),
        "VSCode": data.get("vscode",  {}).get("url", ""),
        "Pwsh":   data.get("pwsh",    {}).get("url", ""),
    }
    return V, URLS, raw.get("tools", {})


def _download(url: str, dest: Path, label: str) -> None:
    print(f"  [i] Downloading {label}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)
    print(f"  [OK] {dest.name} ({dest.stat().st_size / 1024**2:.1f} MB)")


def _archive_member_target(dest: Path, member_name: str) -> Path:
    normalized = member_name.replace("\\", "/")
    if (
        not normalized
        or normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized)
    ):
        raise ValueError(f"unsafe archive member path: {member_name!r}")
    target = (dest / normalized).resolve()
    root = dest.resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"archive member escapes extraction root: {member_name!r}")
    return target


def _validate_archive_members(archive_path: Path, dest: Path) -> None:
    if zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                _archive_member_target(dest, member.filename)
                unix_mode = (member.external_attr >> 16) & 0o170000
                if unix_mode == 0o120000:
                    raise ValueError(
                        f"archive symlink is not allowed: {member.filename!r}"
                    )
        return
    if tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path) as archive:
            for member in archive.getmembers():
                _archive_member_target(dest, member.name)
                if member.issym() or member.islnk():
                    raise ValueError(
                        f"archive link is not allowed: {member.name!r}"
                    )
        return
    raise ValueError(f"unsupported or invalid archive: {archive_path.name}")


def _extract(zip_path: Path, dest: Path) -> None:
    print(f"  [i] Extracting {zip_path.name}...")
    _validate_archive_members(zip_path, dest)
    if zipfile.is_zipfile(zip_path):
        shutil.unpack_archive(str(zip_path), str(dest), format="zip")
    elif tarfile.is_tarfile(zip_path):
        shutil.unpack_archive(str(zip_path), str(dest), format="gztar" if str(zip_path).endswith("gz") else "tar")
    else:
        shutil.unpack_archive(str(zip_path), str(dest))
    print(f"  [OK] Extracted to {dest.name}")


def _load_peers(sys_dir: Path) -> dict:
    p = sys_dir / "ai" / "peers.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8")).get("peers", {})
        except Exception:
            pass
    return {}


def _check_python_version(V: dict) -> None:
    running  = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    expected = V.get("Python", "")
    if expected and running != expected:
        print(f"  [!] Python 버전 불일치: 실행={running}, 기대={expected}")
    else:
        print(f"  [OK] Python {running}")


def _install_extra(tool_name: str, extra: dict, dest_dir: Path, setup_dir: Path) -> None:
    url       = extra.get("url", "")
    kind      = extra.get("type", "zip")
    subfolder = extra.get("dest", "extra")
    extra_dir = dest_dir / subfolder
    if not url:
        return
    if kind == "zip":
        zp = setup_dir / f"{tool_name}-extra-{subfolder}.zip"
        declared_algo = None
        declared_hash = None
        for algo in ("sha3_256", "sha512", "sha256"):
            if extra.get(algo):
                declared_algo = algo
                declared_hash = extra[algo]
                break
        if not declared_hash:
            raise ValueError(
                f"{tool_name}/{subfolder}: a declared digest is required"
            )

        setup_dir.mkdir(parents=True, exist_ok=True)
        part_path = setup_dir / f"{zp.name}.{uuid.uuid4().hex}.part"
        extract_stage = setup_dir / f"{zp.stem}.{uuid.uuid4().hex}.extracting"
        print(f"  [i] Downloading {tool_name}/{subfolder}...")
        try:
            metadata = _secure_download(url, part_path) or {}
            actual_length = part_path.stat().st_size
            expected_length = (
                extra.get("expected_length")
                if extra.get("expected_length") is not None
                else metadata.get("expected_length")
            )
            if expected_length is not None and actual_length != int(expected_length):
                raise ValueError(
                    f"{tool_name}/{subfolder}: length mismatch "
                    f"(expected {expected_length}, got {actual_length})"
                )
            downloaded_hash = _hash_file(part_path, declared_algo)
            if downloaded_hash != declared_hash:
                raise ValueError(
                    f"{tool_name}/{subfolder}: checksum mismatch "
                    f"(expected {declared_hash}, got {downloaded_hash})"
                )
            os.replace(part_path, zp)
            print(f"  [OK] {zp.name} ({zp.stat().st_size / 1024**2:.1f} MB)")
            extract_stage.mkdir(parents=True, exist_ok=False)
            _extract(zp, extract_stage)
            extra_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(extract_stage, extra_dir, dirs_exist_ok=True)
        finally:
            part_path.unlink(missing_ok=True)
            zp.unlink(missing_ok=True)
            shutil.rmtree(extract_stage, ignore_errors=True)
        print(f"  [OK] {tool_name}/{subfolder} ready")


def _default_sys_dir() -> Path:
    return Path(__file__).resolve().parent.parent


# ── D10: on-demand ensure-tool / ensure-peer-cli (auto-install/auto-update) ──
#
# `ensure_tool`/`ensure_peer_cli` are the ONLY mutating entry points. They are
# never called from `real_binary()` (check_cli_reality.py) — that resolver
# must stay a pure, non-mutating path resolver (PRO-19 / T15 invariant).

_LAZY_DRAINING = False

# Consecutive failed lazy drains for the same (peer_key, declared_version)
# before an npm_peer install stops being auto-retried (npm_install_failed).
MAX_NPM_INSTALL_RETRIES = 3


def _get_deferred_path(sys_dir: Path) -> Path:
    return sys_dir.parent / ".ai" / "tool_deferred_retries.json"


def _load_deferred(sys_dir: Path) -> dict:
    p = _get_deferred_path(sys_dir)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def _save_deferred(sys_dir: Path, data: dict) -> None:
    p = _get_deferred_path(sys_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _add_deferred(sys_dir: Path, name: str, kind: str) -> None:
    data = _load_deferred(sys_dir)
    data[f"{kind}:{name}"] = {"kind": kind, "name": name}
    _save_deferred(sys_dir, data)


def _remove_deferred(sys_dir: Path, name: str, kind: str) -> None:
    data = _load_deferred(sys_dir)
    key = f"{kind}:{name}"
    if key in data:
        del data[key]
        _save_deferred(sys_dir, data)


def _drain_deferred_lazy(orch: dict | None, sys_dir: Path, skip_kind: str | None = None, skip_name: str | None = None) -> None:
    """Opportunistically retry deferred (file-locked) installs. Primary
    mechanism is `ensure-tool --retry-deferred`; this is the lazy fallback
    that fires on any subsequent ensure_tool/ensure_peer_cli call. There is
    NO session-start hook in this codebase (verified: _sys/hooks/ has none) -
    do not assume one. `skip_kind`/`skip_name` exclude the entry the CALLER
    is about to process directly anyway - draining it here too would attempt
    the same install twice in one call and double-count retry attempts."""
    global _LAZY_DRAINING
    if _LAZY_DRAINING:
        return
    _LAZY_DRAINING = True
    try:
        data = _load_deferred(sys_dir)
        if not data:
            return
        remaining = {}
        to_process = []
        for key, val in data.items():
            if val.get("kind") == skip_kind and val.get("name") == skip_name:
                remaining[key] = val
                continue
            to_process.append(val)
        _save_deferred(sys_dir, remaining)
        for val in to_process:
            kind = val.get("kind")
            name = val.get("name")
            if kind == "tool":
                ensure_tool(name, orch, sys_dir)
            elif kind == "peer":
                ensure_peer_cli(name, orch, sys_dir)
            elif kind == "runtime":
                ensure_runtime(name, orch, sys_dir)
    finally:
        _LAZY_DRAINING = False


def _hash_file(path: Path, algo: str) -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _canon_hash(obj: dict) -> str:
    s = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()



# GitHub release assets 302 to a time-limited signed URL on GitHub's own
# release-asset CDN - a different host, but still GitHub's, not a third
# party. Narrow allowlist (exact source -> exact known targets only, not
# "any redirect is fine now") so a genuinely compromised/wrong mirror is
# still rejected. Both CDN hostnames observed in practice (varies by
# region/rollout); confirmed 2026-07-21 via direct redirect trace on
# github.com/BurntSushi/ripgrep, github.com/cli/cli, and
# github.com/JanDeDobbeleer/oh-my-posh release URLs.
_RELEASE_CDN_ALLOWLIST: dict[str, frozenset[str]] = {
    "github.com": frozenset({
        "objects.githubusercontent.com",
        "release-assets.githubusercontent.com",
    }),
    "update.code.visualstudio.com": frozenset({
        "vscode.download.prss.microsoft.com",
        "az764295.vo.msecnd.net",
    }),
}


class _SameHostRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Rejects cross-host redirects so a compromised/misconfigured mirror
    can't silently substitute a different origin mid-download - except a
    narrow allowlist for verified CDNs (see _RELEASE_CDN_ALLOWLIST)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        orig_host = urlparse(req.full_url).netloc
        new_host = urlparse(newurl).netloc
        if orig_host != new_host and new_host not in _RELEASE_CDN_ALLOWLIST.get(orig_host, frozenset()):
            raise urllib.error.URLError("Cross-host redirect rejected by governance gate.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _secure_download(url: str, dest_path: Path) -> dict:
    opener = urllib.request.build_opener(_SameHostRedirectHandler())
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with opener.open(req) as response, open(dest_path, "wb") as f:
        shutil.copyfileobj(response, f)
        f.flush()
        os.fsync(f.fileno())
        length_header = response.headers.get("Content-Length")
    try:
        expected_length = int(length_header) if length_header is not None else None
    except (TypeError, ValueError):
        expected_length = None
    return {
        "bytes_written": dest_path.stat().st_size,
        "expected_length": expected_length,
    }


def _flatten_zip_extract(extract_root: Path, active_root: Path) -> None:
    """Copy every *.exe found anywhere under extract_root up to the flat
    active_root layout (mirrors _install_tools' existing rglob-flatten so
    nested-folder release zips don't break canary/real_binary lookups)."""
    for exe in extract_root.rglob("*.exe"):
        shutil.copy2(str(exe), str(active_root / exe.name))


def _run_canary(tmp_dir: Path, canary: dict | None, env: dict | None = None) -> tuple[bool, str]:
    if not canary:
        return True, ""
    argv = canary.get("argv", [])
    if not argv:
        return True, ""
    timeout = canary.get("timeout_sec", 10)
    regex = canary.get("expect_regex")
    target = tmp_dir / argv[0]

    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    sys_dir = tmp_dir.parent.parent
    nodejs_dir = sys_dir / "env" / "nodejs"
    venv_scripts = sys_dir / "env" / "venv" / "Scripts"
    paths = [str(tmp_dir), str(nodejs_dir), str(venv_scripts), run_env.get("PATH", "")]
    run_env["PATH"] = os.pathsep.join(p for p in paths if p)

    if target.suffix.lower() in (".cmd", ".bat"):
        cmd_line = f'"{target}" ' + " ".join(f'"{a}"' if (" " in a or "&" in a) else a for a in argv[1:])
        use_shell = True
        run_args = cmd_line
    else:
        use_shell = False
        run_args = [str(target)] + list(argv[1:])

    try:
        res = subprocess.run(
            run_args,
            capture_output=True,
            timeout=timeout,
            env=run_env,
            shell=use_shell,
        )
        output = res.stdout.decode("utf-8", errors="replace") + res.stderr.decode("utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
    if regex and not re.search(regex, output):
        return False, f"expect_regex {regex!r} not matched in canary output: {output!r}"
    return True, output


def _copy_preserve_tree(src_dir: Path, dest_dir: Path, strip_components: int = 0) -> None:
    """Extract a zip's already-unpacked contents into dest_dir, preserving
    the internal directory structure and stripping `strip_components`
    leading path segments (e.g. strip_components=1 removes a release zip's
    single top-level wrapper folder like node-vX.Y.Z-win-x64/)."""
    for root, _, files in os.walk(src_dir):
        root_path = Path(root)
        for fname in files:
            file_path = root_path / fname
            rel_parts = file_path.relative_to(src_dir).parts
            if len(rel_parts) <= strip_components:
                continue
            target_path = dest_dir / Path(*rel_parts[strip_components:])
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(file_path), str(target_path))


def _migrate_preserve_paths(old_dir: Path, tmp_dir: Path, preserve_paths: list) -> None:
    """Move mutable-state subdirectories (e.g. nodejs's npm-global, which
    holds the installed claude/codex peer CLIs) from the OLD active dir into
    the staged tmp_dir before the atomic swap finalizes - otherwise a
    routine tool/runtime update silently destroys that state."""
    for rel in preserve_paths:
        src = old_dir / rel
        if not src.exists():
            continue
        dest = tmp_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True) if dest.is_dir() else dest.unlink()
        shutil.move(str(src), str(dest))


def _install_atomic(name: str, cfg: dict, manifest_path: Path, target_root: Path, sys_dir: Path, force: bool = False) -> dict:
    url = cfg.get("url")
    declared_version = cfg.get("version")
    if not url:
        return {"status": "error", "detail": f"{name}: no url declared in runtimes.json"}

    declared_algo = None
    declared_hash = None
    for algo in ("sha3_256", "sha512", "sha256"):
        if cfg.get(algo):
            declared_algo = algo
            declared_hash = cfg[algo]
            break

    tmp_dir = target_root / f"{name}_v{declared_version}_tmp"
    old_dir = target_root / f"{name}_old"
    target_root.mkdir(parents=True, exist_ok=True)

    if tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    dl_name = url.split("/")[-1] or "downloaded_file"
    dl_path = tmp_dir / dl_name

    try:
        try:
            _secure_download(url, dl_path)
        except Exception as e:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return {"status": "governance_required", "detail": f"Download rejected/failed: {e}"}

        hash_algo = declared_algo or "sha256"
        downloaded_hash = _hash_file(dl_path, hash_algo)
        checksum_source = "computed_tls_trust"
        checksum_verified = False

        if declared_hash:
            if downloaded_hash != declared_hash:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                return {"status": "governance_required", "detail": f"Checksum mismatch: expected {declared_hash}, got {downloaded_hash}"}
            checksum_source = "declared"
            checksum_verified = True

        mechanism = cfg.get("install_mechanism", "zip_tool")
        if mechanism == "zip_tool":
            extract_tmp = tmp_dir / "_extract"
            extract_tmp.mkdir(parents=True, exist_ok=True)
            _extract(dl_path, extract_tmp)
            dl_path.unlink(missing_ok=True)

            layout = cfg.get("archive_layout", "flatten_exes")
            if layout == "flatten_exes":
                _flatten_zip_extract(extract_tmp, tmp_dir)
            elif layout == "preserve_tree":
                strip = int(cfg.get("strip_components", 0))
                _copy_preserve_tree(extract_tmp, tmp_dir, strip)
            else:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                return {"status": "error", "detail": f"Unknown archive_layout {layout!r}"}

            shutil.rmtree(extract_tmp, ignore_errors=True)
        elif mechanism == "exe_tool":
            bin_name = cfg.get("bin", f"{name}.exe")
            if dl_path.name != bin_name:
                dl_path.rename(tmp_dir / bin_name)
        elif mechanism == "sfx_exe":
            try:
                subprocess.run([str(dl_path), f"-o{tmp_dir}", "-y"], check=True)
            except Exception as e:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                return {"status": "error", "detail": f"SFX extraction failed: {e}"}
            dl_path.unlink(missing_ok=True)
        else:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return {"status": "error", "detail": f"_install_atomic does not support mechanism {mechanism!r}"}

        setup_dir = sys_dir / "data" / "setup-files"
        for extra in cfg.get("extras", []):
            try:
                _install_extra(name, extra, tmp_dir, setup_dir)
            except Exception as e:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                return {"status": "error", "detail": f"Failed to install extra: {e}"}

        canary = cfg.get("canary")
        ok, canary_output = _run_canary(tmp_dir, canary)
        if not ok:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return {"status": "error", "detail": f"Canary failed: {canary_output}"}

        active_dir = target_root / name
        kind = "runtime" if target_root.name == "env" else "tool"
        if active_dir.exists():
            if old_dir.exists():
                shutil.rmtree(old_dir, ignore_errors=True)
            try:
                active_dir.rename(old_dir)
            except OSError as e:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                _add_deferred(sys_dir, name, kind)
                return {"status": "in_use_retry_at_session_boundary", "detail": f"Locked: {e}"}

            preserve_paths = cfg.get("preserve_paths") or []
            if preserve_paths:
                _migrate_preserve_paths(old_dir, tmp_dir, preserve_paths)

        try:
            tmp_dir.rename(active_dir)
        except OSError as e:
            if old_dir.exists() and not active_dir.exists():
                old_dir.rename(active_dir)
            return {"status": "error", "detail": f"Swap to active failed: {e}"}

        manifest = {
            "tool" if kind == "tool" else "runtime": name,
            "declared_version": declared_version,
            "url": url,
            "checksum_algo": hash_algo,
            "checksum_value": downloaded_hash,
            "checksum_source": checksum_source,
            "checksum_verified": checksum_verified,
            "canary_command": canary.get("argv", []) if canary else [],
            "canary_output": canary_output,
            "installed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source_config_hash": _canon_hash(cfg),
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        _remove_deferred(sys_dir, name, kind)

        return {"status": "success", "detail": "Installed successfully"}

    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return {"status": "error", "detail": str(e)}


def _already_current(dest_dir: Path, manifest_path: Path, cfg: dict, declared_version, bin_name: str | None, sys_dir: Path | None = None) -> bool:
    """Three-condition already-current check (D11-ratified): declared_version
    match, source_config_hash match (catches a URL/checksum/canary change
    with no version bump), and the installed binary still physically
    exists on disk (catches manual deletion)."""
    if not manifest_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if manifest.get("declared_version") != declared_version:
        return False
    if manifest.get("source_config_hash") != _canon_hash(cfg):
        return False
    if cfg.get("install_mechanism") == "pip_tool":
        target_sys = sys_dir or dest_dir.parent.parent
        if bin_name and not (target_sys / "env" / "venv" / "Scripts" / bin_name).exists():
            return False
    else:
        if bin_name and not (dest_dir / bin_name).exists():
            return False
    return True


def ensure_tool(name: str, orch: dict | None = None, sys_dir: Path | None = None, force: bool = False) -> dict:
    """Install `name` (a runtimes.json `tools` entry) if missing or stale.
    Read-only no-op if the manifest already matches the declared version."""
    sys_dir = sys_dir or _default_sys_dir()
    _drain_deferred_lazy(orch, sys_dir, skip_kind="tool", skip_name=name)

    _, _, TOOLS = _load_runtimes(sys_dir)
    cfg = TOOLS.get(name)
    if not cfg:
        return {"status": "error", "detail": f"Tool {name!r} not found in runtimes.json tools"}

    tools_dir = sys_dir / "tools"
    dest_dir = tools_dir / name
    manifest_path = dest_dir / ".install_manifest.json"

    declared_version = cfg.get("version")
    bin_name = cfg.get("bin", f"{name}.exe")
    if not force and _already_current(dest_dir, manifest_path, cfg, declared_version, bin_name, sys_dir=sys_dir):
        return {"status": "already_current", "detail": "Version matches manifest"}

    mechanism = cfg.get("install_mechanism", "zip_tool")
    if mechanism in ("zip_tool", "exe_tool", "sfx_exe"):
        return _install_atomic(name, cfg, manifest_path, tools_dir, sys_dir, force=force)
    if mechanism == "pip_tool":
        url = cfg.get("url")
        venv_py = sys_dir / "env" / "venv" / "Scripts" / "python.exe"
        if not venv_py.exists():
            return {"status": "error", "detail": f"venv interpreter not found at {venv_py}"}
        try:
            cmd = [str(venv_py), "-m", "pip", "install", url, "--no-deps", "--force-reinstall"]
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            manifest = {
                "tool": name,
                "declared_version": declared_version,
                "url": url,
                "installed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "source_config_hash": _canon_hash(cfg),
            }
            dest_dir.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            _remove_deferred(sys_dir, name, "tool")
            return {"status": "success", "detail": "Installed successfully via pip"}
        except subprocess.CalledProcessError as exc:
            return {"status": "error", "detail": f"pip install failed: {exc.stderr or exc}"}
    if mechanism == "npm_peer":
        return {"status": "error", "detail": f"{name!r} is install_mechanism=npm_peer; use ensure_peer_cli instead"}
    return {"status": "error", "detail": f"Unknown install_mechanism {mechanism!r}"}


def ensure_runtime(name: str, orch: dict | None = None, sys_dir: Path | None = None, force: bool = False) -> dict:
    """Install or update a base runtime (nodejs/git/vscode/pwsh) from
    runtimes.json's `runtimes` dict. Python is a special bootstrap-only case:
    it cannot swap the interpreter it's currently running under."""
    sys_dir = sys_dir or _default_sys_dir()

    if name == "nodejs" and not force and _is_peer_leased(sys_dir, "nodejs"):
        _add_deferred(sys_dir, name, "runtime")
        return {"status": "in_use_deferred", "detail": "Node.js is currently leased by an active peer session."}

    _drain_deferred_lazy(orch, sys_dir, skip_kind="runtime", skip_name=name)

    path = sys_dir / "runtimes.json"
    if not path.exists():
        return {"status": "error", "detail": f"runtimes.json not found at {path}"}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return {"status": "error", "detail": f"Failed to load runtimes.json: {e}"}

    runtimes = raw.get("runtimes", {})
    cfg = runtimes.get(name)
    if not cfg:
        return {"status": "error", "detail": f"Runtime {name!r} not found in runtimes.json runtimes"}

    env_dir = sys_dir / "env"
    dest_dir = env_dir / name
    manifest_path = dest_dir / ".install_manifest.json"
    declared_version = cfg.get("version")

    if name == "python":
        running_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        if running_version == declared_version:
            manifest = {
                "runtime": "python",
                "declared_version": declared_version,
                "installed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "source_config_hash": _canon_hash(cfg),
                "detail": "Running interpreter matches declared version",
            }
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            return {"status": "already_current", "detail": "Python version matches running interpreter"}
        return {
            "status": "error",
            "detail": f"Python version mismatch (running={running_version}, declared={declared_version}). "
                      f"Python must be updated via INSTALL.bat's own bootstrap mechanism, not ensure_runtime.",
        }

    cfg = dict(cfg)
    if name == "nodejs":
        cfg.setdefault("install_mechanism", "zip_tool")
        cfg.setdefault("archive_layout", "preserve_tree")
        cfg.setdefault("strip_components", 1)
        cfg.setdefault("preserve_paths", ["npm-global"])
        bin_name = "node.exe"
    elif name == "git":
        cfg.setdefault("install_mechanism", "sfx_exe")
        bin_name = None  # git.exe lives under cmd/ or bin/, checked below
    elif name == "vscode":
        cfg.setdefault("install_mechanism", "zip_tool")
        cfg.setdefault("archive_layout", "preserve_tree")
        cfg.setdefault("strip_components", 0)
        bin_name = "Code.exe"
    elif name == "pwsh":
        cfg.setdefault("install_mechanism", "zip_tool")
        cfg.setdefault("archive_layout", "preserve_tree")
        cfg.setdefault("strip_components", 0)
        bin_name = "pwsh.exe"
    else:
        bin_name = cfg.get("bin")

    if not force and _already_current(dest_dir, manifest_path, cfg, declared_version, bin_name):
        return {"status": "already_current", "detail": "Version matches manifest"}
    if not force and name == "git" and manifest_path.exists():
        # git.exe's exact subpath varies (cmd/ vs bin/); fall back to a
        # path-agnostic existence check for the already-current fast path.
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if (manifest.get("declared_version") == declared_version
                    and manifest.get("source_config_hash") == _canon_hash(cfg)
                    and ((dest_dir / "cmd" / "git.exe").exists() or (dest_dir / "bin" / "git.exe").exists())):
                return {"status": "already_current", "detail": "Version matches manifest"}
        except (OSError, json.JSONDecodeError):
            pass

    mechanism = cfg.get("install_mechanism", "zip_tool")
    if mechanism in ("zip_tool", "exe_tool", "sfx_exe"):
        return _install_atomic(name, cfg, manifest_path, env_dir, sys_dir, force=force)
    return {"status": "error", "detail": f"Unknown install_mechanism {mechanism!r} for runtime {name!r}"}


def _is_peer_leased(sys_dir: Path, peer_or_tool: str) -> bool:
    """True if .ai/leases.json (hub.py's active-session lease tracker) has a
    currently-open, non-expired lease matching peer_or_tool. "nodejs" is
    treated as leased if ANY peer has an open lease, since all npm-based
    peer CLIs live inside nodejs's own npm-global directory. Lease schema
    (hub.py's _lease_open/_lease_close): keyed by lease_id (uuid4, T83),
    each entry's "peer_id" field is what matches peer_or_tool here; other
    fields include status ("open" while active), expires_at (naive local-time string,
    "%Y-%m-%dT%H:%M:%S" - hub.py's _now() uses datetime.now(), no tz)."""
    leases_path = sys_dir.parent / ".ai" / "leases.json"
    if not leases_path.exists():
        return False
    try:
        leases = json.loads(leases_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    now = datetime.datetime.now()
    for lease in leases.values():
        if not isinstance(lease, dict) or lease.get("status") != "open":
            continue
        # T83: leases.json is keyed by lease_id (uuid), not peer_id -- match by
        # entry["peer_id"], never the dict key.
        if peer_or_tool != "nodejs" and lease.get("peer_id") != peer_or_tool:
            continue
        expires_at = lease.get("expires_at")
        if not expires_at:
            continue
        try:
            if datetime.datetime.fromisoformat(expires_at) > now:
                return True
        except ValueError:
            continue
    return False


def _resolve_peer_key(peers: dict, peer: str) -> str | None:
    """peers.json's own top-level keys (claude/codex/antigravity) are the
    SSOT for peer install config. `peer` may be given as that key OR as any
    of its declared node_ids (cc/ca, cx, ag)."""
    if peer in peers:
        return peer
    for key, cfg in peers.items():
        if peer in (cfg.get("node_ids") or []):
            return key
    return None


def ensure_peer_cli(peer: str, orch: dict | None = None, sys_dir: Path | None = None, force: bool = False) -> dict:
    """Install a peer CLI if missing, or update it if runtimes.json's pinned
    version changed. `peer` may be a peers.json key (claude/codex/
    antigravity) or a node_id (cc/cx/ag/...). npm-backed peers (npm_package
    set in peers.json) are version-pinned via runtimes.json's tools entry of
    the same key; native-binary peers (e.g. antigravity/agy) delegate to
    ensure_tool for the matching runtimes.json tools entry."""
    sys_dir = sys_dir or _default_sys_dir()

    peers = _load_peers(sys_dir)
    peer_key = _resolve_peer_key(peers, peer)
    if not peer_key:
        return {"status": "error", "detail": f"Peer {peer!r} not found in peers.json"}
    _drain_deferred_lazy(orch, sys_dir, skip_kind="peer", skip_name=peer_key)
    peer_cfg = peers[peer_key]

    native = peer_cfg.get("native_binary")
    if native:
        tool_key = Path(native.get("install_subdir", f"tools/{peer_key}")).name
        _, _, TOOLS = _load_runtimes(sys_dir)
        if tool_key not in TOOLS:
            return {"status": "error", "detail": f"native_binary tool {tool_key!r} not found in runtimes.json tools"}
        return ensure_tool(tool_key, orch, sys_dir, force=force)

    pkg = peer_cfg.get("npm_package")
    if not pkg:
        return {"status": "error", "detail": f"Peer {peer_key!r} has neither native_binary nor npm_package"}

    _, _, TOOLS = _load_runtimes(sys_dir)
    tool_cfg = TOOLS.get(peer_key, {})
    declared_version = tool_cfg.get("version")
    if not declared_version:
        return {"status": "error", "detail": f"No version declared in runtimes.json tools[{peer_key!r}]; add it before bootstrapping"}

    deferred_data = _load_deferred(sys_dir)
    retry_entry = deferred_data.get(f"peer:{peer_key}", {})
    if (not force and retry_entry.get("version") == declared_version
            and retry_entry.get("attempts", 0) >= MAX_NPM_INSTALL_RETRIES):
        return {"status": "error", "detail": f"npm_install_failed: exceeded {MAX_NPM_INSTALL_RETRIES} attempts for {declared_version}"}

    env_dir = sys_dir / "env"
    node_exe = env_dir / "nodejs" / "node.exe"
    if not node_exe.exists():
        return {"status": "error", "detail": "Node.js not installed; run provisioner deploy for nodejs first"}

    npm_global = env_dir / "nodejs" / "npm-global"
    peer_cmd = npm_global / f"{peer_key}.cmd"

    manifest_path = sys_dir / "tools" / peer_key / ".install_manifest.json"
    old_version = None
    is_update = manifest_path.exists()
    if is_update:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            old_version = manifest.get("declared_version")
            if (not force and old_version == declared_version
                    and manifest.get("source_config_hash") == _canon_hash(tool_cfg)
                    and peer_cmd.exists()):
                return {"status": "already_current", "detail": "Version matches manifest"}
        except (OSError, json.JSONDecodeError):
            pass

        if not force and _is_peer_leased(sys_dir, peer_key):
            _add_deferred(sys_dir, peer_key, "peer")
            return {"status": "in_use_deferred", "detail": f"Peer {peer_key} is currently leased."}

    npm_exe = env_dir / "nodejs" / "npm.cmd"
    try:
        res = subprocess.run(
            [str(npm_exe), "view", f"{pkg}@{declared_version}", "dist.integrity", "--json"],
            capture_output=True, text=True, check=True,
        )
        integrity = json.loads(res.stdout.strip())
    except Exception as e:
        return {"status": "error", "detail": f"Failed to fetch registry integrity: {e}"}

    npm_global.mkdir(parents=True, exist_ok=True)
    npm_env = os.environ.copy()
    npm_env["NPM_CONFIG_PREFIX"] = str(npm_global)
    npm_env["NPM_CONFIG_CACHE"] = str(env_dir / "nodejs" / "npm-cache")
    npm_env["PATH"] = str(env_dir / "nodejs") + os.pathsep + npm_env.get("PATH", "")

    try:
        subprocess.run(
            [str(npm_exe), "install", "-g", f"{pkg}@{declared_version}"],
            env=npm_env, check=True,
        )
    except subprocess.CalledProcessError as e:
        attempts = retry_entry.get("attempts", 0) + 1 if retry_entry.get("version") == declared_version else 1
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        entry = {
            "kind": "peer",
            "name": peer_key,
            "version": declared_version,
            "attempts": attempts,
            "first_failed_at": retry_entry.get("first_failed_at") if retry_entry.get("version") == declared_version else now_iso,
            "last_failed_at": now_iso,
            "last_exit_code": e.returncode,
        }
        deferred_data[f"peer:{peer_key}"] = entry
        _save_deferred(sys_dir, deferred_data)
        if attempts >= MAX_NPM_INSTALL_RETRIES:
            return {"status": "npm_install_failed", "detail": f"npm install failed {attempts} times for {declared_version} (exit code {e.returncode})"}
        return {"status": "npm_install_retry_deferred", "detail": f"npm install failed (exit code {e.returncode}), attempt {attempts}/{MAX_NPM_INSTALL_RETRIES}"}

    if peer_key == "claude":
        claude_pkg_dir = npm_global / "node_modules" / "@anthropic-ai" / "claude-code"
        bin_dir = claude_pkg_dir / "bin"
        bin_exe = bin_dir / "claude.exe"
        native_exe = claude_pkg_dir / "node_modules" / "@anthropic-ai" / "claude-code-win32-x64" / "claude.exe"
        if not bin_exe.exists():
            bin_dir.mkdir(parents=True, exist_ok=True)
            if native_exe.exists():
                shutil.copy2(str(native_exe), str(bin_exe))
            else:
                install_cjs = claude_pkg_dir / "install.cjs"
                if install_cjs.exists():
                    subprocess.run([str(node_exe), str(install_cjs)], cwd=str(claude_pkg_dir), env=npm_env, capture_output=True)

    canary = tool_cfg.get("canary")
    ok, canary_output = _run_canary(npm_global, canary, env=npm_env)
    if not ok:
        if is_update and old_version and old_version != declared_version:
            try:
                subprocess.run(
                    [str(npm_exe), "install", "-g", f"{pkg}@{old_version}"],
                    env=npm_env, check=True,
                )
                rb_ok, _rb_out = _run_canary(npm_global, canary, env=npm_env)
                if rb_ok:
                    return {"status": "error", "detail": f"Canary failed for {declared_version}, rolled back to {old_version}: {canary_output}"}
            except subprocess.CalledProcessError:
                pass
        return {"status": "npm_canary_failed", "detail": f"Canary failed: {canary_output}"}

    manifest = {
        "tool": peer_key,
        "declared_version": declared_version,
        "url": f"npm:{pkg}",
        "checksum_algo": "npm_integrity",
        "checksum_value": integrity,
        "checksum_source": "registry_integrity",
        "checksum_verified": True,
        "canary_command": canary.get("argv", []) if canary else [],
        "canary_output": canary_output,
        "installed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_config_hash": _canon_hash(tool_cfg),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _remove_deferred(sys_dir, peer_key, "peer")
    return {"status": "success", "detail": "Installed successfully"}


_DEPLOY_SUCCESS_STATUSES = {"success", "already_current"}
_DEPLOY_DEFERRED_STATUSES = {
    "in_use_retry_at_session_boundary",
    "in_use_deferred",
    "npm_install_retry_deferred",
}


def _runtime_postcondition(sys_dir: Path, name: str, cfg: dict) -> bool:
    runtime_dir = sys_dir / "env" / name
    expected = {
        "python": [runtime_dir / "python.exe"],
        "nodejs": [runtime_dir / "node.exe"],
        "git": [runtime_dir / "cmd" / "git.exe", runtime_dir / "bin" / "git.exe"],
        "vscode": [runtime_dir / "Code.exe"],
        "pwsh": [runtime_dir / "pwsh.exe"],
    }.get(name)
    if expected is None:
        bin_name = cfg.get("bin")
        expected = [runtime_dir / bin_name] if bin_name else [runtime_dir / ".install_manifest.json"]
    return any(path.exists() for path in expected)


def _tool_postcondition(sys_dir: Path, name: str, cfg: dict) -> bool:
    if cfg.get("install_mechanism") == "pip_tool":
        bin_name = cfg.get("bin", f"{name}.exe")
        return (sys_dir / "env" / "venv" / "Scripts" / bin_name).exists()
    bin_name = cfg.get("bin", f"{name}.exe")
    return (sys_dir / "tools" / name / bin_name).exists()


def _peer_postcondition(sys_dir: Path, peer_id: str, cfg: dict) -> bool:
    native = cfg.get("native_binary")
    if native:
        install_subdir = native.get("install_subdir", f"tools/{peer_id}")
        bin_name = native.get("win_exe") or native.get("bin_name") or f"{peer_id}.exe"
        return (sys_dir / install_subdir / bin_name).exists()
    return (sys_dir / "env" / "nodejs" / "npm-global" / f"{peer_id}.cmd").exists()


def _record_deploy_outcome(
    component: str,
    result: dict,
    postcondition_ok: bool,
    installed: list[str],
    deferred: list[dict],
    failed: list[dict],
) -> None:
    status = result.get("status", "error") if isinstance(result, dict) else "error"
    detail = result.get("detail", "missing result") if isinstance(result, dict) else "invalid result"
    if status in _DEPLOY_SUCCESS_STATUSES:
        if postcondition_ok:
            installed.append(component)
            print(f"  [OK] {component} ({status})")
        else:
            failure = {
                "component": component,
                "status": "postcondition_failed",
                "detail": "installer reported success but the expected installed path is absent",
            }
            failed.append(failure)
            print(f"  [!] {component} failed: {failure['detail']}")
    elif status in _DEPLOY_DEFERRED_STATUSES:
        deferred.append({"component": component, "status": status, "detail": detail})
        print(f"  [~] {component} deferred: {detail}")
    else:
        failed.append({"component": component, "status": status, "detail": detail})
        print(f"  [!] {component} failed: {detail}")


def deploy(ctx: dict) -> dict:
    """Install all runtimes, tools, and AI peer CLIs via ensure_runtime/
    ensure_tool/ensure_peer_cli - every entry in runtimes.json/peers.json is
    manifest-tracked and update-aware (D11), not just install-if-missing."""
    args       = ctx["args"]
    force      = "--force" in args
    skip_vsc   = "--skip-vscode" in args
    skip_ai    = "--skip-ai" in args or "--skip-claude" in args
    sys_dir    = ctx["sys_dir"]
    base_dir   = ctx["base_dir"]
    env_dir    = sys_dir / "env"
    setup_dir  = sys_dir / "data" / "setup-files"
    setup_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n>>> Starting Provisioner (force={force})")
    V, URLS, TOOLS = _load_runtimes(sys_dir)
    peers = _load_peers(sys_dir)
    _check_python_version(V)

    # ── Folder structure ─────────────────────────────────────────
    print("\n>>> Folder structure")
    dirs = [
        env_dir / "python", env_dir / "nodejs",
        env_dir / "git", env_dir / "vscode", env_dir / "venv", env_dir / "pwsh",
        sys_dir / "tools" / "apps",
        sys_dir / "data" / "logs", sys_dir / "data" / "temp",
        sys_dir / "data" / "state", sys_dir / "data" / "generated",
        base_dir / "workspace",
        sys_dir / "ai" / "common" / "agents",
        sys_dir / "ai" / "common" / "skills",
        sys_dir / "ai" / "common" / "mcp",
        sys_dir / "common" / "scripts",
        sys_dir / "common" / "assets",
    ]
    for peer_id, cfg in peers.items():
        sub = sys_dir / cfg.get("sys_subdir", peer_id)
        dirs += [sub / "config", sub / "project"]
        if cfg.get("sys_subdir"):
            dirs.append(sub / "templates")
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    print("  [OK] Folder structure ready")

    installed = []
    deferred = []
    failed = []

    # ── Base runtimes (python/nodejs/git/vscode/pwsh) ─────────────
    print("\n>>> Base runtimes")
    try:
        raw = json.loads((sys_dir / "runtimes.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"[Error] runtimes.json is not valid JSON: {exc}") from exc
    for rt_name in raw.get("runtimes", {}).keys():
        if skip_vsc and rt_name == "vscode":
            continue
        res = ensure_runtime(rt_name, sys_dir=sys_dir, force=force)
        _record_deploy_outcome(
            rt_name,
            res,
            _runtime_postcondition(sys_dir, rt_name, raw["runtimes"][rt_name]),
            installed,
            deferred,
            failed,
        )

    # ── Python venv (not an immutable vendor binary - stays procedural) ──
    print("\n>>> Python venv")
    venv_py = env_dir / "venv" / "Scripts" / "python.exe"
    venv_creation_failed = False
    if force or not venv_py.exists():
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "virtualenv", "--quiet"], check=True)
            subprocess.run([sys.executable, "-m", "virtualenv", str(env_dir / "venv")], check=True)
            print("  [OK] venv created")
        except (subprocess.CalledProcessError, OSError) as exc:
            venv_creation_failed = True
            print(f"  [Fail] venv creation failed: {exc}")
            failed.append({
                "component": "venv",
                "status": "error",
                "detail": f"venv creation failed: {exc}",
            })
    else:
        print("  [--] venv (already exists)")
    # Re-check on disk rather than trusting the exit code above: creation can
    # report success without actually leaving a working interpreter behind.
    if venv_py.exists():
        for pkg in ["filelock", "pywinpty"]:
            try:
                subprocess.run([str(venv_py), "-m", "pip", "install", pkg, "--quiet"], check=True)
                print(f"  [OK] {pkg} installed")
            except (subprocess.CalledProcessError, OSError) as exc:
                print(f"  [Fail] {pkg} install failed: {exc}")
                failed.append({
                    "component": pkg,
                    "status": "error",
                    "detail": f"pip install {pkg} failed: {exc}",
                })
    if venv_py.exists():
        installed.append("venv")
    elif not venv_creation_failed:
        failed.append({
            "component": "venv",
            "status": "postcondition_failed",
            "detail": "virtualenv command completed but the venv interpreter is absent",
        })

    # ── CLI Tools ────────────────────────────────────────────────
    print("\n>>> CLI Tools")
    for tool_name, tool_cfg in TOOLS.items():
        if tool_cfg.get("install_mechanism") == "npm_peer":
            continue  # installed via the AI Peer CLIs loop below instead
        if skip_ai and tool_cfg.get("install_mechanism") == "exe_tool" and any(
            peer_cfg.get("native_binary", {}).get("install_subdir", "").endswith(f"/{tool_name}")
            for peer_cfg in peers.values()
        ):
            continue  # e.g. agy: a peer CLI's native binary, skip under --skip-ai too
        res = ensure_tool(tool_name, sys_dir=sys_dir, force=force)
        _record_deploy_outcome(
            tool_name,
            res,
            _tool_postcondition(sys_dir, tool_name, tool_cfg),
            installed,
            deferred,
            failed,
        )

    # ── AI Peer CLIs ─────────────────────────────────────────────
    if not skip_ai:
        print("\n>>> AI Peer CLIs")
        for peer_id, cfg in peers.items():
            if not cfg.get("enabled"):
                continue
            res = ensure_peer_cli(peer_id, sys_dir=sys_dir, force=force)
            _record_deploy_outcome(
                peer_id,
                res,
                _peer_postcondition(sys_dir, peer_id, cfg),
                installed,
                deferred,
                failed,
            )

    ctx["state"]["installed"] = installed
    ctx["state"]["deferred"] = deferred
    ctx["state"]["failed"] = failed
    print("\n======================================================")
    if failed:
        print(f"  Provisioner incomplete: {len(failed)} failed, {len(deferred)} deferred.")
    elif deferred:
        print(f"  Provisioner complete with {len(deferred)} deferred component(s).")
    else:
        print("  Provisioner complete.")
    print("======================================================")
    return {
        "status": "failed" if failed else ("deferred" if deferred else "success"),
        "installed": installed,
        "deferred": deferred,
        "failed": failed,
    }


def _exit_code(res: dict) -> int:
    status = res.get("status")
    if status in ("success", "already_current", "deferred"):
        return 0
    if status in ("in_use_retry_at_session_boundary", "in_use_deferred", "npm_install_retry_deferred"):
        return 3
    if "Checksum mismatch" in res.get("detail", ""):
        return 2
    return 1


def _cli_ensure_tool(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="provisioner.py ensure-tool")
    parser.add_argument("name", nargs="?", help="Name of the runtimes.json tools entry to ensure")
    parser.add_argument("--force", action="store_true", help="Bypass the already-current fast path")
    parser.add_argument("--retry-deferred", action="store_true", help="Drain the deferred-retry queue and exit")
    args = parser.parse_args(argv)

    sys_dir = _default_sys_dir()
    if args.retry_deferred:
        global _LAZY_DRAINING
        _LAZY_DRAINING = False
        _drain_deferred_lazy(None, sys_dir)
        print(json.dumps({"status": "drained"}))
        return 0

    if not args.name:
        parser.error("name is required unless --retry-deferred is given")

    res = ensure_tool(args.name, sys_dir=sys_dir, force=args.force)
    print(json.dumps(res, indent=2))
    return _exit_code(res)


def _cli_ensure_runtime(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="provisioner.py ensure-runtime")
    parser.add_argument("name", help="Name of the runtimes.json runtimes entry to ensure")
    parser.add_argument("--force", action="store_true", help="Bypass the already-current fast path")
    args = parser.parse_args(argv)

    sys_dir = _default_sys_dir()
    res = ensure_runtime(args.name, sys_dir=sys_dir, force=args.force)
    print(json.dumps(res, indent=2))
    return _exit_code(res)


def _cli_ensure_peer_cli(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="provisioner.py ensure-peer-cli")
    parser.add_argument("peer", help="peers.json key or node_id of the peer CLI to ensure")
    parser.add_argument("--force", action="store_true", help="Bypass the already-current fast path")
    args = parser.parse_args(argv)

    sys_dir = _default_sys_dir()
    res = ensure_peer_cli(args.peer, sys_dir=sys_dir, force=args.force)
    print(json.dumps(res, indent=2))
    return _exit_code(res)


if __name__ == "__main__":
    import argparse
    import traceback

    if len(sys.argv) > 1 and sys.argv[1] == "ensure-tool":
        sys.exit(_cli_ensure_tool(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "ensure-runtime":
        sys.exit(_cli_ensure_runtime(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "ensure-peer-cli":
        sys.exit(_cli_ensure_peer_cli(sys.argv[2:]))

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-vscode", action="store_true")
    parser.add_argument("--skip-ai", action="store_true")
    args, _ = parser.parse_known_args()

    # standalone run: build minimal ctx
    _sys = Path(__file__).parent.parent.resolve()
    ctx = {
        "base_dir": _sys.parent,
        "sys_dir":  _sys,
        "paths":    {"state": _sys / "data" / "state", "generated": _sys / "data" / "generated"},
        "args":     sys.argv[1:],
        "state":    {},
    }
    try:
        result = deploy(ctx)
        sys.exit(_exit_code(result))
    except Exception as e:
        print(f"\n[FATAL] {e}")
        traceback.print_exc()
        sys.exit(1)
