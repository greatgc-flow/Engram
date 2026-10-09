"""Test/CI-only offline upgrade staging and helper handoff harness."""
import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SYS_DIR_DEFAULT = _REPO_ROOT / "_sys"
if str(_SYS_DIR_DEFAULT) not in sys.path:
    sys.path.insert(0, str(_SYS_DIR_DEFAULT))
if str(_SYS_DIR_DEFAULT / "core") not in sys.path:
    sys.path.insert(0, str(_SYS_DIR_DEFAULT / "core"))

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
    if not helper_src.exists():
        helper_src = _SYS_DIR / "core" / "core_update_helper.ps1"
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


def seed_user_data(engram_dir: Path) -> None:
    """Seed user data under .engram/ including structured, binary, and Unicode content."""
    engram_dir = Path(engram_dir)
    engram_dir.mkdir(parents=True, exist_ok=True)

    # 1. Structured JSON
    (engram_dir / "user_config.json").write_text(
        json.dumps({"theme": "midnight", "user_id": "u-42", "active": True}, indent=2),
        encoding="utf-8",
    )

    # 2. Multilingual Unicode text
    unicode_text = (
        "Engram Memory Vault 🧠\n"
        "Japanese: 日本語テストノート (ひらがな・カタカナ・漢字)\n"
        "Spanish: ¿Cómo estás niño? ¡Mañana café!\n"
        "Russian: Привет, как дела? Тестовый файл.\n"
        "Symbols: €100 + £50 = ¥20,000 | 🚀 ⚡ 🔒\n"
    )
    (engram_dir / "unicode_notes.md").write_text(unicode_text, encoding="utf-8")

    # 3. Raw arbitrary binary with all byte values 0x00-0xFF
    full_byte_range = bytes(range(256)) * 4 + b"\x00\xff\xfe\x00\x1a\x04\x00"
    (engram_dir / "binary_store.dat").write_bytes(full_byte_range)

    # 4. Nested subfolder with binary payload and Unicode path
    sub_dir = engram_dir / "vault_sub" / "데이터_data"
    sub_dir.mkdir(parents=True, exist_ok=True)
    (sub_dir / "random_entropy.bin").write_bytes(bytes([b ^ 0x5C for b in full_byte_range]))
    (sub_dir / "accented_filename_é_ü.txt").write_text("accented file payload", encoding="utf-8")


