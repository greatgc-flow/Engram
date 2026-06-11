"""
setup.py - Portable Dev Environment Bootstrapper
Runtime versions/URLs driven by _sys/runtimes.json.
AI CLI peers driven by _sys/ai/peers.json.
No hardcoded versions or URLs in this file.
"""
import os
import sys
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path


def _load_runtimes() -> tuple[dict, dict, dict]:
    """Load V (versions), URLS, and TOOLS from _sys/runtimes.json."""
    sys_dir = Path(__file__).parent.parent.resolve()
    runtimes_path = sys_dir / "runtimes.json"
    if not runtimes_path.exists():
        raise FileNotFoundError(
            f"[Error] _sys/runtimes.json not found.\n"
            f"  Expected: {runtimes_path}\n"
            f"  This file should be present in the git repo."
        )
    raw = json.loads(runtimes_path.read_text(encoding="utf-8"))
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
    TOOLS = raw.get("tools", {})
    return V, URLS, TOOLS


V, URLS, TOOLS = _load_runtimes()


def get_paths() -> dict:
    sys_dir = Path(__file__).parent.parent.resolve()
    base_dir = sys_dir.parent
    return {
        "base":  base_dir,
        "sys":   sys_dir,
        "env":   sys_dir / "env",
        "tools": sys_dir / "tools",
        "data":  sys_dir / "data",
        "setup": sys_dir / "data" / "setup-files",
    }


def load_peers(sys_dir: Path) -> dict:
    """Load AI peer definitions from _sys/ai/peers.json."""
    peers_path = sys_dir / "ai" / "peers.json"
    if peers_path.exists():
        try:
            return json.loads(peers_path.read_text(encoding="utf-8")).get("peers", {})
        except Exception:
            pass
    return {}


def download_file(url: str, dest: Path, label: str) -> None:
    print(f"  [i] Downloading {label}...")
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response, open(dest, "wb") as out_file:
        shutil.copyfileobj(response, out_file)
    size_mb = dest.stat().st_size / (1024 * 1024)
    print(f"  [OK] Downloaded: {dest.name} ({size_mb:.1f} MB)")


def extract_zip(zip_path: Path, dest_dir: Path) -> None:
    print(f"  [i] Extracting {zip_path.name}...")
    try:
        shutil.unpack_archive(str(zip_path), str(dest_dir))
        print(f"  [OK] Extracted to {dest_dir.name}")
    except Exception as e:
        print(f"  [Fail] Extraction failed: {e}")
        subprocess.run(["tar", "-xf", str(zip_path), "-C", str(dest_dir)], check=True)


def install_tools(paths: dict, force: bool = False) -> None:
    """Install all CLI tools from runtimes.json [tools] section."""
    if not TOOLS:
        print("  [--] No tools defined in runtimes.json")
        return

    tools_dir = paths["tools"]
    setup_dir = paths["setup"]

    for name, cfg in TOOLS.items():
        url      = cfg.get("url", "")
        kind     = cfg.get("type", "zip")   # "zip" | "exe"
        bin_name = cfg.get("bin", f"{name}.exe")
        extras   = cfg.get("extras", [])
        dest_dir = tools_dir / name
        dest_dir.mkdir(parents=True, exist_ok=True)

        sentinel = dest_dir / bin_name
        if not force and sentinel.exists():
            print(f"  [--] {name} (already installed)")
            # extras (e.g. oh-my-posh themes) — also skip if dest exists
            for extra in extras:
                extra_dest = dest_dir / extra.get("dest", "extra")
                if not extra_dest.exists():
                    _install_tool_extra(name, extra, dest_dir, setup_dir)
            continue

        print(f"\n>>> Tool: {name} v{cfg.get('version', '?')}")

        if kind == "exe":
            # Direct single-exe download
            dl_path = setup_dir / f"{name}-dl.exe"
            download_file(url, dl_path, name)
            shutil.copy2(str(dl_path), str(sentinel))
            dl_path.unlink()
            print(f"  [OK] {name} ready → {sentinel.name}")
        else:
            # Zip: extract all .exe files into dest_dir
            zip_path = setup_dir / f"{name}.zip"
            download_file(url, zip_path, name)
            tmp_dir = setup_dir / f"_{name}_tmp"
            tmp_dir.mkdir(exist_ok=True)
            extract_zip(zip_path, tmp_dir)
            for exe in tmp_dir.rglob("*.exe"):
                shutil.copy2(str(exe), str(dest_dir / exe.name))
            shutil.rmtree(tmp_dir)
            zip_path.unlink(missing_ok=True)
            print(f"  [OK] {name} ready")

        # extras (e.g. oh-my-posh themes zip)
        for extra in extras:
            _install_tool_extra(name, extra, dest_dir, setup_dir)


