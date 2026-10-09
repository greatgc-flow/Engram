"""Test/CI-only offline upgrade staging and helper handoff harness."""
import json
import os
import shutil
from pathlib import Path
from typing import Any

from core import provisioner, updater

_SYS_DIR = updater._SYS_DIR
_PORTABLE_ROOT = updater._PORTABLE_ROOT
_download_and_stage_core_update = updater._download_and_stage_core_update


def stage_and_handoff_core_update(
    core_update: dict[str, Any],
    sys_dir: Path | None = None,
    target_dir: Path | None = None,
    parent_pid: int | None = None,
) -> dict[str, Any]:
    """Securely stage, validate, and hand off a core update to core_update_helper.ps1."""
    from core.layout import INSTALL_ROOT_ENTRIES

    sys_dir = sys_dir or _SYS_DIR
    target_dir = target_dir or _PORTABLE_ROOT
    parent_pid = os.getpid() if parent_pid is None else parent_pid

    target_version = core_update["latest_version"]
    if os.environ.get("ENGRAM_UPDATE_CANDIDATE_ZIP", "").strip():
        import re
        if not isinstance(target_version, str) or not re.fullmatch(
            r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?(?:\+[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?",
            target_version,
        ):
            raise ValueError("invalid candidate version")
    temp_update_dir = sys_dir / "data" / "temp" / "core-update" / target_version
    temp_update_dir.mkdir(parents=True, exist_ok=True)

    zip_path = temp_update_dir / "update.zip"
    staged_dir = temp_update_dir / "staged"
    backup_dir = temp_update_dir / "backup"

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
        f"{sys_dir.name}/env", f"{sys_dir.name}/tools",
        f"{sys_dir.name}/data/state", f"{sys_dir.name}/data/logs",
        f"{sys_dir.name}/data/cache", f"{sys_dir.name}/data/temp",
        f"{sys_dir.name}/data/backups",
        f"{sys_dir.name}/runtimes.json", f"{sys_dir.name}/tool-catalog.v1.json",
    ]
    if sys_dir.name != "_sys":
        protected.extend([
            "_sys/env", "_sys/tools",
            "_sys/data/state", "_sys/data/logs",
            "_sys/data/cache", "_sys/data/temp",
            "_sys/data/backups",
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

    helper_src = sys_dir / "core" / "core_update_helper.ps1"
    helper_dest = temp_update_dir / "core_update_helper.ps1"
    shutil.copyfile(helper_src, helper_dest)

    journal_path = temp_update_dir / "journal.json"

    plan_payload = {
        "target_dir": str(target_dir),
        "staged_dir": str(staged_dir),
        "backup_dir": str(backup_dir),
        "journal_path": str(journal_path),
        "parent_pid": parent_pid,
        "sys_dir_name": sys_dir.name,
    }
    candidate_zip = os.environ.get("ENGRAM_UPDATE_CANDIDATE_ZIP", "").strip()
    candidate_sha = os.environ.get("ENGRAM_UPDATE_CANDIDATE_SHA256", "").strip()
    candidate_seam = (
        bool(candidate_zip)
        and core_update["url"] == Path(candidate_zip).resolve().as_uri()
        and len(candidate_sha) == 64
        and all(c in "0123456789abcdefABCDEF" for c in candidate_sha)
        and candidate_sha.lower() == core_update["checksum_value"].lower()
    )
    if candidate_seam and os.environ.get("ENGRAM_UPDATE_SKIP_PROCESS_WAIT") == "1":
        plan_payload["skip_process_wait"] = True

    plan_file = temp_update_dir / "plan.json"
    plan_file.write_text(json.dumps(plan_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    proc = provisioner._launch_detached_powershell_helper(
        helper_dest, plan_file, temp_update_dir
    )

    return {
        "status": "staged",
        "target_version": target_version,
        "temp_update_dir": temp_update_dir,
        "staged_dir": staged_dir,
        "backup_dir": backup_dir,
        "plan_file": plan_file,
        "journal_path": journal_path,
        "helper_script": helper_dest,
        "process": proc,
    }


