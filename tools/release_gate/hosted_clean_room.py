"""Hosted clean-room candidate driver (EN-GAP-P1-005/clean-room-hosted).

Runs candidate-contained verification in a fresh isolated directory with NO repo
checkout or development tree on a hosted ephemeral runner (e.g. windows-latest).
Emits candidate-bound sandbox_evidence.json with provider 'hosted-ephemeral-vm'
and runner_environment 'github-hosted'.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

import importlib.util
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from installed_artifact_suite import run_checks

_spec = importlib.util.spec_from_file_location(
    "release_evidence_checks", Path(__file__).resolve().parents[2] / "_sys/checks/release_evidence.py"
)
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
Hold = base.Hold


def default_runner(cmd: list[str], *, cwd: Path, env: dict[str, str], timeout: int = 600) -> str:
    """Execute command on Windows runner via cmd.exe /c."""
    full_cmd = ["cmd.exe", "/c", *cmd]
    result = subprocess.run(
        full_cmd,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise Hold(f"clean-room check '{' '.join(cmd)}' exited {result.returncode}: {err}")
    return result.stdout.strip()


def run_clean_room_checks(clean_root: Path, *, runner=None) -> None:
    """Execute candidate-contained clean-room checks: bootstrap, doctor, and update check."""
    if runner is None:
        runner = default_runner

    env = dict(os.environ, CI="1", PYTHONUTF8="1")

    try:
        run_checks(clean_root, runner=runner, env=env)
    except ValueError as exc:
        raise Hold(str(exc)) from exc


def execute_hosted_clean_room(
    candidate_path: Path,
    clean_root: Path,
    out_path: Path,
    *,
    assets_dir: Path | None = None,
    candidate_zip: Path | None = None,
    provider: str = "hosted-ephemeral-vm",
    runner_environment: str = "github-hosted",
    workflow_run_id: str | None = None,
    image: str | None = None,
    runner=None,
) -> dict:
    """Validate clean-room isolation, run checks, and emit evidence."""
    candidate = base._read(candidate_path)
    base._identity(candidate)
    hashes = base._hashes(candidate.get("candidate_sha256s"))

    if Path(clean_root).is_symlink():
        raise Hold("clean-room root must be fresh (must not be a link)")
    clean_root = Path(clean_root).resolve()
    out_path = Path(out_path).resolve()

    # Verify absence of git dev tree in clean root
    if (clean_root / ".git").exists():
        raise Hold("clean-room root must not contain a git repository (.git)")
    if (clean_root / "requirements-dev.txt").exists():
        raise Hold("clean-room root must not contain dev requirements (requirements-dev.txt)")

    if clean_root.exists() or clean_root.is_symlink():
        raise Hold("clean-room root must be fresh (must not exist)")
    archive = candidate_zip
    if archive is None and assets_dir is not None:
        zips = list(Path(assets_dir).glob("*.zip"))
        if len(zips) != 1:
            raise Hold(f"expected exactly one portable zip in assets, found {len(zips)}")
        archive = zips[0]
    if archive is None:
        raise Hold("no candidate archive was supplied")
    archive = Path(archive)
    if assets_dir is not None:
        name = archive.resolve().relative_to(Path(assets_dir).resolve()).as_posix()
    else:
        matches = [name for name in hashes if Path(name).name == archive.name]
        if len(matches) != 1:
            raise Hold("archive must identify exactly one candidate asset")
        name = matches[0]
    # Extract the same bytes that were hashed; never reopen an unverified archive.
    import io
    payload = archive.read_bytes()
    if hashlib.sha256(payload).hexdigest() != hashes.get(name):
        raise Hold("candidate archive SHA256 mismatch")
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        for member in zf.infolist():
            target = (clean_root / member.filename).resolve()
            if not target.is_relative_to(clean_root):
                raise Hold("archive path escapes clean-room root")
        clean_root.mkdir(parents=True, exist_ok=False)
        zf.extractall(clean_root)

    for forbidden in (".git", "requirements-dev.txt"):
        if (clean_root / forbidden).exists():
            raise Hold(f"candidate clean-room contains {forbidden}")

    # Run the clean-room suite
    run_clean_room_checks(clean_root, runner=runner)

    run_id = os.environ.get("GITHUB_RUN_ID") or "1"
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT") or "1"
    resolved_run_id = str(workflow_run_id or run_id)
    resolved_image = str(image or os.environ.get("RUNNER_IMAGE_VERSION") or os.environ.get("ImageVersion") or "windows-latest")

    evidence = {
        "status": "PASS",
        "candidate_sha256s": hashes,
        "cancelled": False,
        "skipped": False,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "provider": provider,
        "runner_environment": runner_environment,
        "workflow_run_id": resolved_run_id,
        "image": resolved_image,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return evidence


def main(argv: list[str] | None = None, *, runner=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path, help="Path to frozen candidate.json")
    parser.add_argument("--clean-root", required=True, type=Path, help="Fresh directory for candidate extraction")
    parser.add_argument("--out", required=True, type=Path, help="Path to emit sandbox_evidence.json")
    parser.add_argument("--assets", type=Path, default=None, help="Optional release/assets directory")
    parser.add_argument("--candidate-zip", type=Path, default=None, help="Optional candidate ZIP archive")
    parser.add_argument("--provider", default="hosted-ephemeral-vm", help="Evidence provider identifier")
    parser.add_argument("--runner-environment", default="github-hosted", help="Runner environment identifier")
    parser.add_argument("--workflow-run-id", default=None, help="Workflow run ID override")
    parser.add_argument("--image", default=None, help="Runner image version string override")
    args = parser.parse_args(argv)

    run_id = os.environ.get("GITHUB_RUN_ID") or "1"
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT") or "1"
    workflow_run_id = args.workflow_run_id or run_id
    image = args.image or os.environ.get("RUNNER_IMAGE_VERSION") or os.environ.get("ImageVersion") or "windows-latest"

    fallback_evidence = {
        "status": "HOLD",
        "candidate_sha256s": {},
        "cancelled": False,
        "skipped": False,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "provider": args.provider,
        "runner_environment": args.runner_environment,
        "workflow_run_id": str(workflow_run_id),
        "image": str(image),
    }

    try:
        candidate_data = base._read(args.candidate)
        fallback_evidence["candidate_sha256s"] = candidate_data.get("candidate_sha256s", {})
        evidence = execute_hosted_clean_room(
            args.candidate,
            args.clean_root,
            args.out,
            assets_dir=args.assets,
            candidate_zip=args.candidate_zip,
            provider=args.provider,
            runner_environment=args.runner_environment,
            workflow_run_id=workflow_run_id,
            image=image,
            runner=runner,
        )
        print("PASS: hosted clean-room candidate verified")
        return 0
    except Exception as exc:
        fallback_evidence["reason"] = str(exc)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(fallback_evidence, indent=2) + "\n", encoding="utf-8")
        print(f"HOLD: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
