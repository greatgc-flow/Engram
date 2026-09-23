"""
updater.py - First-class update dispatch pipeline.
"""
import argparse
import os
import sys
import shutil
import json
from pathlib import Path
from typing import Any

_CORE_DIR = Path(__file__).resolve().parent
_SYS_DIR = _CORE_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))

from root import bootstrap_root_package, find_root  # noqa: E402
bootstrap_root_package(_SYS_DIR)

from checks import check_tool_updates
from core import provisioner
from core.doctor import check_components


def _download_and_stage_core_update(
    url: str, checksum_value: str, zip_path: Path, staged_dir: Path
) -> None:
    """Securely download and extract a core-update archive.

    Reuses provisioner's already-hardened `_secure_download` (rejects
    cross-host redirects except a narrow verified-CDN allowlist) and
    `_extract` (rejects zip-slip path-traversal and symlink archive
    members) instead of a raw `urllib.request.urlretrieve` +
    `zipfile.ZipFile(...).extractall()`, which has neither protection --
    a malicious or compromised update archive could otherwise write
    outside `staged_dir` during extraction itself, before any of this
    function's own post-extraction content checks ever run.
    """

    provisioner._secure_download(url, zip_path)

    actual_hash = provisioner._hash_file(zip_path, "sha256")
    if actual_hash.lower() != checksum_value.lower():
        raise ValueError(
            f"Checksum mismatch: expected {checksum_value}, got {actual_hash}"
        )

    if staged_dir.exists():
        shutil.rmtree(staged_dir, ignore_errors=True)
    staged_dir.mkdir(parents=True)
    provisioner._extract(zip_path, staged_dir)


