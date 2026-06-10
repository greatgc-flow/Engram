"""
setup.py - Portable Dev Environment Bootstrapper
Handles downloading and installing all components: Node.js, FFmpeg, Git, VS Code, etc.
AI CLI peers are driven by _sys/ai/peers.json — add a peer there, no code change needed.
"""
import os
import sys
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

# --- Runtime Versions & URLs ---
V = {
    "Python": "3.13.4",
    "NodeJS": "22.22.3",
    "Git": "2.49.0",
    "VSCode": "1.100.2",
    "Pwsh": "7.6.2"
}

URLS = {
    "NodeJS": f"https://nodejs.org/dist/v{V['NodeJS']}/node-v{V['NodeJS']}-win-x64.zip",
    "Git": f"https://github.com/git-for-windows/git/releases/download/v{V['Git']}.windows.1/PortableGit-{V['Git']}-64-bit.7z.exe",
    "FFmpeg": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl-shared.zip",
    "VSCode": f"https://update.code.visualstudio.com/{V['VSCode']}/win32-x64-archive/stable",
    "Pwsh": f"https://github.com/PowerShell/PowerShell/releases/download/v{V['Pwsh']}/PowerShell-{V['Pwsh']}-win-x64.zip"
}


def get_paths() -> dict:
    sys_dir = Path(__file__).parent.parent.resolve()
    base_dir = sys_dir.parent
    return {
        "base": base_dir,
        "sys": sys_dir,
        "env": sys_dir / "env",
        "tools": sys_dir / "tools",
        "data": sys_dir / "data",
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


def run_setup(force: bool = False, skip_vscode: bool = False, skip_ai: bool = False) -> None:
    paths = get_paths()
    print(f"\n>>> Starting Setup (Force={force})")

    # 1. Folder Structure
    print("\n>>> Folder structure")
    dirs = [
        paths["env"], paths["env"] / "python", paths["env"] / "nodejs",
        paths["env"] / "ffmpeg", paths["env"] / "git", paths["env"] / "vscode",
        paths["env"] / "venv", paths["env"] / "pwsh",
        paths["tools"], paths["tools"] / "apps",
        paths["data"] / "logs", paths["data"] / "temp", paths["setup"],
        paths["base"] / "workspace",
        paths["sys"] / "ai", paths["sys"] / "ai" / "common",
    ]
    # Create config/ and project/ dirs for each registered peer
    peers = load_peers(paths["sys"])
    for peer_id, cfg in peers.items():
        subdir = paths["sys"] / cfg.get("sys_subdir", peer_id)
        dirs.append(subdir / "config")
        dirs.append(subdir / "project")

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

    # 6. Install filelock
    print("  [i] Installing filelock...")
    subprocess.run([str(venv_py), "-m", "pip", "install", "filelock", "--quiet"], check=True)
    print("  [OK] filelock installed")

    # 7. AI Peer CLIs (driven by peers.json)
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

    # 8. Finalize with Registry
    print("\n>>> Finalizing with Registry context menu")
    manage_py = paths["sys"] / "cli" / "manage.py"
    subprocess.run([sys.executable, str(manage_py), "Register"], check=True)

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
