import json
import ntpath
import os
import re
import stat
import subprocess
import shutil
from pathlib import Path

from core import env_ops, env_manifest, backups, state_paths

class RegistryOps:
    def entries_for_root(self, old_root: str, localappdata: Path) -> list[dict]:
        old_norm = ntpath.normcase(ntpath.normpath(old_root))
        entries = []
        if not localappdata.exists():
            return entries
        seen = set()
        
        def check_file(p: Path) -> bool:
            try:
                val = p.read_bytes().decode("mbcs", errors="ignore").strip()
                return ntpath.normcase(ntpath.normpath(val)) == old_norm
            except OSError:
                return False

        for f in localappdata.glob("SandboxRun_*.root.txt"):
            if check_file(f):
                seen.add(f.name[:-len(".root.txt")])
        for f in localappdata.glob("SandboxRun_*.physroot.txt"):
            if check_file(f):
                seen.add(f.name[:-len(".physroot.txt")])

        try:
            import winreg
        except ImportError:
            winreg = None

        for key_name in seen:
            entry = {"key_name": key_name, "files": {}, "reg_keys": []}
            for ext in (".bat", ".ico", ".root.txt", ".physroot.txt"):
                p = localappdata / f"{key_name}{ext}"
                if p.exists():
                    try:
                        import base64
                        entry["files"][p.name] = base64.b64encode(p.read_bytes()).decode("ascii")
                    except OSError:
                        pass
            
            targets = [
                r"Software\Classes\Directory\shell",
                r"Software\Classes\Directory\Background\shell",
                r"Software\Classes\Drive\shell",
                r"Software\Classes\*\shell"
            ]
            if winreg:
                for t in targets:
                    path = f"{t}\\{key_name}"
                    try:
                        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_READ)
                        winreg.CloseKey(k)
                        entry["reg_keys"].append(f"HKCU\\{path}")
                    except OSError:
                        pass
            entries.append(entry)
        return entries

    def export(self, entries: list[dict], dest_file: Path) -> None:
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        for entry in entries:
            entry["reg_exports"] = {}
            for k in entry.get("reg_keys", []):
                tmp_reg = dest_file.with_suffix(".tmp.reg")
                res = subprocess.run(["reg", "export", k, str(tmp_reg), "/y"], capture_output=True)
                if res.returncode == 0 and tmp_reg.exists():
                    try:
                        entry["reg_exports"][k] = tmp_reg.read_text(encoding="utf-16le")
                    except Exception:
                        pass
                try:
                    tmp_reg.unlink(missing_ok=True)
                except OSError:
                    pass
        dest_file.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    def remove(self, entries: list[dict]) -> None:
        localappdata = Path(os.environ.get("LOCALAPPDATA", ""))
        for entry in entries:
            for reg_key in entry.get("reg_keys", []):
                subprocess.run(["reg", "delete", reg_key.replace("HKCU\\", "HKCU\\"), "/f"], capture_output=True)
            key_name = entry.get("key_name")
            if key_name:
                for ext in (".bat", ".ico", ".root.txt", ".physroot.txt"):
                    p = localappdata / f"{key_name}{ext}"
                    try:
                        p.unlink(missing_ok=True)
                    except OSError:
                        pass

    def reimport(self, export_file: Path) -> None:
        if not export_file.exists():
            return
        try:
            entries = json.loads(export_file.read_text(encoding="utf-8"))
        except Exception:
            return
        localappdata = Path(os.environ.get("LOCALAPPDATA", ""))
        import base64
        for entry in entries:
            for name, b64content in entry.get("files", {}).items():
                p = localappdata / name
                try:
                    p.write_bytes(base64.b64decode(b64content))
                except OSError:
                    pass
            for k, reg_content in entry.get("reg_exports", {}).items():
                tmp_reg = export_file.with_suffix(".tmp.reg")
                try:
                    tmp_reg.write_text(reg_content, encoding="utf-16le")
                    subprocess.run(["reg", "import", str(tmp_reg)], capture_output=True)
                except Exception:
                    pass
                try:
                    tmp_reg.unlink(missing_ok=True)
                except OSError:
                    pass

    def enable_menu(self, ctx: dict) -> None:
        try:
            from core import registrar
            registrar.apply(ctx)
        except ImportError:
            pass

