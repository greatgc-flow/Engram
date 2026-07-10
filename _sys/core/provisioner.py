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
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


def _load_runtimes(sys_dir: Path) -> tuple[dict, dict, dict]:
    path = sys_dir / "runtimes.json"
    if not path.exists():
        raise FileNotFoundError(f"[Error] runtimes.json not found at {path}")
    raw  = json.loads(path.read_text(encoding="utf-8"))
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
        "FFmpeg": data.get("ffmpeg",  {}).get("url", ""),
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


def _extract(zip_path: Path, dest: Path) -> None:
    print(f"  [i] Extracting {zip_path.name}...")
    try:
        shutil.unpack_archive(str(zip_path), str(dest))
    except Exception:
        subprocess.run(["tar", "-xf", str(zip_path), "-C", str(dest)], check=True)
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


def _install_tools(TOOLS: dict, env_dir: Path, setup_dir: Path, force: bool) -> list:
    installed = []
    if not TOOLS:
        print("  [--] No tools defined in runtimes.json")
        return installed
    tools_dir = env_dir.parent / "tools"
    for name, cfg in TOOLS.items():
        url      = cfg.get("url", "")
        kind     = cfg.get("type", "zip")
        bin_name = cfg.get("bin", f"{name}.exe")
        dest_dir = tools_dir / name
        dest_dir.mkdir(parents=True, exist_ok=True)
        sentinel = dest_dir / bin_name
        if not force and sentinel.exists():
            print(f"  [--] {name} (already installed)")
            installed.append(name)
            continue
        print(f"\n>>> Tool: {name} v{cfg.get('version', '?')}")
        if kind == "exe":
            dl = setup_dir / f"{name}-dl.exe"
            _download(url, dl, name)
            shutil.copy2(str(dl), str(sentinel))
            dl.unlink()
        else:
            zp = setup_dir / f"{name}.zip"
            _download(url, zp, name)
            tmp = setup_dir / f"_{name}_tmp"
            tmp.mkdir(exist_ok=True)
            _extract(zp, tmp)
            for exe in tmp.rglob("*.exe"):
                shutil.copy2(str(exe), str(dest_dir / exe.name))
            shutil.rmtree(tmp)
            zp.unlink(missing_ok=True)
        for extra in cfg.get("extras", []):
            _install_extra(name, extra, dest_dir, setup_dir)
        installed.append(name)
        print(f"  [OK] {name} ready")
    return installed


def _install_extra(tool_name: str, extra: dict, dest_dir: Path, setup_dir: Path) -> None:
    url       = extra.get("url", "")
    kind      = extra.get("type", "zip")
    subfolder = extra.get("dest", "extra")
    extra_dir = dest_dir / subfolder
    if not url:
        return
    extra_dir.mkdir(parents=True, exist_ok=True)
    if kind == "zip":
        zp = setup_dir / f"{tool_name}-extra-{subfolder}.zip"
        _download(url, zp, f"{tool_name}/{subfolder}")
        _extract(zp, extra_dir)
        zp.unlink(missing_ok=True)
        print(f"  [OK] {tool_name}/{subfolder} ready")


def _install_ai_peers(peers: dict, npm_exe: Path, npm_global: Path, env: dict, force: bool) -> list:
    installed = []
    for peer_id, cfg in peers.items():
        if not cfg.get("enabled"):
            continue
        pkg = cfg.get("npm_package")
        if not pkg:
            continue
        print(f"\n>>> AI Peer: {cfg.get('description', peer_id)}")
        peer_cmd = npm_global / f"{peer_id}.cmd"
        if force or not peer_cmd.exists():
            subprocess.run([str(npm_exe), "install", "-g", pkg], env=env, check=True)
            print(f"  [OK] {peer_id} CLI ready")
        else:
            print(f"  [--] {peer_id} CLI (already installed)")
        installed.append(peer_id)
    return installed


def _default_sys_dir() -> Path:
    return Path(__file__).resolve().parent.parent


# ── D10: on-demand ensure-tool / ensure-peer-cli (auto-install/auto-update) ──
#
# `ensure_tool`/`ensure_peer_cli` are the ONLY mutating entry points. They are
# never called from `real_binary()` (check_cli_reality.py) — that resolver
# must stay a pure, non-mutating path resolver (PRO-19 / T15 invariant).

_LAZY_DRAINING = False


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