def _install_tool_extra(tool_name: str, extra: dict, dest_dir: Path, setup_dir: Path) -> None:
    """Install an extra resource (e.g. themes zip) for a tool."""
    url       = extra.get("url", "")
    kind      = extra.get("type", "zip")
    subfolder = extra.get("dest", "extra")
    extra_dir = dest_dir / subfolder
    if not url:
        return
    extra_dir.mkdir(parents=True, exist_ok=True)
    if kind == "zip":
        zip_path = setup_dir / f"{tool_name}-extra-{subfolder}.zip"
        download_file(url, zip_path, f"{tool_name}/{subfolder}")
        extract_zip(zip_path, extra_dir)
        zip_path.unlink(missing_ok=True)
        print(f"  [OK] {tool_name}/{subfolder} ready")


def install_ai_peers(paths: dict, npm_exe: Path, env: dict, force: bool = False) -> None:
    """Install all enabled AI peer CLIs from peers.json."""
    peers = load_peers(paths["sys"])
    npm_global = paths["env"] / "nodejs" / "npm-global"

    for peer_id, cfg in peers.items():
        if not cfg.get("enabled"):
            continue
        pkg = cfg.get("npm_package")
        if not pkg:
            continue

        print(f"\n>>> AI Peer: {cfg.get('description', peer_id)}")
        peer_cmd = npm_global / f"{peer_id}.cmd"

        if force or not peer_cmd.exists():
            print(f"  [i] npm install -g {pkg} ...")
            subprocess.run([str(npm_exe), "install", "-g", pkg], env=env, check=True)
            print(f"  [OK] {peer_id} CLI ready")
        else:
            print(f"  [--] {peer_id} CLI (already installed)")


def check_python_version(paths: dict) -> None:
    """현재 Python 버전과 runtimes.json 기대 버전 비교 후 안내."""
    running = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    expected = V.get("Python", "")
    if expected and running != expected:
        print(f"  [!] Python 버전 불일치: 실행 중={running}, runtimes.json={expected}")
        print(f"      PURGE 후 INSTALL.bat 재실행 시 {expected} 버전으로 교체됩니다.")
    else:
        print(f"  [OK] Python {running}")


