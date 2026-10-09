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

from core import provisioner

# Run the actual public updater in a child process so its helper can wait for exit.
_WORKER = r"""
import sys
from pathlib import Path
code_sys, target, fault = map(Path, sys.argv[1:4])
sys.path[:0] = [str(code_sys), str(code_sys / "core")]
from core import updater, provisioner
# Candidate fallback uses candidate code, with installation paths bound to the previous tree.
for module in list(sys.modules.values()):
    filename = getattr(module, "__file__", None)
    if not filename or not Path(filename).resolve().is_relative_to(code_sys):
        continue
    for key, value in list(vars(module).items()):
        if isinstance(value, Path) and value.is_relative_to(code_sys.parent):
            setattr(module, key, target / value.relative_to(code_sys.parent))
import subprocess, hashlib, json, shutil
original_launch = provisioner._launch_detached_powershell_helper
original_helper = code_sys / "core/core_update_helper.ps1"
def launch(helper, plan, workdir):
    if code_sys != target / "_sys":
        shutil.copyfile(original_helper, helper)
    if fault.is_file():
        return subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", str(fault),
            "-Helper", str(helper), "-PlanPath", str(plan)], cwd=workdir)
    return original_launch(helper, plan, workdir)
provisioner._launch_detached_powershell_helper = launch
provisioner._default_sys_dir = lambda: target / "_sys"
result = updater.run({"args": ["--only", "core", "--yes"],
                      "sys_dir": target / "_sys", "base_dir": target, "state": {}})
if result.get("status") != "success":
    raise SystemExit(str(result))
if fault.is_file():
    inventory = {p.relative_to(target).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in target.rglob("*") if p.is_file()
                 and not p.relative_to(target).as_posix().startswith("_sys/data/temp/")}
    fault.with_suffix(".inventory.json").write_text(json.dumps(inventory), encoding="utf-8")

"""

_FAULT = r"""
param($Helper, $PlanPath)
$global:payload = Get-Content -LiteralPath $PlanPath -Raw | ConvertFrom-Json
function Copy-Item {
    param($Path, $LiteralPath, $Destination, [switch]$Force, [switch]$Recurse)
    $source = if ($LiteralPath) { $LiteralPath } else { $Path }
    if ([string]$source -like "$($global:payload.backup_dir)*") {
        $status = (Get-Content $global:payload.journal_path -Raw | ConvertFrom-Json).status
        if ($status -ne 'ROLLBACK_IN_PROGRESS') { throw 'undo journal not in progress' }
        Set-Content ($global:payload.journal_path + '.undo') $status
    }
    if ($LiteralPath) {
        Microsoft.PowerShell.Management\Copy-Item -LiteralPath $LiteralPath -Destination $Destination -Force:$Force -Recurse:$Recurse
    } else {
        Microsoft.PowerShell.Management\Copy-Item -Path $Path -Destination $Destination -Force:$Force -Recurse:$Recurse
    }
    if ([string]$source -like "$($global:payload.staged_dir)*") {
        throw 'deterministic failure after replacement'
    }
}
& $Helper -PlanPath $PlanPath
exit $LASTEXITCODE
"""


def public_update(target: Path, code_sys: Path, fault: Path, env: dict, version: str, expected: str) -> None:
    import subprocess
    import time
    journal_path = target / "_sys/data/temp/core-update" / version / "journal.json"
    if journal_path.exists():
        raise RuntimeError("pre-existing upgrade journal")
    result = subprocess.run([sys.executable, "-c", _WORKER, str(code_sys), str(target), str(fault)],
                            env=env, cwd=target, timeout=120)
    if result.returncode:
        raise RuntimeError(f"public updater failed: {result.returncode}")
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            journal = json.loads(journal_path.read_text(encoding="utf-8-sig"))
            if journal.get("status") in ("COMPLETED", "FAILED_ROLLED_BACK", "FAILED_ROLLBACK_FAILED"):
                break
        except (OSError, ValueError):
            pass
        time.sleep(.1)
    else:
        raise RuntimeError("helper journal timed out")
    if journal["status"] != expected:
        raise RuntimeError(f"expected {expected}, got {journal['status']}")
    if expected == "FAILED_ROLLED_BACK":
        if Path(str(journal_path) + ".undo").read_text(encoding="utf-8-sig").strip() != "ROLLBACK_IN_PROGRESS":
            raise RuntimeError("rollback did not expose in-progress journal")


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

    import tempfile
    env = dict(os.environ, ENGRAM_UPDATE_CANDIDATE_ZIP=str(candidate_zip),
               ENGRAM_UPDATE_CANDIDATE_SHA256=cand_sha)
    previous_sys = target_dir / "_sys"
    seam_files = (previous_sys / "core/version_resolver.py", previous_sys / "core/provisioner.py")
    previous_seam = all(p.is_file() and "ENGRAM_UPDATE_CANDIDATE_SHA256" in p.read_text(encoding="utf-8")
                        for p in seam_files)
    updater_source = "previous" if previous_seam else "candidate"
    with tempfile.TemporaryDirectory(prefix="engram-upgrade-", dir=target_dir.parent) as temp:
        work = Path(temp)
        candidate_root = work / "candidate"
        provisioner._extract(candidate_zip, candidate_root)
        code_sys = previous_sys if previous_seam else candidate_root / "_sys"
        if not code_sys.is_dir():
            raise ValueError("candidate code root missing")
        rollback_root = work / "rollback"
        shutil.copytree(target_dir, rollback_root)
        fault = work / "replacement-failure.ps1"
        fault.write_text(_FAULT, encoding="utf-8")
        # Compare every installed file at handoff; exclude only helper artifacts.
        def installed_inventory(root):
            return {k: v for k, v in take_inventory(root).items()
                    if not k.startswith("_sys/data/temp/")}
        rollback_code = rollback_root / "_sys" if previous_seam else code_sys
        public_update(rollback_root, rollback_code, fault, env, cand_version, "FAILED_ROLLED_BACK")
        before_tree = json.loads(fault.with_suffix(".inventory.json").read_text(encoding="utf-8"))
        assert_inventory_identical(before_tree, installed_inventory(rollback_root))
        public_update(target_dir, code_sys, work / "no-fault", env, cand_version, "COMPLETED")

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
        "updater_source": updater_source,
        "scenarios": {"upgrade": "PASS", "rollback": "PASS"},
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
