"""self_care.py - Event-based self-care pipeline.

Usage:
    python self_care.py [--trigger session_end|error_threshold|commit_interval|manual]

Steps: Observe -> Validate -> Cleanup -> DocsMECE -> Scan -> Propose -> LessonGrad -> Sync -> Record
Step failures are non-blocking: errors logged, remaining steps continue.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


_CHECKS_DIR = Path(__file__).parent
_SYS_DIR = _CHECKS_DIR.parent
_OUTPUT_TAIL_LIMIT = 1000
_SATURATION_SEEN_FILENAME = "saturation-proposals-seen.json"
_LESSON_GRADUATION_SEEN_FILENAME = "lesson-graduation-proposals-seen.json"
_PROPOSAL_DEDUP_WINDOW_DAYS = 7


def _findings_fingerprint(scan_findings: str) -> str:
    """Stable fingerprint of a scan-findings block, insensitive to volatile fields.

    The saturation-scan stdout leads with a "[START] ... commit_count=N" (or
    "[SKIP] ...") line that changes every run even when the underlying
    findings are identical; strip it before hashing so re-detecting the same
    drift doesn't look like a new fingerprint each time.
    """
    normalized_lines = [
        line for line in scan_findings.splitlines()
        if not line.startswith("[START]") and not line.startswith("[SKIP]")
    ]
    normalized = "\n".join(normalized_lines).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


_LOCK_ACQUIRE_TIMEOUT_SECONDS = 5.0
_PROPOSAL_ADD_SUBPROCESS_TIMEOUT_SECONDS = 20.0
# Must stay comfortably above the critical section's bounded worst-case hold
# time (~_PROPOSAL_ADD_SUBPROCESS_TIMEOUT_SECONDS) or a live-but-slow holder's
# lock can be mistaken for one left behind by a dead process and stolen out
# from under it (cross-review finding, cx, 2026-08-02).
_LOCK_STALE_AFTER_SECONDS = 60.0


@contextlib.contextmanager
def _file_lock(lock_path: Path, timeout: float = _LOCK_ACQUIRE_TIMEOUT_SECONDS):
    """Best-effort exclusive lock via atomic file creation.

    Yields whether the lock was actually acquired. Callers MUST fail closed
    (skip the mutating action) when this is False rather than proceeding
    unprotected -- silently proceeding under contention was an earlier
    version's bug: it defeated the point of locking and let a slow first
    call and a timed-out second call both mutate state (cross-review
    finding, cx, 2026-08-02).

    Uses `time.monotonic()` for the acquisition deadline so a backward
    wall-clock adjustment (NTP sync, DST, manual clock change) can't extend
    the wait indefinitely (cross-review finding, cx, 2026-08-02).

    A lock file left behind by a process that died mid-hold (SIGKILL, power
    loss -- the `finally` below never runs) is stolen once its mtime is older
    than `_LOCK_STALE_AFTER_SECONDS`, so a single crash doesn't permanently
    disable mutual exclusion for every run afterward (cross-review finding,
    ag, 2026-08-02). This is still a best-effort, not a hard guarantee (no
    ownership token/lease -- a live holder stuck past the stale threshold can
    still have its lock stolen); acceptable here because the failure mode of
    this specific lock is at most one extra duplicate proposal, never data
    loss or corruption.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    fd = None
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                age = time.time() - lock_path.stat().st_mtime
            except OSError:
                age = 0.0
            if age > _LOCK_STALE_AFTER_SECONDS:
                # Best-effort steal; if unlink keeps failing (e.g. a real
                # live holder, not a dead one, or a permissions issue) this
                # must still fall through to the timeout bound below rather
                # than spin here forever.
                with contextlib.suppress(OSError):
                    lock_path.unlink()
            if time.monotonic() - start > timeout:
                fd = None
                break
            time.sleep(0.05)
    try:
        yield fd is not None
    finally:
        if fd is not None:
            os.close(fd)
            try:
                lock_path.unlink()
            except OSError:
                pass