def run_setup(force: bool = False, skip_vscode: bool = False, skip_ai: bool = False) -> None:
    paths = get_paths()
    print(f"\n>>> Starting Setup (Force={force})")
    check_python_version(paths)

    # 1. Folder Structure
    print("\n>>> Folder structure")
    dirs = [
        paths["env"], paths["env"] / "python", paths["env"] / "nodejs",
        paths["env"] / "ffmpeg", paths["env"] / "git", paths["env"] / "vscode",
        paths["env"] / "venv", paths["env"] / "pwsh",
        paths["tools"], paths["tools"] / "apps",
        paths["data"] / "logs", paths["data"] / "temp", paths["setup"],
        paths["base"] / "workspace",
        paths["sys"] / "ai",
        paths["sys"] / "ai" / "common",
        paths["sys"] / "ai" / "common" / "agents",
        paths["sys"] / "ai" / "common" / "skills",
        paths["sys"] / "ai" / "common" / "mcp",
        paths["sys"] / "common",
        paths["sys"] / "common" / "scripts",
        paths["sys"] / "common" / "assets",
    ]
    peers = load_peers(paths["sys"])
    for peer_id, cfg in peers.items():
        subdir = paths["sys"] / cfg.get("sys_subdir", peer_id)
        dirs.append(subdir / "config")
        dirs.append(subdir / "project")
        if cfg.get("sys_subdir"):
            dirs.append(subdir / "templates")

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    print("  [OK] Folder structure ready")

    # 2. NodeJS
    print(f"\n>>> Node.js {V['NodeJS']}")
    node_exe = paths["env"] / "nodejs" / "node.exe"
    if force or not node_exe.exists():
        zip_path = paths["setup"] / "nodejs.zip"
        if force or not zip_path.exists():
            download_file(URLS["NodeJS"], zip_path, "Node.js")

        tmp_dir = paths["setup"] / "_nodejs_tmp"
        tmp_dir.mkdir(exist_ok=True)
        extract_zip(zip_path, tmp_dir)

        extracted = next(tmp_dir.iterdir())
        if extracted.is_dir():
            for item in extracted.iterdir():
                dest = paths["env"] / "nodejs" / item.name
                if dest.exists():
                    if dest.is_dir(): shutil.rmtree(dest)
                    else: dest.unlink()
                shutil.move(str(item), str(paths["env"] / "nodejs"))
        shutil.rmtree(tmp_dir)
        print("  [OK] Node.js ready")
    else:
        print("  [--] Node.js (already installed)")

    # 3. Git
    print(f"\n>>> Git {V['Git']} (portable)")
    git_exe = paths["env"] / "git" / "cmd" / "git.exe"
    if force or not git_exe.exists():
        exe_path = paths["setup"] / "PortableGit.7z.exe"
        if force or not exe_path.exists():
            download_file(URLS["Git"], exe_path, "Git Portable")
        print("  [i] Extracting Git (self-extracting archive)...")
        subprocess.run([str(exe_path), f"-o{paths['env'] / 'git'}", "-y"], check=True)
        print("  [OK] Git ready")
    else:
        print("  [--] Git (already installed)")

    # 4. VS Code
    if not skip_vscode:
        print(f"\n>>> VS Code {V['VSCode']} (portable)")
        vsc_exe = paths["env"] / "vscode" / "Code.exe"
        if force or not vsc_exe.exists():
            zip_path = paths["setup"] / "vscode.zip"
            if force or not zip_path.exists():
                download_file(URLS["VSCode"], zip_path, "VS Code")
            extract_zip(zip_path, paths["env"] / "vscode")
            (paths["env"] / "vscode" / "data").mkdir(exist_ok=True)
            print("  [OK] VS Code ready")
        else:
            print("  [--] VS Code (already installed)")

    # 5. Python venv
    print("\n>>> Python virtual environment")
    venv_dir = paths["env"] / "venv"
    venv_py = venv_dir / "Scripts" / "python.exe"
    if force or not venv_py.exists():
        print("  [i] Installing virtualenv...")
        subprocess.run([sys.executable, "-m", "pip", "install", "virtualenv", "--quiet"], check=True)
        print("  [i] Creating venv...")
        subprocess.run([sys.executable, "-m", "virtualenv", str(venv_dir)], check=True)
        print("  [OK] venv created")
    else:
        print("  [--] venv (already exists)")

    # 6. Install pip packages
    print("  [i] Installing filelock...")
    subprocess.run([str(venv_py), "-m", "pip", "install", "filelock", "--quiet"], check=True)
    print("  [OK] filelock installed")
    print("  [i] Installing pywinpty (agy PTY support)...")
    subprocess.run([str(venv_py), "-m", "pip", "install", "pywinpty", "--quiet"], check=True)
    print("  [OK] pywinpty installed")

    # 7. CLI Tools (driven by runtimes.json [tools])
    print("\n>>> CLI Tools (from _sys/runtimes.json)")
    install_tools(paths, force=force)

    # 8. AI Peer CLIs (driven by peers.json)
    if not skip_ai:
        print("\n>>> AI Peer CLIs (from _sys/ai/peers.json)")
        npm_global = paths["env"] / "nodejs" / "npm-global"
        npm_global.mkdir(exist_ok=True)

        env = os.environ.copy()
        env["NPM_CONFIG_PREFIX"] = str(npm_global)
        env["NPM_CONFIG_CACHE"] = str(paths["env"] / "nodejs" / "npm-cache")
        env["PATH"] = str(paths["env"] / "nodejs") + os.pathsep + env["PATH"]

        npm_exe = paths["env"] / "nodejs" / "npm.cmd"
        install_ai_peers(paths, npm_exe, env, force=force)

    # 9. Finalize with Registry (non-fatal — environment is usable even if registry fails)
    print("\n>>> Registering context menu and junctions")
    manage_py = paths["sys"] / "cli" / "manage.py"
    result = subprocess.run([sys.executable, str(manage_py), "Register"])
    if result.returncode != 0:
        print("  [Warning] Registry setup failed — environment still functional via start.bat.")
        print("            Run register.bat manually after resolving permissions.")
    else:
        print("  [OK] Registration complete")

    print("\n======================================================")
    print("  Setup complete! All components installed.")
    print("======================================================")


if __name__ == "__main__":
    import argparse
    import traceback

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-vscode", action="store_true")
    parser.add_argument("--skip-ai", action="store_true", help="Skip AI peer CLI installation")
    parser.add_argument("--skip-claude", action="store_true", help="Deprecated: use --skip-ai")
    args = parser.parse_args()

    skip_ai = args.skip_ai or args.skip_claude

    try:
        run_setup(force=args.force, skip_vscode=args.skip_vscode, skip_ai=skip_ai)
    except Exception as e:
        print(f"\n[FATAL ERROR] Setup failed:")
        print(f"  {e}\n")
        print("--- Stack Trace ---")
        traceback.print_exc()
        print("-------------------")
        sys.exit(1)
