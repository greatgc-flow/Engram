"""Run with the PeerHub interpreter against a source checkout and a new synthetic DB."""

import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile


def tree(root):
    result = {}
    for path in root.rglob("*"):
        if path.is_file():
            with path.open("rb") as stream:
                result[path.relative_to(root)] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


def probe(source, root):
    sys.path.insert(0, str(source.resolve(strict=True)))
    from peerhub._version import __version__
    from peerhub.cli import main

    if __version__ != "0.28.2":
        raise ValueError("Use PeerHub 0.28.2 for this contract receipt")
    blocked = []
    def guard(event, args):
        if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system", "os.posix_spawn"}:
            blocked.append(event)
            raise RuntimeError("network/process operation attempted in offline fixture")
    sys.addaudithook(guard)

    db = root / "store" / "fixture.db"
    def cli(*args, code=0):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
            actual = main(["--db", str(db), *args, "--json"])
        if actual != code:
            raise RuntimeError(f"{args[0]} returned {actual}, expected {code}")
        return json.loads(stdout.getvalue())

    def check(ok, label):
        if not ok:
            raise ValueError(label)

    missing = cli("stream", "list", code=5)
    check(missing["status"] == "UNAVAILABLE" and not db.parent.exists(), "missing store side effect")
    cli("peer", "register", "--peer", "user")
    cli("stream", "create", "--stream", "wp0")
    record = cli("record", "append", "--stream", "wp0", "--author-peer", "user", "--kind", "message",
                 "--body", "synthetic", "--idempotency-key", "wp0-msg")
    packet = root / "fixture.md"
    packet.write_text("Synthetic read-only question.", encoding="utf-8")
    before = tree(db.parent)
    preview = cli("ask", "cc", "--prompt-file", str(packet), "--stream", "wp0", "--request-id", "wp0-01",
                  "--profile", "cc.standard", "--workspace", str(root), "--timeout-seconds", "180",
                  "--max-output-bytes", "65536", "--dry-run")
    check(before == tree(db.parent), "ask preview changed source files")
    streams = cli("stream", "list", "--limit", "1")
    records = cli("record", "read", "--stream", "wp0", "--after", "0", "--limit", "1")
    sessions = cli("session", "list")
    check([s["stream_id"] for s in streams["items"]] == ["wp0"], "stream selection")
    check(records == [record] and sessions["items"] == [], "record or session mismatch")
    expected = {"store_exists": True, "stream_exists": True, "peer_id": "cc", "profile": "cc.standard",
                "stream_id": "wp0", "request_id": "wp0-01", "workspace": str(root),
                "session_mode": "fresh", "writable": False, "replay": False}
    check(all(preview.get(k) == v for k, v in expected.items()), "dry-run binding")
    after = tree(db.parent)
    changed = {p for p in before.keys() | after.keys() if before.get(p) != after.get(p)}
    allowed = {Path(db.name + suffix) for suffix in ("-shm", "-wal")}
    check(changed <= allowed and not (changed & before.keys()), "history read changed existing data")
    # A logical read can materialize SQLite WAL support files on an idle store.
    # Keep physical no-write as a distinct oracle instead of silently accepting it.
    history_footprint = "FAIL" if changed else "PASS"
    check(not blocked, "process/network audit events observed")
    return {"version": __version__, "logical_read": "PASS", "preview_tree_equal": True,
            "history_tree_equal": history_footprint, "history_created": sorted(map(str, changed)),
            "record_shape": "array", "session_shape": "object", "preview_keys": sorted(preview),
            "observed_blocked_operations": len(blocked)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    source = parser.parse_args().source.resolve(strict=True)
    sys.dont_write_bytecode = True
    original_dir = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="engram-peerhub-") as tmp:
        os.chdir(tmp)
        try:
            receipt = probe(source, Path(tmp).resolve())
            print(json.dumps(receipt, sort_keys=True))
            if receipt["history_tree_equal"] == "FAIL":
                raise SystemExit(3)
        finally:
            os.chdir(original_dir)