def take_inventory(root_dir: Path) -> dict[str, str]:
    """Capture file inventory mapping relative POSIX path to SHA-256 digest."""
    inventory: dict[str, str] = {}
    if not root_dir.exists():
        return inventory
    for path in sorted(root_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root_dir).as_posix()
            inventory[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return inventory


def assert_inventory_identical(before: dict[str, str], after: dict[str, str]) -> None:
    """Assert two inventories have zero additions, deletions, or hash mismatches."""
    added = set(after.keys()) - set(before.keys())
    deleted = set(before.keys()) - set(after.keys())
    mismatched = {k: (before[k], after[k]) for k in before.keys() & after.keys() if before[k] != after[k]}
    if added or deleted or mismatched:
        raise ValueError(
            f"user data altered during upgrade: added={sorted(added)}, deleted={sorted(deleted)}, mismatched={mismatched}"
        )


def run_upgrade_gate(
    target_dir: Path,
    candidate_zip: Path,
    candidate_json_path: Path,
    previous_tag: str,
    out_evidence_path: Path | None = None,
    seed_if_missing: bool = False,
) -> dict[str, Any]:
    """Run offline upgrade check of target_dir against candidate_zip and record evidence."""
    target_dir = Path(target_dir).resolve()
    candidate_zip = Path(candidate_zip).resolve()
    candidate_json_path = Path(candidate_json_path).resolve()
    previous_tag = str(previous_tag).strip()

    if not target_dir.is_dir():
        raise ValueError(f"isolated target dir does not exist: {target_dir}")
    if not candidate_zip.is_file():
        raise ValueError(f"candidate zip does not exist: {candidate_zip}")
    if not candidate_json_path.is_file():
        raise ValueError(f"candidate json does not exist: {candidate_json_path}")
    if not previous_tag:
        raise ValueError("previous tag must not be empty")

    candidate_data = json.loads(candidate_json_path.read_text(encoding="utf-8"))
    candidate_tag = candidate_data.get("tag")
    if candidate_tag and previous_tag == candidate_tag:
        raise ValueError(f"previous tag '{previous_tag}' matches candidate tag '{candidate_tag}'")

    candidate_sha256s = candidate_data.get("candidate_sha256s", {})
    if not candidate_sha256s:
        raise ValueError("candidate json has no candidate_sha256s")

    cand_sha = candidate_sha256s.get(candidate_zip.name)
    if not cand_sha:
        for k, v in candidate_sha256s.items():
            if k.endswith(candidate_zip.name) or Path(k).name == candidate_zip.name:
                cand_sha = v
                break
    if not cand_sha:
        zip_entries = [v for k, v in candidate_sha256s.items() if k.endswith(".zip")]
        if len(zip_entries) == 1:
            cand_sha = zip_entries[0]
    if not cand_sha:
        raise ValueError(f"could not find hash for candidate zip {candidate_zip.name} in candidate.json")

    actual_zip_sha = hashlib.sha256(candidate_zip.read_bytes()).hexdigest()
    if actual_zip_sha.lower() != cand_sha.lower():
        raise ValueError(
            f"candidate zip actual hash {actual_zip_sha} does not match candidate.json hash {cand_sha}"
        )

    cand_version = None
    with zipfile.ZipFile(candidate_zip, "r") as zf:
        for name in zf.namelist():
            norm = name.replace("\\", "/")
            if norm.endswith("_sys/core/version.json"):
                vdata = json.loads(zf.read(name).decode("utf-8"))
                cand_version = vdata.get("version")
                break
    if not cand_version:
        raise ValueError("candidate zip missing _sys/core/version.json")

    engram_dir = target_dir / ".engram"
    if not engram_dir.exists() or not any(engram_dir.iterdir()):
        if seed_if_missing:
            seed_user_data(engram_dir)
        else:
            raise ValueError(f"user data missing in {engram_dir}; seed user data before upgrade")

    before_inventory = take_inventory(engram_dir)
    if not before_inventory:
        raise ValueError("user data inventory is empty before upgrade")

    os.environ["ENGRAM_UPDATE_CANDIDATE_ZIP"] = str(candidate_zip)
    os.environ["ENGRAM_UPDATE_CANDIDATE_SHA256"] = cand_sha
    os.environ["ENGRAM_UPDATE_SKIP_PROCESS_WAIT"] = "1"

    staged_res = stage_and_handoff_core_update(
        core_update={
            "latest_version": cand_version,
            "url": candidate_zip.as_uri(),
            "checksum_value": cand_sha,
        },
        sys_dir=target_dir / "_sys",
        target_dir=target_dir,
        parent_pid=999999,
    )

    proc = staged_res["process"]
    ret = proc.wait(timeout=60)
    if ret != 0:
        raise RuntimeError(f"core update helper process failed with exit code {ret}")

    journal_path = staged_res["journal_path"]
    if not journal_path.exists():
        raise RuntimeError("upgrade journal.json was not created")
    journal = json.loads(journal_path.read_text(encoding="utf-8-sig"))
    if journal.get("status") != "COMPLETED":
        raise RuntimeError(f"upgrade journal status is '{journal.get('status')}', expected COMPLETED")

    after_inventory = take_inventory(engram_dir)
    assert_inventory_identical(before_inventory, after_inventory)

    installed_version_file = target_dir / "_sys" / "core" / "version.json"
    if not installed_version_file.exists():
        raise RuntimeError("target _sys/core/version.json missing after upgrade")
    installed_version = json.loads(installed_version_file.read_text(encoding="utf-8")).get("version")
    if installed_version != cand_version:
        raise RuntimeError(
            f"installed version '{installed_version}' does not match candidate version '{cand_version}'"
        )

    evidence = {
        "status": "PASS",
        "candidate_sha256s": candidate_sha256s,
        "previous_tag": previous_tag,
        "cancelled": False,
        "skipped": False,
    }
    if os.environ.get("GITHUB_RUN_ID"):
        evidence["run_id"] = os.environ["GITHUB_RUN_ID"]
    if os.environ.get("GITHUB_RUN_ATTEMPT"):
        evidence["run_attempt"] = os.environ["GITHUB_RUN_ATTEMPT"]

    if out_evidence_path:
        out_path = Path(out_evidence_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")

    seed_p = subparsers.add_parser("seed", help="Seed user data into target directory")
    seed_p.add_argument("--target-dir", required=True, help="Isolated target directory")

    run_p = subparsers.add_parser("run", help="Run upgrade harness against candidate")
    run_p.add_argument("--target-dir", required=True, help="Isolated target directory")
    run_p.add_argument("--candidate-zip", required=True, help="Candidate portable zip")
    run_p.add_argument("--candidate-json", required=True, help="Path to release/candidate.json")
    run_p.add_argument("--prev-tag", required=True, help="Previous release tag")
    run_p.add_argument("--out", required=False, default=None, help="Output evidence JSON path")
    run_p.add_argument("--seed", action="store_true", help="Seed user data if missing")

    parser.add_argument("--target-dir", help="Isolated target directory")
    parser.add_argument("--candidate-zip", help="Candidate portable zip")
    parser.add_argument("--candidate-json", help="Path to release/candidate.json")
    parser.add_argument("--prev-tag", help="Previous release tag")
    parser.add_argument("--out", default=None, help="Output evidence JSON path")
    parser.add_argument("--seed", action="store_true", help="Seed user data")

    args = parser.parse_args(argv)

    if args.command == "seed":
        target = Path(args.target_dir)
        seed_user_data(target / ".engram" if target.name != ".engram" else target)
        print(f"PASS: user data seeded under {target / '.engram'}")
        return 0

    target_dir = args.target_dir
    candidate_zip = args.candidate_zip
    candidate_json = args.candidate_json
    prev_tag = args.prev_tag
    out_evidence = args.out
    seed_flag = args.seed

    if not (target_dir and candidate_zip and candidate_json and prev_tag):
        parser.print_help()
        return 2

    try:
        run_upgrade_gate(
            target_dir=Path(target_dir),
            candidate_zip=Path(candidate_zip),
            candidate_json_path=Path(candidate_json),
            previous_tag=prev_tag,
            out_evidence_path=Path(out_evidence) if out_evidence else None,
            seed_if_missing=seed_flag,
        )
        print(f"PASS: upgrade verified and evidence emitted to {out_evidence}")
        return 0
    except Exception as exc:
        print(f"HOLD: upgrade harness error: {exc}", file=sys.stderr)
        if out_evidence:
            try:
                cand_data = json.loads(Path(candidate_json).read_text(encoding="utf-8")) if Path(candidate_json).is_file() else {}
                fail_evidence = {
                    "status": "HOLD",
                    "candidate_sha256s": cand_data.get("candidate_sha256s", {}),
                    "previous_tag": prev_tag,
                    "cancelled": False,
                    "skipped": False,
                    "error": str(exc),
                }
                if os.environ.get("GITHUB_RUN_ID"):
                    fail_evidence["run_id"] = os.environ["GITHUB_RUN_ID"]
                if os.environ.get("GITHUB_RUN_ATTEMPT"):
                    fail_evidence["run_attempt"] = os.environ["GITHUB_RUN_ATTEMPT"]
                out_p = Path(out_evidence)
                out_p.parent.mkdir(parents=True, exist_ok=True)
                out_p.write_text(json.dumps(fail_evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            except Exception:
                pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