def _drain_deferred_lazy(orch: dict | None, sys_dir: Path) -> None:
    """Opportunistically retry deferred (file-locked) installs. Primary
    mechanism is `ensure-tool --retry-deferred`; this is the lazy fallback
    that fires on any subsequent ensure_tool/ensure_peer_cli call. There is
    NO session-start hook in this codebase (verified: _sys/hooks/ has none) -
    do not assume one."""
    global _LAZY_DRAINING
    if _LAZY_DRAINING:
        return
    _LAZY_DRAINING = True
    try:
        data = _load_deferred(sys_dir)
        if not data:
            return
        _save_deferred(sys_dir, {})
        for val in data.values():
            kind = val.get("kind")
            name = val.get("name")
            if kind == "tool":
                ensure_tool(name, orch, sys_dir)
            elif kind == "peer":
                ensure_peer_cli(name, orch, sys_dir)
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


class _SameHostRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Rejects cross-host redirects so a compromised/misconfigured mirror
    can't silently substitute a different origin mid-download."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        orig_host = urlparse(req.full_url).netloc
        new_host = urlparse(newurl).netloc
        if orig_host != new_host:
            raise urllib.error.URLError("Cross-host redirect rejected by governance gate.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _secure_download(url: str, dest_path: Path) -> None:
    opener = urllib.request.build_opener(_SameHostRedirectHandler())
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with opener.open(req) as response, open(dest_path, "wb") as f:
        shutil.copyfileobj(response, f)


def _flatten_zip_extract(extract_root: Path, active_root: Path) -> None:
    """Copy every *.exe found anywhere under extract_root up to the flat
    active_root layout (mirrors _install_tools' existing rglob-flatten so
    nested-folder release zips don't break canary/real_binary lookups)."""
    for exe in extract_root.rglob("*.exe"):
        shutil.copy2(str(exe), str(active_root / exe.name))


def _run_canary(tmp_dir: Path, canary: dict | None) -> tuple[bool, str]:
    if not canary:
        return True, ""
    argv = canary.get("argv", [])
    if not argv:
        return True, ""
    timeout = canary.get("timeout_sec", 5)
    regex = canary.get("expect_regex")
    full_argv = [str(tmp_dir / argv[0])] + list(argv[1:])
    try:
        res = subprocess.run(full_argv, capture_output=True, text=True, timeout=timeout)
        output = (res.stdout or "") + (res.stderr or "")
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
    if regex and not re.search(regex, output):
        return False, f"expect_regex {regex!r} not matched in canary output: {output!r}"
    return True, output


def _install_atomic(name: str, cfg: dict, manifest_path: Path, tools_dir: Path, sys_dir: Path) -> dict:
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

    tmp_dir = tools_dir / f"{name}_v{declared_version}_tmp"
    old_dir = tools_dir / f"{name}_old"
    tools_dir.mkdir(parents=True, exist_ok=True)

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
            _flatten_zip_extract(extract_tmp, tmp_dir)
            shutil.rmtree(extract_tmp, ignore_errors=True)
        elif mechanism == "exe_tool":
            bin_name = cfg.get("bin", f"{name}.exe")
            if dl_path.name != bin_name:
                dl_path.rename(tmp_dir / bin_name)
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

        active_dir = tools_dir / name
        if active_dir.exists():
            if old_dir.exists():
                shutil.rmtree(old_dir, ignore_errors=True)
            try:
                active_dir.rename(old_dir)
            except OSError as e:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                _add_deferred(sys_dir, name, "tool")
                return {"status": "in_use_retry_at_session_boundary", "detail": f"Locked: {e}"}

        try:
            tmp_dir.rename(active_dir)
        except OSError as e:
            if old_dir.exists() and not active_dir.exists():
                old_dir.rename(active_dir)
            return {"status": "error", "detail": f"Swap to active failed: {e}"}

        manifest = {
            "tool": name,
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
        _remove_deferred(sys_dir, name, "tool")

        return {"status": "success", "detail": "Installed successfully"}

    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return {"status": "error", "detail": str(e)}


def ensure_tool(name: str, orch: dict | None = None, sys_dir: Path | None = None) -> dict:
    """Install `name` (a runtimes.json `tools` entry) if missing or stale.
    Read-only no-op if the manifest already matches the declared version."""
    sys_dir = sys_dir or _default_sys_dir()
    _drain_deferred_lazy(orch, sys_dir)

    _, _, TOOLS = _load_runtimes(sys_dir)
    cfg = TOOLS.get(name)
    if not cfg:
        return {"status": "error", "detail": f"Tool {name!r} not found in runtimes.json tools"}

    tools_dir = sys_dir / "tools"
    dest_dir = tools_dir / name
    manifest_path = dest_dir / ".install_manifest.json"

    declared_version = cfg.get("version")
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("declared_version") == declared_version:
                return {"status": "already_current", "detail": "Version matches manifest"}
        except (OSError, json.JSONDecodeError):
            pass

    mechanism = cfg.get("install_mechanism", "zip_tool")
    if mechanism in ("zip_tool", "exe_tool"):
        return _install_atomic(name, cfg, manifest_path, tools_dir, sys_dir)
    if mechanism == "npm_peer":
        return {"status": "error", "detail": f"{name!r} is install_mechanism=npm_peer; use ensure_peer_cli instead"}
    return {"status": "error", "detail": f"Unknown install_mechanism {mechanism!r}"}


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


def ensure_peer_cli(peer: str, orch: dict | None = None, sys_dir: Path | None = None) -> dict:
    """Install a peer CLI if missing. `peer` may be a peers.json key
    (claude/codex/antigravity) or a node_id (cc/cx/ag/...). npm-backed peers
    (npm_package set in peers.json) are version-pinned via runtimes.json's
    tools entry of the same key; native-binary peers (e.g. antigravity/agy)
    delegate to ensure_tool for the matching runtimes.json tools entry."""
    sys_dir = sys_dir or _default_sys_dir()
    _drain_deferred_lazy(orch, sys_dir)

    peers = _load_peers(sys_dir)
    peer_key = _resolve_peer_key(peers, peer)
    if not peer_key:
        return {"status": "error", "detail": f"Peer {peer!r} not found in peers.json"}
    peer_cfg = peers[peer_key]

    native = peer_cfg.get("native_binary")
    if native:
        tool_key = Path(native.get("install_subdir", f"tools/{peer_key}")).name
        _, _, TOOLS = _load_runtimes(sys_dir)
        if tool_key not in TOOLS:
            return {"status": "error", "detail": f"native_binary tool {tool_key!r} not found in runtimes.json tools"}
        return ensure_tool(tool_key, orch, sys_dir)

    pkg = peer_cfg.get("npm_package")
    if not pkg:
        return {"status": "error", "detail": f"Peer {peer_key!r} has neither native_binary nor npm_package"}

    _, _, TOOLS = _load_runtimes(sys_dir)
    tool_cfg = TOOLS.get(peer_key, {})
    declared_version = tool_cfg.get("version")
    if not declared_version:
        return {"status": "error", "detail": f"No version declared in runtimes.json tools[{peer_key!r}]; add it before bootstrapping"}

    env_dir = sys_dir / "env"
    node_exe = env_dir / "nodejs" / "node.exe"
    if not node_exe.exists():
        return {"status": "error", "detail": "Node.js not installed; run provisioner deploy for nodejs first"}

    npm_global = env_dir / "nodejs" / "npm-global"
    node_ids = peer_cfg.get("node_ids") or [peer_key]
    peer_cmd = npm_global / f"{node_ids[0]}.cmd"

    manifest_path = sys_dir / "tools" / peer_key / ".install_manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("declared_version") == declared_version and peer_cmd.exists():
                return {"status": "already_current", "detail": "Version matches manifest"}
        except (OSError, json.JSONDecodeError):
            pass

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
        _add_deferred(sys_dir, peer_key, "peer")
        return {"status": "error", "detail": f"npm install failed: {e}"}

    manifest = {
        "tool": peer_key,
        "declared_version": declared_version,
        "url": f"npm:{pkg}",
        "checksum_algo": "npm_integrity",
        "checksum_value": integrity,
        "checksum_source": "registry_integrity",
        "checksum_verified": True,
        "canary_command": [],
        "canary_output": "",
        "installed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_config_hash": _canon_hash(tool_cfg),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _remove_deferred(sys_dir, peer_key, "peer")
    return {"status": "success", "detail": "Installed successfully"}


def deploy(ctx: dict) -> None:
    """Install all runtimes, tools, and AI peer CLIs."""
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
        env_dir / "python", env_dir / "nodejs", env_dir / "ffmpeg",
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

    # ── Node.js ──────────────────────────────────────────────────
    print(f"\n>>> Node.js {V['NodeJS']}")
    node_exe = env_dir / "nodejs" / "node.exe"
    if force or not node_exe.exists():
        zp = setup_dir / "nodejs.zip"
        if force or not zp.exists():
            _download(URLS["NodeJS"], zp, "Node.js")
        tmp = setup_dir / "_nodejs_tmp"
        tmp.mkdir(exist_ok=True)
        _extract(zp, tmp)
        extracted = next(tmp.iterdir())
        if extracted.is_dir():
            for item in extracted.iterdir():
                dest = env_dir / "nodejs" / item.name
                if dest.exists():
                    shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
                shutil.move(str(item), str(env_dir / "nodejs"))
        shutil.rmtree(tmp)
        print("  [OK] Node.js ready")
    else:
        print("  [--] Node.js (already installed)")
    installed.append("nodejs")

    # ── Git ──────────────────────────────────────────────────────
    print(f"\n>>> Git {V['Git']} (portable)")
    git_exe = env_dir / "git" / "cmd" / "git.exe"
    if force or not git_exe.exists():
        exe_path = setup_dir / "PortableGit.7z.exe"
        if force or not exe_path.exists():
            _download(URLS["Git"], exe_path, "Git Portable")
        subprocess.run([str(exe_path), f"-o{env_dir / 'git'}", "-y"], check=True)
        print("  [OK] Git ready")
    else:
        print("  [--] Git (already installed)")
    installed.append("git")

    # ── VS Code ──────────────────────────────────────────────────
    if not skip_vsc:
        print(f"\n>>> VS Code {V['VSCode']} (portable)")
        vsc_exe = env_dir / "vscode" / "Code.exe"
        if force or not vsc_exe.exists():
            zp = setup_dir / "vscode.zip"
            if force or not zp.exists():
                _download(URLS["VSCode"], zp, "VS Code")
            _extract(zp, env_dir / "vscode")
            (env_dir / "vscode" / "data").mkdir(exist_ok=True)
            print("  [OK] VS Code ready")
        else:
            print("  [--] VS Code (already installed)")
        installed.append("vscode")

    # ── Python venv ──────────────────────────────────────────────
    print("\n>>> Python venv")
    venv_py = env_dir / "venv" / "Scripts" / "python.exe"
    if force or not venv_py.exists():
        subprocess.run([sys.executable, "-m", "pip", "install", "virtualenv", "--quiet"], check=True)
        subprocess.run([sys.executable, "-m", "virtualenv", str(env_dir / "venv")], check=True)
        print("  [OK] venv created")
    else:
        print("  [--] venv (already exists)")
    for pkg in ["filelock", "pywinpty"]:
        subprocess.run([str(venv_py), "-m", "pip", "install", pkg, "--quiet"], check=True)
        print(f"  [OK] {pkg} installed")
    installed.append("venv")

    # ── CLI Tools ────────────────────────────────────────────────
    print("\n>>> CLI Tools")
    installed += _install_tools(TOOLS, env_dir, setup_dir, force)

    # ── AI Peer CLIs ─────────────────────────────────────────────
    if not skip_ai:
        print("\n>>> AI Peer CLIs")
        npm_global = env_dir / "nodejs" / "npm-global"
        npm_global.mkdir(exist_ok=True)
        npm_env = os.environ.copy()
        npm_env["NPM_CONFIG_PREFIX"] = str(npm_global)
        npm_env["NPM_CONFIG_CACHE"]  = str(env_dir / "nodejs" / "npm-cache")
        npm_env["PATH"]              = str(env_dir / "nodejs") + os.pathsep + npm_env["PATH"]
        npm_exe = env_dir / "nodejs" / "npm.cmd"
        installed += _install_ai_peers(peers, npm_exe, npm_global, npm_env, force)

    ctx["state"]["installed"] = installed
    print("\n======================================================")
    print("  Provisioner complete.")
    print("======================================================")


def _cli_ensure_tool(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="provisioner.py ensure-tool")
    parser.add_argument("name", nargs="?", help="Name of the runtimes.json tools entry to ensure")
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

    res = ensure_tool(args.name, sys_dir=sys_dir)
    print(json.dumps(res, indent=2))
    if res["status"] in ("success", "already_current"):
        return 0
    if res["status"] == "in_use_retry_at_session_boundary":
        return 3
    if "Checksum mismatch" in res.get("detail", ""):
        return 2
    return 1


def _cli_ensure_peer_cli(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="provisioner.py ensure-peer-cli")
    parser.add_argument("peer", help="peers.json key or node_id of the peer CLI to ensure")
    args = parser.parse_args(argv)

    sys_dir = _default_sys_dir()
    res = ensure_peer_cli(args.peer, sys_dir=sys_dir)
    print(json.dumps(res, indent=2))
    if res["status"] in ("success", "already_current"):
        return 0
    if res["status"] == "in_use_retry_at_session_boundary":
        return 3
    if "Checksum mismatch" in res.get("detail", ""):
        return 2
    return 1


if __name__ == "__main__":
    import argparse
    import traceback

    if len(sys.argv) > 1 and sys.argv[1] == "ensure-tool":
        sys.exit(_cli_ensure_tool(sys.argv[2:]))
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
        deploy(ctx)
    except Exception as e:
        print(f"\n[FATAL] {e}")
        traceback.print_exc()
        sys.exit(1)