def derive_menu_intent(sys_dir: Path | str, localappdata: Path | str, registry: RegistryOps | None = None) -> bool:
    sys_dir = Path(sys_dir)
    localappdata = Path(localappdata)
    state_file = sys_dir / "data" / "state" / state_paths.REGISTER_STATE_FILENAME
    if not state_file.exists():
        return False
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    
    entries = data.get("registry_entries", [])
    if not entries:
        return False
        
    for entry in entries:
        key_name = entry.get("key_name")
        if key_name:
            relay = localappdata / f"{key_name}.bat"
            if relay.exists():
                return True
        for reg_key in entry.get("reg_keys", []):
            relative = reg_key.replace("HKEY_CURRENT_USER\\", "").replace("HKCU\\", "")
            try:
                import winreg
                k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, relative, 0, winreg.KEY_READ)
                winreg.CloseKey(k)
                return True
            except (OSError, ImportError):
                pass
    return False

def rewrite_if_under(path_str: str, old_root: str, new_root: str) -> str:
    if not isinstance(path_str, str):
        return path_str
    
    old_norm = ntpath.normcase(old_root)
    path_norm = ntpath.normcase(path_str)
    
    if path_norm == old_norm or (path_norm.startswith(old_norm) and (old_norm.endswith("\\") or path_norm[len(old_norm)] == "\\")):
        prefix_len = len(old_root)
        original_prefix = path_str[:prefix_len]
        
        uses_fwd_slash = ('/' in original_prefix) or ('/' in path_str and '\\' not in path_str)
        if uses_fwd_slash and '\\' not in original_prefix:
            new_prefix = new_root.replace("\\", "/")
        else:
            new_prefix = new_root
            
        rel = path_str[prefix_len:]
        
        if old_norm.endswith("\\"):
            if not new_prefix.endswith("\\") and not new_prefix.endswith("/"):
                new_prefix += "/" if uses_fwd_slash else "\\"
        else:
            if rel.startswith("\\") or rel.startswith("/"):
                if new_prefix.endswith("\\") or new_prefix.endswith("/"):
                    rel = rel[1:]
                else:
                    if uses_fwd_slash and rel.startswith("\\"):
                        rel = "/" + rel[1:]
                    elif not uses_fwd_slash and rel.startswith("/"):
                        rel = "\\" + rel[1:]
                        
        return new_prefix + rel

    return path_str