def _parse_args(args: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Updater runner",
        epilog=(
            "Examples:\n"
            "  engram update                              interactive: show plan, confirm, apply\n"
            "  engram update --yes                         apply without confirmation\n"
            "  engram update --check                       show plan only, exit 1 if anything can't be checked (for scripts/CI)\n"
            "  engram update --dry-run                     discover + show proposal, apply nothing\n"
            "  engram update --only claude,codex            update just those two AI CLIs\n"
            "  engram update --only nodejs --allow-major-runtime-upgrade --yes\n"
            "                                               let Node.js cross a major version (e.g. 22 -> 24)\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--check", action="store_true", help="Stop after printing plan. Exit 1 if Could not check is non-empty")
    parser.add_argument("--dry-run", action="store_true", help="Discover and show proposal, apply nothing")
    parser.add_argument("--only", nargs="+", help="Update only specified components")
    parser.add_argument(
        "--allow-major-runtime-upgrade",
        action="store_true",
        help="Allow major version upgrade for base runtimes (e.g. Node.js 22 -> 24)",
    )
    if "/?" in args:
        # argparse understands -h/--help natively but not the Windows /? convention.
        parser.print_help()
        raise SystemExit(0)
    return parser.parse_args(args)


def run(ctx: dict[str, Any]) -> dict[str, Any]:
    args_list = ctx.get("args", [])
    try:
        args = _parse_args(args_list)
    except SystemExit as e:
        # argparse's own --help/-h exits 0 after already printing full usage;
        # only a real parse error (exit code 2) should fail the pipeline.
        if e.code in (0, None):
            return {"status": "success", "detail": "help displayed"}
        return {"status": "failed", "detail": f"Argument parsing failed with code {e.code}", "exit_code": 2}

    normalized_only = check_tool_updates.normalize_only_list(getattr(args, "only", None))
    only_set = set(normalized_only) if normalized_only is not None else None

    live_runtimes = provisioner.load_json_with_fallback(provisioner.resolve_declared_config(_SYS_DIR, "runtimes.json"))
    catalog = provisioner.load_json_with_fallback(provisioner.resolve_declared_config(_SYS_DIR, provisioner.TOOL_CATALOG_FILENAME))

    if only_set is not None:
        valid_names: set[str] = {"engram", "core"}
        for s in ("runtimes", "tools"):
            valid_names.update(live_runtimes.get(s, {}).keys())
        for tool in catalog.get("tools", []):
            if isinstance(tool, dict):
                tid = tool.get("tool_id")
                if tid:
                    valid_names.add(tid)
                for alias in tool.get("aliases", []):
                    valid_names.add(alias)
        unknown = [n for n in normalized_only if n not in valid_names]
        if unknown:
            print(f"[Error] Unknown component: {', '.join(unknown)}")
            return {"status": "failed", "detail": f"Unknown component in --only: {', '.join(unknown)}", "exit_code": 2}

    print(">>> Discovering updates...")
    sys_dir = _SYS_DIR
    allow_major = getattr(args, "allow_major_runtime_upgrade", False)
    
    run_kwargs: dict[str, Any] = {"propose_diff": True}
    if normalized_only is not None:
        run_kwargs["only"] = normalized_only
    if allow_major:
        run_kwargs["allow_major_runtime_upgrade"] = True

    try:
        try:
            payload = check_tool_updates.run(**run_kwargs)
        except TypeError:
            run_kwargs.pop("allow_major_runtime_upgrade", None)
            payload = check_tool_updates.run(**run_kwargs)
    except Exception as e:
        return {"status": "failed", "detail": f"Update discovery failed: {e}"}

    if payload.get("errors"):
        return {"status": "failed", "detail": "Update discovery encountered errors", "errors": payload["errors"]}

    artifact_dir = payload.get("artifact_dir")
    if not artifact_dir:
        return {"status": "failed", "detail": "No artifact dir returned by update discovery"}
    
    runtimes_updates = []
    tools_updates = []
    ai_clis_updates = []
    
    for update in payload.get("updates_discovered", []):
        if not isinstance(update, dict):
            print(f"  [Warning] Malformed update item in payload: {update} — skipped")
            continue
        section = update.get("section")
        if section not in ("runtimes", "tools", "catalog"):
            tool = update.get("tool")
            if tool in live_runtimes.get("runtimes", {}):
                section = "runtimes"
            elif tool in live_runtimes.get("tools", {}):
                section = "tools"
            elif any(isinstance(t, dict) and (t.get("tool_id") == tool or tool in t.get("aliases", [])) for t in catalog.get("tools", [])):
                section = "catalog"
            else:
                print(f"  [Warning] Unknown component section '{section}' for update '{tool}' — skipped")
                continue
            update["section"] = section
        if section == "runtimes":
            runtimes_updates.append(update)
        elif section == "tools":
            tools_updates.append(update)
        elif section == "catalog":
            ai_clis_updates.append(update)
            
    repairs_needed = check_components(sys_dir).get("missing", [])
    if only_set is not None:
        alias_map = {}
        for tool in catalog.get("tools", []):
            if isinstance(tool, dict):
                tid = tool.get("tool_id")
                if tid:
                    alias_map[tid.lower()] = tid
                    for a in tool.get("aliases", []):
                        alias_map[a.lower()] = tid
        canonical_only = {alias_map.get(n.lower(), n) for n in only_set}
        filtered_repairs = []
        for rep in repairs_needed:
            clean_rep = rep.split("/", 1)[-1]
            if clean_rep in only_set or clean_rep in canonical_only:
                filtered_repairs.append(rep)
        repairs_needed = filtered_repairs

    not_checked = payload.get("not_checked", [])
    could_not_check = payload.get("could_not_check", [])
    
    # ---------------------------------------------------------
    # Engram Core Channel Detection & Discovery
    # ---------------------------------------------------------
    from core import version_resolver
    from checks.check_tool_updates import DISCOVERY_CACHE_PATH
    
    core_update = None
    core_not_checked = None
    core_error = None
    
    want_core = only_set is None or bool(only_set & {"engram", "core"})
    if want_core:
        try:
            from core.version import load_version_info
            current_version_info = load_version_info(_SYS_DIR / "core" / "version.json")
        except ImportError:
            current_version_info = provisioner.load_json_with_fallback(_SYS_DIR / "core" / "version.json")

        current_engram_version = current_version_info.get("version", "unknown")
        
        if (_PORTABLE_ROOT / ".git").exists():
            core_not_checked = {"component": "Engram core", "reason": "git checkout — use git pull"}
        else:
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            if local_appdata:
                winget_path = Path(local_appdata) / "Microsoft" / "WinGet" / "Packages"
                try:
                    if _PORTABLE_ROOT.is_relative_to(winget_path):
                        core_not_checked = {"component": "Engram core", "reason": "managed by WinGet — run winget upgrade greatgc-flow.Engram"}
                except ValueError:
                    pass
                    
        if not core_not_checked:
            core_discovery = version_resolver.resolve_latest(
                tool_name="Engram core",
                provider="engram_release",
                current_version=current_engram_version,
                discovery_id="greatgc-flow/Engram",
                cache_path=DISCOVERY_CACHE_PATH,
            )
            status = core_discovery.get("status")
            if status != "ok":
                if status == "discovery_unavailable":
                    core_not_checked = {"component": "Engram core", "reason": "rate limited"}
                else:
                    core_error = {
                        "component": "Engram core",
                        "error_type": core_discovery.get("error_type", "unknown"),
                        "detail": core_discovery.get("detail", "unknown error")
                    }
            else:
                latest = core_discovery.get("latest_version")
                if latest and current_engram_version != latest:
                    core_update = {
                        "tool": "engram",
                        "component": "Engram core",
                        "current_version": current_engram_version,
                        "latest_version": latest,
                        "url": core_discovery.get("url"),
                        "checksum_algo": core_discovery.get("checksum_algo"),
                        "checksum_value": core_discovery.get("checksum_value"),
                    }
                
    if core_not_checked:
        not_checked.append(core_not_checked)
    if core_error:
        could_not_check.append(core_error)
        
    core_updates = [core_update] if core_update else []
    # ---------------------------------------------------------

    self_update_tools = []
    for tool in catalog.get("tools", []):
        if not isinstance(tool, dict):
            continue
        tid = tool.get("tool_id")
        if not tid:
            continue
        u_cfg = tool.get("update", {})
        if u_cfg.get("mechanism") == "self_update":
            if only_set is not None:
                aliases = tool.get("aliases", [])
                if tid not in only_set and not any(a in only_set for a in aliases):
                    continue
            bin_name = u_cfg.get("bin", tool.get("install", {}).get("bin", f"{tid}.exe"))
            exe_path = sys_dir / "tools" / tid / bin_name
            npm_cmd = provisioner.npm_global_dir(sys_dir) / f"{tid}.cmd"
            if exe_path.exists() or npm_cmd.exists():
                manifest_path = sys_dir / "tools" / tid / ".install_manifest.json"
                cur_ver = tool.get("version", "unknown")
                if manifest_path.exists():
                    try:
                        m_data = json.loads(manifest_path.read_text(encoding="utf-8"))
                        if m_data.get("observed_version"):
                            cur_ver = m_data.get("observed_version")
                    except Exception:
                        pass
                self_update_tools.append({
                    "tool": tid,
                    "name": tool.get("name", tid),
                    "current_version": cur_ver,
                    "mechanism": "self_update",
                })

    notices = payload.get("notices", [])
    has_actionable = bool(
        core_updates
        or runtimes_updates
        or tools_updates
        or ai_clis_updates
        or repairs_needed
        or self_update_tools
    )
    
    if not has_actionable and not could_not_check and not not_checked and not notices:
        print("Everything Engram can check is up to date.")
        if args.check:
            sys.exit(0)
        return {"status": "success", "detail": "No updates discovered"}

    if could_not_check:
        print("\nCould not check (provider failures):")
        for cnc in could_not_check:
            print(f"  - {cnc.get('component')} ({cnc.get('error_type')}: {cnc.get('detail')})")
            
    if core_updates:
        print("\nEngram core:")
        for update in core_updates:
            display_name = update.get("component") or update.get("tool") or "Engram core"
            print(f"  {display_name}: {update.get('current_version')} -> {update.get('latest_version')}")
            
    if runtimes_updates:
        print("\nRuntimes:")
        for update in runtimes_updates:
            print(f"  {update.get('tool')}: {update.get('current_version')} -> {update.get('latest_version')}")
            
    if tools_updates:
        print("\nTools:")
        for update in tools_updates:
            print(f"  {update.get('tool')}: {update.get('current_version')} -> {update.get('latest_version')}")
            
    if ai_clis_updates:
        print("\nAI CLIs:")
        for update in ai_clis_updates:
            print(f"  {update.get('tool')}: {update.get('current_version')} -> {update.get('latest_version')}")

    if self_update_tools:
        print("\nSelf-updating tools (delegated in-place update):")
        for su in self_update_tools:
            print(f"  {su.get('tool')}: active version {su.get('current_version')} (runs '{su.get('tool')} update')")
            
    if repairs_needed:
        print("\nRepairs (missing components planned for reinstall):")
        for r in repairs_needed:
            print(f"  - {r}")

    if notices:
        print("\nNotices / Manual update advisories:")
        for n in notices:
            print(f"  - {n.get('component')}: {n.get('detail')}")

    if not_checked:
        print("\nNot checked:")
        for nc in not_checked:
            print(f"  - {nc.get('component')} ({nc.get('reason')})")

    if args.check:
        if could_not_check:
            sys.exit(1)
        sys.exit(0)

    if not has_actionable:
        print("\nEverything Engram can check is up to date.")
        return {"status": "success", "detail": "No updates discovered"}

    total_changes = (
        len(core_updates)
        + len(runtimes_updates)
        + len(tools_updates)
        + len(ai_clis_updates)
        + len(repairs_needed)
        + len(self_update_tools)
    )

    if args.dry_run:
        print(f"\nDry run complete. Proposal written to {artifact_dir}")
        return {"status": "success", "detail": "Dry run complete"}

    if not args.yes:
        try:
            choice = input(f"\nApply {total_changes} changes? [y/N] ")
        except (EOFError, OSError):
            choice = "n"
        if choice.strip().lower() != "y":
            print(f"\nUpdate declined.")
            sys.exit(3)

    print("\nApplying declarations...")
    exit_code, apply_result = check_tool_updates.apply_proposal(
        artifact_dir, yes=True
    )

    if exit_code in (1, 2):
        return {"status": "failed", "detail": "Apply failed or proposal invalid/stale", "apply_result": apply_result}
    elif exit_code != 0:
        return {"status": "failed", "detail": f"Unknown exit code {exit_code}", "apply_result": apply_result}

    print("\nReconciling via provisioner (in-process)...")
    try:
        deploy_ctx = dict(ctx)
        if only_set is not None:
            deploy_ctx["only"] = only_set
        deploy_result = provisioner.deploy(deploy_ctx)
        if deploy_result.get("status") == "error":
            print(f"Provisioner deploy error: {deploy_result.get('detail')}")
            return {"status": "incomplete", "detail": "applied but deploy failed"}
    except Exception as e:
        print(f"Provisioner deploy exception: {e}")
        return {"status": "incomplete", "detail": "applied but deploy threw exception"}

    failed = deploy_result.get("failed", [])
    deferred = deploy_result.get("deferred", [])
    reverted_components = []

    if self_update_tools:
        print("\nRunning self-updates for self-managed tools...")
        for su in self_update_tools:
            tool_id = su.get("tool")
            print(f"  >>> Updating {tool_id} (in-place)...")
            res = provisioner.self_update_peer(tool_id, sys_dir)
            st = res.get("status")
            det = res.get("detail", "")
            if st == "success":
                print(f"  [OK] {tool_id} updated: {det}")
                deploy_result.setdefault("installed", []).append(tool_id)
            elif st == "already_current":
                print(f"  [OK] {tool_id} (already_current: {det})")
            elif st == "in_use_deferred":
                print(f"  [!] {tool_id} deferred: {det}")
                deferred.append(tool_id)
            else:
                print(f"  [!] {tool_id} update warning: {det}")
    
    if failed or deferred:
        # We need to revert the specific components in runtimes.json and tool-catalog.v1.json
        comp_names = []
        for item in failed + deferred:
            c = item.get("component") if isinstance(item, dict) else str(item)
            if c and c not in comp_names:
                comp_names.append(c)

        print(f"\nReverting {len(comp_names)} failed/deferred component(s)...")
        
        backup_path = apply_result.get("backup_path")
        catalog_backup_path = apply_result.get("catalog_backup_path")
        
        if backup_path and Path(backup_path).exists():
            try:
                old_runtimes = json.loads(Path(backup_path).read_text(encoding="utf-8"))
                live_runtimes_path = _SYS_DIR / "runtimes.json"
                live_runtimes = json.loads(live_runtimes_path.read_text(encoding="utf-8"))
                
                changed = False
                for comp in comp_names:
                    for section in ["runtimes", "tools"]:
                        if section in live_runtimes and section in old_runtimes and comp in live_runtimes[section]:
                            if comp in old_runtimes[section]:
                                live_runtimes[section][comp] = old_runtimes[section][comp]
                            else:
                                del live_runtimes[section][comp]
                            changed = True
                            if comp not in reverted_components:
                                reverted_components.append(comp)
                            
                if changed:
                    check_tool_updates._atomic_write_json(live_runtimes_path, live_runtimes)
            except Exception as e:
                print(f"Failed to revert runtimes.json: {e}")

        if catalog_backup_path and Path(catalog_backup_path).exists():
            try:
                old_catalog = json.loads(Path(catalog_backup_path).read_text(encoding="utf-8"))
                live_catalog_path = _SYS_DIR / provisioner.TOOL_CATALOG_FILENAME
                live_catalog = json.loads(live_catalog_path.read_text(encoding="utf-8"))
                
                changed = False
                for comp in comp_names:
                    if "tools" in live_catalog and "tools" in old_catalog:
                        # Find index in live
                        for i, tool in enumerate(live_catalog["tools"]):
                            if tool.get("tool_id") == comp:
                                # Find in old
                                old_tool = next((t for t in old_catalog["tools"] if t.get("tool_id") == comp), None)
                                if old_tool:
                                    live_catalog["tools"][i] = old_tool
                                else:
                                    del live_catalog["tools"][i]
                                changed = True
                                if comp not in reverted_components:
                                    reverted_components.append(comp)
                                break
                                
                if changed:
                    check_tool_updates._atomic_write_json(live_catalog_path, live_catalog)
            except Exception as e:
                print(f"Failed to revert tool-catalog.v1.json: {e}")

    receipt = {
        "artifact_dir": artifact_dir,
        "planned_changes": apply_result.get("planned_changes", []),
        "applied": deploy_result.get("installed", []),
        "reverted": reverted_components,
        "deferred": deferred,
        "errors": failed,
    }
    receipt_dir = _SYS_DIR / "data" / "state" / "update" / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    stamp = Path(artifact_dir).name
    receipt_path = receipt_dir / f"{stamp}.json"
    if artifact_dir:
        check_tool_updates._write_json(receipt_path, receipt)
        print(f"\nUpdate receipt written to {receipt_path}")

    # Core update handoff would go here (Section 8.4)
    if core_update:
        print("\nStaging Engram core update...")
        from core.layout import INSTALL_ROOT_ENTRIES

        target_version = core_update["latest_version"]
        temp_update_dir = _SYS_DIR / "data" / "temp" / "core-update" / target_version
        temp_update_dir.mkdir(parents=True, exist_ok=True)

        zip_path = temp_update_dir / "update.zip"
        staged_dir = temp_update_dir / "staged"
        backup_dir = temp_update_dir / "backup"

        try:
            print(f"  - Downloading {core_update['url']}...")
            _download_and_stage_core_update(
                core_update["url"], core_update["checksum_value"], zip_path, staged_dir
            )

            root_entries = list(staged_dir.iterdir())
            if len(root_entries) == 1 and root_entries[0].is_dir():
                wrapped_dir = root_entries[0]
                for item in wrapped_dir.iterdir():
                    shutil.move(str(item), str(staged_dir))
                wrapped_dir.rmdir()
                
            # Verifications
            staged_version_file = staged_dir / "_sys" / "core" / "version.json"
            if not staged_version_file.exists():
                raise ValueError("staged/_sys/core/version.json not found")
            staged_version = json.loads(staged_version_file.read_text(encoding="utf-8")).get("version")
            if staged_version != target_version:
                raise ValueError(f"staged version tag '{staged_version}' does not match target '{target_version}'")
                
            # Check root entries
            for entry in staged_dir.iterdir():
                if entry.name not in INSTALL_ROOT_ENTRIES:
                    raise ValueError(f"staged root entry '{entry.name}' not in INSTALL_ROOT_ENTRIES")
                    
            # Check no staged path falls under protected areas
            protected = [
                ".engram", "workspace",
                f"{_SYS_DIR.name}/env", f"{_SYS_DIR.name}/tools", f"{_SYS_DIR.name}/data",
                f"{_SYS_DIR.name}/runtimes.json", f"{_SYS_DIR.name}/tool-catalog.v1.json",
            ]
            if _SYS_DIR.name != "_sys":
                protected.extend([
                    "_sys/env", "_sys/tools", "_sys/data",
                    "_sys/runtimes.json", "_sys/tool-catalog.v1.json",
                ])
            for p in staged_dir.rglob("*"):
                rel_p = p.relative_to(staged_dir).as_posix()
                for prot in protected:
                    if rel_p == prot or rel_p.startswith(prot + "/"):
                        raise ValueError(f"staged path '{rel_p}' falls under protected area '{prot}'")
                    
            # Check manifest hashes
            manifest_path = staged_dir / "_sys" / "core" / "release-manifest.json"
            if manifest_path.exists():
                manifest_files = json.loads(manifest_path.read_text(encoding="utf-8")).get("files", {})
                for path_str, expected_hash in manifest_files.items():
                    target_file = staged_dir / path_str
                    if target_file.exists() and target_file.is_file():
                        actual_file_hash = provisioner._hash_file(target_file, "sha256")
                        if actual_file_hash.upper() != expected_hash.upper():
                            raise ValueError(f"staged file '{path_str}' hash mismatch")

            # Handoff
            print("  - Handing off to core_update_helper.ps1...")
            
            helper_src = _SYS_DIR / "core" / "core_update_helper.ps1"
            helper_dest = temp_update_dir / "core_update_helper.ps1"
            shutil.copyfile(helper_src, helper_dest)
            
            journal_path = temp_update_dir / "journal.json"
            
            plan_payload = {
                "target_dir": str(_PORTABLE_ROOT),
                "staged_dir": str(staged_dir),
                "backup_dir": str(backup_dir),
                "journal_path": str(journal_path),
                "parent_pid": os.getpid(),
                "sys_dir_name": _SYS_DIR.name,
            }
            plan_file = temp_update_dir / "plan.json"
            plan_file.write_text(json.dumps(plan_payload, indent=2, ensure_ascii=False), encoding="utf-8")
            
            provisioner._launch_detached_powershell_helper(
                helper_dest, plan_file, temp_update_dir
            )
            
            print(f"\nEngram will finish updating to {target_version} when this window closes.")
            receipt["core_handoff"] = True
            check_tool_updates._atomic_write_json(receipt_path, receipt)
            
        except Exception as e:
            print(f"  - Core update staging failed: {e}")
            failed.append("Engram core")
            receipt["errors"] = failed
            check_tool_updates._atomic_write_json(receipt_path, receipt)
            sys.exit(1)

    if failed:
        sys.exit(1)
        
    return {"status": "success", "apply_result": apply_result}
