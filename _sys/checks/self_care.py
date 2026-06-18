"""self_care.py — Event-based self-care pipeline (7 steps).

Usage:
    python self_care.py [--trigger session_end|error_threshold|commit_interval|manual]

Steps: Observe → Validate → Cleanup → Scan → Propose → Sync → Record
Step failures are non-blocking: errors logged, remaining steps continue.
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


_CHECKS_DIR = Path(__file__).parent
_SYS_DIR    = _CHECKS_DIR.parent


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

    # ── Step 6: Sync ──────────────────────────────────────────────────────────

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
            ("observe",    self.observe),
            ("validate",   self.validate),
            ("cleanup",    self.cleanup),
            ("docs_mece",  self.docs_mece),
            ("scan",       self.scan),
            ("propose",    self.propose),
            ("sync",       self.sync),
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
        "--trigger",
        choices=["session_end", "error_threshold", "commit_interval", "manual"],
        default="manual",
    )
    args = parser.parse_args()

    sc = SelfCare()
    sc.run(trigger=args.trigger)
    sys.exit(0)


if __name__ == "__main__":
    main()