def plan_relocation(
    sys_dir: Path | str, 
    base_dir: Path | str, 
    *, 
    manifest: dict | None, 
    drift: env_manifest.RootDrift, 
    localappdata: Path | str, 
    registry: RegistryOps | None = None,
    remap_ai_state: bool = False, 
    process_running=None, 
    runner=None,
    now=None
) -> list:
    if registry is None:
        registry = RegistryOps()
    if runner is None:
        def _default_runner(argv: list[str]) -> tuple[int, str]:
            try:
                res = subprocess.run(argv, capture_output=True, text=True, timeout=10)
                return res.returncode, res.stdout + res.stderr
            except Exception as e:
                return -1, str(e)
        runner = _default_runner
    if process_running is None and remap_ai_state:
        def _pr(name):
            try:
                import psutil
                return any(p.name() == name for p in psutil.process_iter(['name']))
            except ImportError:
                rc, out = runner(["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH"])
                return rc == 0 and name.lower() in out.lower()
        process_running = _pr
    if now is None:
        now = env_ops.utc_now

    sys_dir = Path(sys_dir)
    base_dir = Path(base_dir)
    localappdata = Path(localappdata)
    
    old_root = drift.previous_root
    is_copy = (drift.status == "copied")
    
    steps = []
    
    active = None
    try:
        active = env_ops.active_journal(sys_dir)
    except Exception:
        pass
        
    if active and active.get("kind") == "relocate":
        menu_intent = "re-enable-menu" in active.get("planned_posts", [])
    else:
        menu_intent = derive_menu_intent(sys_dir, localappdata, registry)
    
    if old_root and not is_copy:
        def do_export(ctx: env_ops.OpContext):
            entries = registry.entries_for_root(old_root, localappdata)
            ctx.data["registry_entries"] = entries
            ref = backups.create_text(
                sys_dir=ctx.sys_dir, kind="registry-export", filename="export.json",
                text="", reason="relocation export", op_id=ctx.op_id, label="reg", now=now()
            )
            export_path = ref.path / backups.PAYLOAD / "export.json"
            registry.export(entries, export_path)
            ctx.data["registry_export_path"] = str(export_path)

        steps.append(env_ops.Step("export-registry-keys", do=do_export, undo=None, done=None, group="A"))
        
        def do_remove(ctx: env_ops.OpContext):
            entries = ctx.data.get("registry_entries", [])
            registry.remove(entries)
            
        def undo_remove(ctx: env_ops.OpContext):
            export_path = ctx.data.get("registry_export_path")
            if export_path and Path(export_path).exists():
                registry.reimport(Path(export_path))
                
        def done_remove(ctx: env_ops.OpContext) -> bool:
            return len(registry.entries_for_root(old_root, localappdata)) == 0

        steps.append(env_ops.Step("remove-stale-registry-entries", do=do_remove, undo=undo_remove, done=done_remove, group="A"))

    if old_root:
        def do_regen_state(ctx: env_ops.OpContext):
            state_dir = sys_dir / "data" / "state"
            for name in ("install.state.json", "register.state.json", "menu-enable.state.json"):
                p = state_dir / name
                if not p.exists():
                    continue
                text = p.read_bytes().decode("utf-8")
                backups.create_text(
                    sys_dir=ctx.sys_dir, kind="state", filename=name,
                    text=text, reason=f"relocation state backup {name}",
                    op_id=ctx.op_id, label=name.split(".")[0], now=now()
                )
                try:
                    data = json.loads(text)
                except Exception:
                    continue
                
                def rewrite_node(node):
                    if isinstance(node, dict):
                        for k, v in list(node.items()):
                            if k == "base_dir":
                                node[k] = str(base_dir)
                            elif isinstance(v, (dict, list)):
                                rewrite_node(v)
                            elif isinstance(v, str):
                                node[k] = rewrite_if_under(v, old_root, str(base_dir))
                    elif isinstance(node, list):
                        for i in range(len(node)):
                            if isinstance(node[i], (dict, list)):
                                rewrite_node(node[i])
                            elif isinstance(node[i], str):
                                node[i] = rewrite_if_under(node[i], old_root, str(base_dir))

                rewrite_node(data)
                env_manifest._atomic_write_text(p, json.dumps(data, indent=2) + "\n")
                
        def undo_regen_state(ctx: env_ops.OpContext):
            scan_res = backups.scan(sys_dir)
            for ref in scan_res.valid:
                if ref.meta.get("op_id") == ctx.op_id and ref.kind == "state":
                    payload = ref.path / backups.PAYLOAD
                    for f in payload.iterdir():
                        if f.name.endswith(".state.json"):
                            target = sys_dir / "data" / "state" / f.name
                            env_manifest._atomic_write_text(target, f.read_bytes().decode("utf-8"))
                            
        def done_regen_state(ctx: env_ops.OpContext) -> bool:
            state_dir = sys_dir / "data" / "state"
            files_checked = 0
            for name in ("install.state.json", "register.state.json", "menu-enable.state.json"):
                p = state_dir / name
                if not p.exists():
                    continue
                files_checked += 1
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if name == "install.state.json":
                        if data.get("base_dir") != str(base_dir):
                            return False
                    
                    def has_old(node):
                        if isinstance(node, dict):
                            for k, v in node.items():
                                if k == "base_dir": continue
                                if has_old(v): return True
                        elif isinstance(node, list):
                            return any(has_old(x) for x in node)
                        elif isinstance(node, str):
                            return node != rewrite_if_under(node, old_root, str(base_dir))
                        return False

                    if has_old(data):
                        return False
                except Exception:
                    return False
            return files_checked > 0

        steps.append(env_ops.Step("regenerate-state-files", do=do_regen_state, undo=undo_regen_state, done=done_regen_state, group="A"))

        def do_rebase_git(ctx: env_ops.OpContext):
            git_cfg = base_dir / ".engram" / "git" / ".gitconfig"
            if not git_cfg.exists():
                return
            text = git_cfg.read_bytes().decode("utf-8")
            backups.create_text(
                sys_dir=ctx.sys_dir, kind="state", filename=".gitconfig",
                text=text, reason="relocation gitconfig backup",
                op_id=ctx.op_id, label="gitconfig", now=now()
            )
            
            lines = text.splitlines(keepends=True)
            new_lines = []
            in_safe = False
            for line in lines:
                strip_line = line.strip()
                if strip_line.startswith("[") and "]" in strip_line:
                    if strip_line.lower() == "[safe]":
                        in_safe = True
                    else:
                        in_safe = False
                        
                    m = re.search(r'(?i)\[includeIf\s+"gitdir:(.+?)"\]', line)
                    if m:
                        val = m.group(1)
                        new_val = rewrite_if_under(val, old_root, str(base_dir))
                        if new_val != val:
                            line = line[:m.start(1)] + new_val + line[m.end(1):]
                elif in_safe:
                    m = re.search(r'(?i)^(\s*directory\s*=\s*)(.+?)([\r\n]*)$', line)
                    if m:
                        val = m.group(2)
                        suffix = m.group(3)
                        
                        has_quotes = False
                        if val.startswith('"') and val.endswith('"') and len(val) >= 2:
                            has_quotes = True
                            val = val[1:-1]
                            
                        new_val = rewrite_if_under(val, old_root, str(base_dir))
                        if new_val != val:
                            if has_quotes:
                                new_val = f'"{new_val}"'
                            line = line[:m.start(2)] + new_val + suffix
                new_lines.append(line)
            env_manifest._atomic_write_text(git_cfg, "".join(new_lines))

        def undo_rebase_git(ctx: env_ops.OpContext):
            scan_res = backups.scan(sys_dir)
            for ref in scan_res.valid:
                if ref.meta.get("op_id") == ctx.op_id and ref.kind == "state":
                    payload = ref.path / backups.PAYLOAD / ".gitconfig"
                    if payload.exists():
                        target = base_dir / ".engram" / "git" / ".gitconfig"
                        env_manifest._atomic_write_text(target, payload.read_bytes().decode("utf-8"))

        steps.append(env_ops.Step("rebase-git-config", do=do_rebase_git, undo=undo_rebase_git, done=None, group="A"))

        if remap_ai_state:
            def do_remap_ai(ctx: env_ops.OpContext):
                if process_running("claude.exe"):
                    raise RuntimeError("claude.exe is running")
                claude_dir = base_dir / ".engram" / "claude"
                claude_json = claude_dir / ".claude.json"
                if not claude_json.exists():
                    return
                
                try:
                    text = claude_json.read_bytes().decode("utf-8")
                    data = json.loads(text)
                except Exception:
                    ctx.data["ai_state_skipped"] = True
                    return
                    
                if not isinstance(data, dict) or "projects" not in data or not isinstance(data["projects"], dict):
                    ctx.data["ai_state_skipped"] = True
                    return
                    
                ref = backups.create_text(
                    sys_dir=ctx.sys_dir, kind="ai-state", filename=".claude.json",
                    text=text, reason="relocation ai-state backup",
                    op_id=ctx.op_id, label="claude", now=now()
                )
                if hasattr(os, "chmod"):
                    os.chmod(ref.path, stat.S_IRUSR | stat.S_IWUSR)
                    
                old_paths_found = []
                new_projects = {}
                for k, v in data["projects"].items():
                    new_k = rewrite_if_under(k, old_root, str(base_dir))
                    
                    if isinstance(v, dict):
                        for mcp in v.get("mcpServers", {}).values():
                            cmd = mcp.get("command", "")
                            if isinstance(cmd, str):
                                rewritten = rewrite_if_under(cmd, old_root, str(base_dir))
                                if rewritten != cmd:
                                    old_paths_found.append(cmd)
                        for hook in v.get("hooks", []):
                            cmd = hook.get("command", "")
                            if isinstance(cmd, str):
                                rewritten = rewrite_if_under(cmd, old_root, str(base_dir))
                                if rewritten != cmd:
                                    old_paths_found.append(cmd)
                    
                    new_projects[new_k] = v
                    
                    if new_k != k:
                        old_slug = re.sub(r'[^A-Za-z0-9]', '-', k)
                        new_slug = re.sub(r'[^A-Za-z0-9]', '-', new_k)
                        old_slug_dir = claude_dir / "projects" / old_slug
                        new_slug_dir = claude_dir / "projects" / new_slug
                        if old_slug_dir.exists():
                            if new_slug_dir.exists():
                                ctx.data.setdefault("ai_state_slug_collisions", []).append(old_slug)
                            else:
                                new_slug_dir.parent.mkdir(parents=True, exist_ok=True)
                                shutil.move(str(old_slug_dir), str(new_slug_dir))
                                ctx.data.setdefault("renamed_slugs", []).append((str(old_slug_dir), str(new_slug_dir)))
                                
                data["projects"] = new_projects
                ctx.data["ai_state_old_paths"] = old_paths_found
                
                m = re.search(r'\n( +)"projects"', text)
                indent = len(m.group(1)) if m else 2
                env_manifest._atomic_write_text(claude_json, json.dumps(data, indent=indent) + "\n")
                
            def undo_remap_ai(ctx: env_ops.OpContext):
                scan_res = backups.scan(sys_dir)
                for ref in scan_res.valid:
                    if ref.meta.get("op_id") == ctx.op_id and ref.kind == "ai-state":
                        payload = ref.path / backups.PAYLOAD / ".claude.json"
                        if payload.exists():
                            target = base_dir / ".engram" / "claude" / ".claude.json"
                            env_manifest._atomic_write_text(target, payload.read_bytes().decode("utf-8"))
                for old_d, new_d in ctx.data.get("renamed_slugs", []):
                    if Path(new_d).exists():
                        shutil.move(new_d, old_d)

            steps.append(env_ops.Step("remap-ai-state", do=do_remap_ai, undo=undo_remap_ai, done=None, group="A"))

    if menu_intent:
        def do_re_enable_menu(ctx: env_ops.OpContext):
            apply_ctx = {
                "base_dir": base_dir,
                "sys_dir": sys_dir,
                "paths": {"state": sys_dir / "data" / "state"},
                "state": {}
            }
            registry.enable_menu(apply_ctx)
        steps.append(env_ops.Step("re-enable-menu", do=do_re_enable_menu, group="B"))

    def do_write_manifest(ctx: env_ops.OpContext):
        nonlocal manifest
        if manifest is None:
            manifest = env_manifest.propose_adoption(sys_dir, base_dir, now=now())
        new_manifest = dict(manifest)
        new_manifest["root"] = env_manifest.current_root_identity(base_dir)
        if is_copy:
            new_manifest["install_id"] = env_manifest.new_install_id()
            
        if "python_version" in ctx.data:
            new_manifest.setdefault("python", {})["version"] = ctx.data["python_version"]
        if "venv_python_version" in ctx.data:
            new_manifest.setdefault("venv", {})["python_version"] = ctx.data["venv_python_version"]
            
        new_manifest["last_op"] = {
            "id": ctx.op_id,
            "kind": ctx.kind,
            "result": "committed",
            "at": now()
        }
        env_manifest.write_manifest(sys_dir, new_manifest)
        
    def done_write_manifest(ctx: env_ops.OpContext) -> bool:
        read = env_manifest.read_manifest(sys_dir)
        if read.status == "ok" and read.data:
            return read.data.get("last_op", {}).get("id") == ctx.op_id
        return False

    steps.append(env_ops.Step("write-manifest", do=do_write_manifest, done=done_write_manifest, group="B"))

    def do_write_lbd(ctx: env_ops.OpContext):
        lbd = sys_dir / "data" / env_manifest.LAST_BASE_DIR_FILENAME
        env_manifest._atomic_write_text(lbd, str(base_dir))
        
    def done_write_lbd(ctx: env_ops.OpContext) -> bool:
        lbd = sys_dir / "data" / env_manifest.LAST_BASE_DIR_FILENAME
        if lbd.exists():
            return lbd.read_text(encoding="utf-8").strip() == str(base_dir)
        return False

    steps.append(env_ops.Step("write-last-base-dir", do=do_write_lbd, done=done_write_lbd, group="B"))

    return steps