def _parse_ts(ts: str) -> datetime:
    """Parse lesson source_ref timestamp (YYYYMMDDTHHMMSS or ISO8601) to UTC datetime."""
    ts = ts.strip()
    if not ts:
        return datetime.min.replace(tzinfo=timezone.utc)

    # compact form: 20260614T000000
    if len(ts) == 15 and ts[8] == "T":
        try:
            return datetime.strptime(ts, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    # ISO8601
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(ts[:len(fmt)], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return datetime.min.replace(tzinfo=timezone.utc)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _tail(value: object, limit: int = _OUTPUT_TAIL_LIMIT) -> str:
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = value
    else:
        text = str(value)

    if len(text) <= limit:
        return text
    return text[-limit:]


def _record_checked_step_error(
    state: dict,
    *,
    step: str,
    cmd: list[object],
    returncode: int,
    stdout: object = "",
    stderr: object = "",
) -> None:
    state.setdefault("errors", []).append({
        "step": step,
        "cmd": [str(part) for part in cmd],
        "returncode": int(returncode),
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
        "ts": _utc_now(),
        "severity": "warn",
    })


def _run_checked_step(
    state: dict,
    step: str,
    cmd: list[object],
    timeout: float | None = None,
) -> subprocess.CompletedProcess:
    """Run a subprocess and record structured state errors on nonzero/exception.

    This intentionally calls subprocess.run through the module-level subprocess
    import so existing tests and callers that patch "subprocess.run" keep working.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception as exc:
        result = subprocess.CompletedProcess(
            args=cmd,
            returncode=1,
            stdout="",
            stderr=f"{type(exc).__name__}: {exc}",
        )
        _record_checked_step_error(
            state,
            step=step,
            cmd=cmd,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
        return result

    if result.returncode != 0:
        _record_checked_step_error(
            state,
            step=step,
            cmd=cmd,
            returncode=result.returncode,
            stdout=getattr(result, "stdout", ""),
            stderr=getattr(result, "stderr", ""),
        )

    return result


class SelfCare:
    def __init__(self, sys_dir: Path | None = None, archive_dir: Path | None = None):
        self.sys_dir = Path(sys_dir) if sys_dir else _SYS_DIR
        self.archive_dir = Path(archive_dir) if archive_dir else self.sys_dir.parent / "_archive"
        self.state: dict = {
            "health": {},
            "directives": [],
            "scan_findings": "",
            "steps_completed": [],
            "errors": [],
        }

    # Step 1: Observe

    def observe(self) -> None:
        health_path = self.sys_dir / "health.json"
        if health_path.exists():
            try:
                self.state["health"] = json.loads(health_path.read_text(encoding="utf-8"))
            except Exception:
                self.state["health"] = {}

        directives_path = self.sys_dir / "runtime-directives.jsonl"
        directives = []
        if directives_path.exists():
            for line in directives_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        directives.append(json.loads(line))
                    except Exception:
                        pass
        self.state["directives"] = directives
        self.state["steps_completed"].append("observe")

    # Step 2: Validate

    def validate(self) -> None:
        virtualizer = self.sys_dir / "core" / "virtualizer.py"
        if not virtualizer.exists():
            virtualizer = _CHECKS_DIR.parent / "core" / "virtualizer.py"

        result = _run_checked_step(
            self.state,
            "validate",
            [sys.executable, str(virtualizer), "--status"],
        )
        if result.returncode == 0:
            self.state["steps_completed"].append("validate")

    # Step 3: Cleanup

    def cleanup(self) -> None:
        now = time.time()
        valid = [
            d for d in self.state["directives"]
            if d.get("timestamp", 0) + d.get("ttl", float("inf")) >= now
        ]
        self.state["directives"] = valid

        directives_path = self.sys_dir / "runtime-directives.jsonl"
        if directives_path.exists():
            lines = "\n".join(json.dumps(d) for d in valid)
            directives_path.write_text(lines + "\n" if lines else "", encoding="utf-8")

        self.state["steps_completed"].append("cleanup")

    # Step 3: Docs MECE

    def docs_mece(self) -> None:
        mece_script = _CHECKS_DIR / "check_docs_mece.py"
        if not mece_script.exists():
            self.state["steps_completed"].append("docs_mece")
            return

        result = subprocess.run(
            [sys.executable, str(mece_script), "--checks", "CHK-01,CHK-02", "--json"],
            capture_output=True,
            text=True,
        )
        try:
            out = json.loads(result.stdout)
        except Exception:
            out = {}
        self.state["docs_mece"] = out
        if result.returncode != 0:
            summary = out.get("summary", {})
            self.state["errors"].append(f"docs_mece: CHK failures {summary}")
        self.state["steps_completed"].append("docs_mece")

    # Step 4: Scan

    def scan(self) -> None:
        scan_script = _CHECKS_DIR / "saturation_scan.py"
        result = subprocess.run(
            [sys.executable, str(scan_script)],
            capture_output=True,
            text=True,
        )
        self.state["scan_findings"] = result.stdout.strip()
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            suffix = f": {detail}" if detail else ""
            self.state["errors"].append(
                f"scan: saturation_scan.py failed with exit code "
                f"{result.returncode}{suffix}"
            )
        self.state["steps_completed"].append("scan")

    # Step 5: Propose

    def _load_proposal_seen(self, filename: str) -> dict:
        seen_path = self.archive_dir / filename
        if not seen_path.exists():
            return {}
        try:
            return json.loads(seen_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_proposal_seen(self, filename: str, seen: dict) -> None:
        """Write a proposal seen-store atomically (temp file + os.replace).

        `Path.write_text` truncates-then-writes in place; a second writer
        landing mid-write (e.g. after the lock above was stolen from a dead
        holder) could observe or produce a corrupt/partial JSON file.
        `os.replace` is an atomic rename on both POSIX and Windows.
        """
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        seen_path = self.archive_dir / filename
        tmp_path = seen_path.with_suffix(f"{seen_path.suffix}.tmp{os.getpid()}")
        tmp_path.write_text(json.dumps(seen, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp_path, seen_path)

    # Backward-compatible aliases retained for callers that inspect the
    # saturation seen-store directly.
    def _load_saturation_seen(self) -> dict:
        return self._load_proposal_seen(_SATURATION_SEEN_FILENAME)

    def _save_saturation_seen(self, seen: dict) -> None:
        self._save_proposal_seen(_SATURATION_SEEN_FILENAME, seen)

    def _proposal_is_open(self, proposal_id: str) -> bool:
        """A tracked proposal is still open if its file exists and has at
        least one voter left in PENDING; once every voter has resolved (or
        the file is gone -- archived/otherwise resolved elsewhere) it no
        longer blocks a fresh proposal for a recurring dedup key."""
        proposals_dir = self.sys_dir / "ai" / "proposals"
        matches = list(proposals_dir.glob(f"{proposal_id}*.md"))
        if not matches:
            return False
        try:
            content = matches[0].read_text(encoding="utf-8")
        except OSError:
            return False
        return bool(re.search(r"^- \S+: PENDING$", content, re.MULTILINE))

    def _run_idempotent_proposal(
        self,
        *,
        step: str,
        dedup_key: str,
        seen_filename: str,
        cmd: list[object],
    ) -> bool:
        """Run proposal-add unless this key already has an open proposal.

        Shared by propose() (saturation-scan findings, keyed by content
        fingerprint) and lesson_graduation() (keyed by the lesson's own
        stable id) -- T90: generalized from propose()'s original T89 dedup
        machinery rather than duplicating it per caller.
        """
        now = datetime.now(timezone.utc)
        lock_path = self.archive_dir / f"{seen_filename}.lock"

        with _file_lock(lock_path, timeout=_LOCK_ACQUIRE_TIMEOUT_SECONDS) as acquired:
            if not acquired:
                # Fail closed: do not race another check-then-write sequence.
                # False leaves the caller's step incomplete so a later session
                # retries instead of treating the deferred work as finished.
                self.state["errors"].append(
                    f"{step}: could not acquire {seen_filename} lock within "
                    "timeout; deferring to a later session"
                )
                return False

            seen = self._load_proposal_seen(seen_filename)
            entry = seen.get(dedup_key)
            is_duplicate = False
            if entry:
                proposal_id = entry.get("proposal_id")
                if proposal_id:
                    is_duplicate = self._proposal_is_open(proposal_id)
                else:
                    # Degraded entry from before proposal_id capture (or a
                    # run whose hub.py stdout didn't match the expected
                    # format) -- fall back to a time-window heuristic rather
                    # than treat it as permanently open or never-open.
                    try:
                        last_seen = datetime.fromisoformat(
                            entry["last_seen"].replace("Z", "+00:00")
                        )
                    except (KeyError, ValueError):
                        last_seen = None
                    if last_seen and now - last_seen < timedelta(
                        days=_PROPOSAL_DEDUP_WINDOW_DAYS
                    ):
                        is_duplicate = True

            if is_duplicate:
                entry["last_seen"] = now.isoformat().replace("+00:00", "Z")
                entry["repeat_count"] = int(entry.get("repeat_count", 1)) + 1
                self._save_proposal_seen(seen_filename, seen)
                return True

            result = _run_checked_step(
                self.state,
                step,
                cmd,
                timeout=_PROPOSAL_ADD_SUBPROCESS_TIMEOUT_SECONDS,
            )
            if result.returncode != 0:
                return False

            stdout_text = result.stdout if isinstance(result.stdout, str) else ""
            id_match = re.search(r"PROPOSAL-ADD (\S+)", stdout_text)
            seen[dedup_key] = {
                "first_seen": (
                    entry["first_seen"] if entry
                    else now.isoformat().replace("+00:00", "Z")
                ),
                "last_seen": now.isoformat().replace("+00:00", "Z"),
                "repeat_count": int(entry.get("repeat_count", 0)) + 1 if entry else 1,
                "proposal_id": id_match.group(1) if id_match else None,
            }
            self._save_proposal_seen(seen_filename, seen)
            return True

    def propose(self) -> None:
        scan_findings = self.state.get("scan_findings")
        is_skip_line = bool(scan_findings) and scan_findings.startswith("[SKIP]")
        is_clean_scan = bool(re.search(r"=== saturation-scan: 0 finding", scan_findings or ""))
        if not scan_findings or is_skip_line or is_clean_scan:
            # A [SKIP] line (commit_count untracked or not a multiple of 10)
            # and a clean "0 finding(s)" report are both saturation_scan.py's
            # own non-empty stdout, not an actual finding to propose about.
            self.state["steps_completed"].append("propose")
            return

        hub = self.sys_dir / "core" / "hub.py"
        succeeded = self._run_idempotent_proposal(
            step="propose",
            dedup_key=_findings_fingerprint(scan_findings),
            seen_filename=_SATURATION_SEEN_FILENAME,
            cmd=[
                sys.executable,
                str(hub),
                "proposal-add",
                "--subject",
                "Auto: Saturation detected",
                "--rationale",
                scan_findings[:200],
            ],
        )
        if succeeded:
            self.state["steps_completed"].append("propose")

    # Step 6: Lesson Graduation (Phase 6 / EDGE-05)

    def lesson_graduation(self) -> None:
        """Promote recurring lessons to docs-v2/10-invariants.md via proposal-add.

        Algorithm (impl-plan.md section 9):
          1. Load governance_params.json for threshold + window
          2. Scan active-lessons.jsonl for lessons with source_refs count >= threshold
             OR lessons cited across >= threshold unique debate sessions within window_days
          3. For each candidate without an open proposal: hub.py proposal-add
          4. Log result to state
        """
        gov_path = self.sys_dir / "ai" / "governance_params.json"
        gov: dict = {}
        if gov_path.exists():
            try:
                gov = json.loads(gov_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        threshold = int(gov.get("lesson_graduation_threshold", 3))
        window_days = int(gov.get("lesson_graduation_window_days", 7))
        target_doc = gov.get("lesson_graduation_target_doc", "_sys/docs-v2/10-invariants.md")
        auto_propose = bool(gov.get("lesson_graduation_auto_propose", True))

        lessons_path = self.sys_dir / "ai" / "knowledge" / "general" / "active-lessons.jsonl"
        if not lessons_path.exists():
            self.state["steps_completed"].append("lesson_graduation")
            return

        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        candidates: list[dict] = []

        for line in lessons_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                lesson = json.loads(line)
            except Exception:
                continue
            if lesson.get("status") != "active":
                continue

            refs = lesson.get("source_refs", [])
            recent_refs = [
                r for r in refs
                if _parse_ts(r.get("ts", "")) >= cutoff
            ]
            unique_debates = {
                r.get("id")
                for r in recent_refs
                if r.get("type") in ("debate", "parity-audit")
            }

            if len(refs) >= threshold or len(unique_debates) >= threshold:
                candidates.append(lesson)

        self.state["graduation_candidates"] = [l.get("id") for l in candidates]

        if not candidates or not auto_propose:
            self.state["steps_completed"].append("lesson_graduation")
            return

        hub = self.sys_dir / "core" / "hub.py"
        all_succeeded = True
        for lesson in candidates:
            lid = lesson.get("id", "?")
            title = lesson.get("title", "untitled")
            rule = lesson.get("compact_rule", "")
            rationale = (
                f"Lesson {lid} ({title}) has been observed >= {threshold} times. "
                f"Candidate for graduation to {target_doc}.\n"
                f"Rule: {rule[:300]}"
            )
            succeeded = self._run_idempotent_proposal(
                step="lesson_graduation",
                dedup_key=str(lid),
                seen_filename=_LESSON_GRADUATION_SEEN_FILENAME,
                cmd=[
                    sys.executable,
                    str(hub),
                    "proposal-add",
                    "--subject",
                    f"Lesson graduation: {lid} -> {target_doc}",
                    "--rationale",
                    rationale[:500],
                ],
            )
            if not succeeded:
                all_succeeded = False

        if all_succeeded:
            self.state["steps_completed"].append("lesson_graduation")

    # Step 7: Sync

    def sync(self) -> None:
        sync_script = _CHECKS_DIR / "sync_docs.py"
        result = _run_checked_step(
            self.state,
            "sync",
            [sys.executable, str(sync_script), "--dry-run"],
        )
        if result.returncode == 0:
            self.state["steps_completed"].append("sync")

    # Step 7: Record

    def record(self, trigger: str = "manual") -> None:
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.archive_dir / "self-care-log.jsonl"
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger": trigger,
            "steps": self.state.get("steps_completed", []),
            "errors": self.state.get("errors", []),
        }
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        self.state["steps_completed"].append("record")

    # Run all steps non-blocking

    def run(self, trigger: str = "manual") -> None:
        steps = [
            ("observe", self.observe),
            ("validate", self.validate),
            ("cleanup", self.cleanup),
            ("docs_mece", self.docs_mece),
            ("scan", self.scan),
            ("propose", self.propose),
            ("lesson_graduation", self.lesson_graduation),
            ("sync", self.sync),
        ]
        for name, fn in steps:
            try:
                fn()
            except Exception as exc:
                self.state["errors"].append(f"{name}: {exc}")
        self.record(trigger=trigger)


def main() -> None:
    parser = argparse.ArgumentParser(description="Engram self-care pipeline")
    parser.add_argument(
        "step",
        nargs="?",
        default="all",
        help="Specific step to run (e.g. observe), or 'all'",
    )
    parser.add_argument(
        "--trigger",
        choices=["session_end", "error_threshold", "commit_interval", "manual"],
        default="manual",
    )
    parser.add_argument(
        "--lesson-grad-only",
        action="store_true",
        help="Only run lesson_graduation step",
    )
    args = parser.parse_args()

    sc = SelfCare()
    if args.lesson_grad_only:
        try:
            sc.lesson_graduation()
        except Exception as exc:
            sc.state["errors"].append(f"lesson_graduation: {exc}")
        sc.record(trigger=args.trigger)
    elif args.step and args.step != "all":
        try:
            method = getattr(sc, args.step)
            if args.step in ("run", "record"):
                method(trigger=args.trigger)
            else:
                method()
        except Exception as exc:
            sc.state["errors"].append(f"{args.step}: {exc}")
            
        if args.step not in ("run", "record"):
            sc.record(trigger=args.trigger)
    else:
        sc.run(trigger=args.trigger)
    sys.exit(0)


if __name__ == "__main__":
    main()
