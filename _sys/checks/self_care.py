"""self_care.py — Event-based self-care pipeline (8 steps + lesson graduation).

Usage:
    python self_care.py [--trigger session_end|error_threshold|commit_interval|manual]

Steps: Observe → Validate → Cleanup → DocsMECE → Scan → Propose → LessonGrad → Sync → Record
Step failures are non-blocking: errors logged, remaining steps continue.
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


_CHECKS_DIR = Path(__file__).parent
_SYS_DIR    = _CHECKS_DIR.parent


def _parse_ts(ts: str) -> datetime:
    """Parse lesson source_ref timestamp (YYYYMMDDTHHMMSS or ISO8601) → UTC datetime."""
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


class SelfCare:
    def __init__(self, sys_dir: Path | None = None, archive_dir: Path | None = None):
        self.sys_dir     = Path(sys_dir) if sys_dir else _SYS_DIR
        self.archive_dir = Path(archive_dir) if archive_dir else self.sys_dir.parent / "_archive"
        self.state: dict = {
            "health":         {},
            "directives":     [],
            "scan_findings":  "",
            "steps_completed": [],
            "errors":         [],
        }

    # ── Step 1: Observe ───────────────────────────────────────────────────────

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

    # ── Step 2: Validate ──────────────────────────────────────────────────────

    def validate(self) -> None:
        virtualizer = self.sys_dir / "core" / "virtualizer.py"
        if not virtualizer.exists():
            virtualizer = _CHECKS_DIR.parent / "core" / "virtualizer.py"
        subprocess.run(
            [sys.executable, str(virtualizer), "--status"],
            capture_output=True, text=True
        )
        self.state["steps_completed"].append("validate")

    # ── Step 3: Cleanup ───────────────────────────────────────────────────────

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

    # ── Step 3: Docs MECE ─────────────────────────────────────────────────────

    def docs_mece(self) -> None:
        mece_script = _CHECKS_DIR / "check_docs_mece.py"
        if not mece_script.exists():
            self.state["steps_completed"].append("docs_mece")
            return
        result = subprocess.run(
            [sys.executable, str(mece_script), "--checks", "CHK-01,CHK-02", "--json"],
            capture_output=True, text=True
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

    # ── Step 4: Scan ──────────────────────────────────────────────────────────

    def scan(self) -> None:
        scan_script = _CHECKS_DIR / "saturation_scan.py"
        result = subprocess.run(
            [sys.executable, str(scan_script), "--quiet"],
            capture_output=True, text=True
        )
        self.state["scan_findings"] = result.stdout.strip()
        self.state["steps_completed"].append("scan")

    # ── Step 5: Propose ───────────────────────────────────────────────────────

    def propose(self) -> None:
        if self.state.get("scan_findings"):
            hub = self.sys_dir / "core" / "hub.py"
            subprocess.run(
                [sys.executable, str(hub), "proposal-add",
                 "--title", "Auto: Saturation detected",
                 "--rationale", self.state["scan_findings"][:200]],
                capture_output=True, text=True
            )
        self.state["steps_completed"].append("propose")

    # ── Step 6: Lesson Graduation (Phase 6 / EDGE-05) ────────────────────────

    def lesson_graduation(self) -> None:
        """Promote recurring lessons to docs-v2/10-invariants.md via proposal-add.

        Algorithm (impl-plan.md §9):
          1. Load governance_params.json for threshold + window
          2. Scan active-lessons.jsonl for lessons with source_refs count >= threshold
             OR lessons cited across >= threshold unique debate sessions within window_days
          3. For each candidate: hub.py proposal-add with content block
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
            unique_debates = {r.get("id") for r in recent_refs if r.get("type") in ("debate", "parity-audit")}

            if len(refs) >= threshold or len(unique_debates) >= threshold:
                candidates.append(lesson)

        self.state["graduation_candidates"] = [l.get("id") for l in candidates]

        if not candidates or not auto_propose:
            self.state["steps_completed"].append("lesson_graduation")
            return

        hub = self.sys_dir / "core" / "hub.py"
        for lesson in candidates:
            lid = lesson.get("id", "?")
            title = lesson.get("title", "untitled")
            rule = lesson.get("compact_rule", "")
            rationale = (
                f"Lesson {lid} ({title}) has been observed >= {threshold} times. "
                f"Candidate for graduation to {target_doc}.\n"
                f"Rule: {rule[:300]}"
            )
            subprocess.run(
                [sys.executable, str(hub), "proposal-add",
                 "--title", f"Lesson graduation: {lid} → {target_doc}",
                 "--rationale", rationale[:500]],
                capture_output=True, text=True,
            )

        self.state["steps_completed"].append("lesson_graduation")

    # ── Step 7: Sync ──────────────────────────────────────────────────────────

    def sync(self) -> None:
        sync_script = _CHECKS_DIR / "sync_docs.py"
        subprocess.run(
            [sys.executable, str(sync_script), "--dry-run"],
            capture_output=True, text=True
        )
        self.state["steps_completed"].append("sync")

    # ── Step 7: Record ────────────────────────────────────────────────────────

    def record(self, trigger: str = "manual") -> None:
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.archive_dir / "self-care-log.jsonl"
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger":   trigger,
            "steps":     self.state.get("steps_completed", []),
            "errors":    self.state.get("errors", []),
        }
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        self.state["steps_completed"].append("record")

    # ── Run all steps (non-blocking) ──────────────────────────────────────────

    def run(self, trigger: str = "manual") -> None:
        steps = [
            ("observe",            self.observe),
            ("validate",           self.validate),
            ("cleanup",            self.cleanup),
            ("docs_mece",          self.docs_mece),
            ("scan",               self.scan),
            ("propose",            self.propose),
            ("lesson_graduation",  self.lesson_graduation),
            ("sync",               self.sync),
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
            getattr(sc, args.step)()
        except Exception as exc:
            sc.state["errors"].append(f"{args.step}: {exc}")
        sc.record(trigger=args.trigger)
    else:
        sc.run(trigger=args.trigger)
    sys.exit(0)


if __name__ == "__main__":
    main()
