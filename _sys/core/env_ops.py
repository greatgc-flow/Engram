import json
import zlib
import datetime
import uuid
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Optional

JOURNAL_FILENAME = "env-op.journal.jsonl"

class SimulatedCrash(BaseException):
    pass

@dataclass
class OpContext:
    sys_dir: Path
    op_id: str
    kind: str
    paths: dict[str, Path]
    data: dict

@dataclass
class Step:
    name: str
    do: Callable[[OpContext], None]
    undo: Optional[Callable[[OpContext], None]] = None
    done: Optional[Callable[[OpContext], bool]] = None
    group: str = "A"

class JournalError(RuntimeError):
    pass

def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def new_op_id(kind: str, now: Optional[str] = None) -> str:
    ts = now or utc_now()
    return f"{ts.replace(':', '').replace('-', '')}-{kind}-{uuid.uuid4().hex[:8]}"

def journal_path(sys_dir: Path | str) -> Path:
    return Path(sys_dir) / "data" / "state" / JOURNAL_FILENAME

def _compute_crc(record: dict) -> str:
    rec = record.copy()
    rec.pop("crc", None)
    text = json.dumps(rec, sort_keys=True, separators=(',', ':'))
    return f"{zlib.crc32(text.encode('utf-8')):08x}"

def read_journal(sys_dir: Path | str) -> list[dict]:
    path = journal_path(sys_dir)
    if not path.exists():
        return []
    records = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    if "crc" not in record:
                        break
                    if _compute_crc(record) != record["crc"]:
                        break
                    records.append(record)
                except ValueError:
                    break
    except FileNotFoundError:
        pass
    except OSError as e:
        raise JournalError(f"Failed to read journal: {e}") from e
    return records

def current_phase(sys_dir: Path | str) -> Optional[str]:
    records = read_journal(sys_dir)
    phase = None
    for r in records:
        if r.get("event") == "PHASE":
            phase = r.get("name")
    return phase

def _parse_journal(records: list[dict]) -> Optional[dict]:
    if not records:
        return None
    phase = None
    op_id = None
    kind = None
    steps = {}
    paths = {}
    planned_posts = []
    
    for r in records:
        evt = r.get("event")
        if evt == "PHASE":
            phase = r.get("name")
            if "op_id" in r:
                op_id = r["op_id"]
            if "kind" in r:
                kind = r["kind"]
        elif evt == "PATHS":
            paths = r.get("paths", {})
            if "op_id" in r:
                op_id = r["op_id"]
            if "kind" in r:
                kind = r["kind"]
        elif evt == "POSTS":
            planned_posts = r.get("names", [])
        elif evt in ("STEP", "POST"):
            steps[r["name"]] = r["state"]
            
    if phase is None:
        return None
        
    pending_post = [p for p in planned_posts if steps.get(p) != "done"]
    
    return {"op_id": op_id, "kind": kind, "phase": phase, "steps": steps, "paths": paths, "pending_post": pending_post, "planned_posts": planned_posts, "data": {}}

def active_journal(sys_dir: Path | str) -> Optional[dict]:
    records = read_journal(sys_dir)
    j = _parse_journal(records)
    if not j or j["phase"] == "ROLLED_BACK":
        return None
        
    blocking_posts = [p for p in j["planned_posts"] if j["steps"].get(p) not in ("done", "failed")]
    
    if j["phase"] == "COMMITTED" and not blocking_posts:
        return None
        
    # Also parse data fields
    for r in records:
        if "data" in r and isinstance(r["data"], dict):
            j["data"].update(r["data"])

    return j

def journal_blocks(sys_dir: Path | str) -> Optional[dict]:
    return active_journal(sys_dir)

def _rotate_journal(jpath: Path, old_op_id: str):
    done_path = jpath.with_name(f"{JOURNAL_FILENAME}.{old_op_id}.done")
    try:
        if jpath.exists():
            os.replace(jpath, done_path)
    except OSError:
        pass
    
    done_files = []
    for f in jpath.parent.glob(f"{JOURNAL_FILENAME}.*.done"):
        try:
            done_files.append((f.stat().st_mtime, f))
        except OSError:
            pass
    done_files.sort(key=lambda x: x[0], reverse=True)
    for _, f in done_files[5:]:
        try:
            f.unlink()
        except OSError:
            pass

def _append_record_fn(jpath: Path, seq_box: list[int], now_fn: Callable[[], str]):
    def append_record(event: str, **kwargs):
        seq_box[0] += 1
        record = {"seq": seq_box[0], "ts": now_fn(), "event": event, **kwargs}
        record["crc"] = _compute_crc(record)
        line = json.dumps(record, separators=(',', ':')) + "\n"
        with open(jpath, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
    return append_record

def _do_rollback(ctx: OpContext, started_a: list[Step], append_record: Callable, steps_state: dict) -> dict:
    append_record("PHASE", name="ROLLING_BACK")
    failed_step = None
    for s, state in steps_state.items():
        if state == "failed":
            failed_step = s
    if not failed_step and started_a:
        failed_step = started_a[-1].name

    try:
        for step in reversed(started_a):
            state = steps_state.get(step.name)
            if state == "undone":
                continue
            if step.undo is not None:
                step.undo(ctx)
            append_record("STEP", name=step.name, state="undone")
            steps_state[step.name] = "undone"
        append_record("PHASE", name="ROLLED_BACK")
        return {"status": "failed", "operation": ctx.kind, "op_id": ctx.op_id, "phase": "ROLLED_BACK", "detail": "clean rollback", "failed_step": failed_step, "exit_code": 12}
    except Exception as e:
        if "step" in locals():
            fail_name = step.name
        else:
            fail_name = started_a[-1].name if started_a else "unknown"
        append_record("STEP", name=fail_name, state="failed(undo)", error=str(e))
        append_record("PHASE", name="ROLLBACK_FAILED")
        return {"status": "failed", "operation": ctx.kind, "op_id": ctx.op_id, "phase": "ROLLBACK_FAILED", "detail": f"rollback failed on {fail_name}", "failed_step": fail_name, "exit_code": 13}

def _peek_op_id(sys_dir: Path) -> str:
    records = read_journal(sys_dir)
    for r in records:
        if "op_id" in r:
            return r["op_id"]
    return "unknown"

def execute(
    sys_dir: Path | str, kind: str, steps: list[Step], *, paths: Optional[dict[str, Path]] = None,
    op_id: Optional[str] = None, now: Callable[[], str] = utc_now, crash_after: Optional[str] = None,
    lock_probe=None, initial_data: Optional[dict] = None
) -> dict:
    sys_dir = Path(sys_dir)
    jpath = journal_path(sys_dir)
    
    op_id = op_id or new_op_id(kind, now())
    paths = paths or {}
    jpath.parent.mkdir(parents=True, exist_ok=True)
    
    from core import env_lock
    try:
        lock_handle = env_lock.acquire(sys_dir, op_id, process_probe=lock_probe or env_lock.default_process_probe)
    except env_lock.EnvLockBusy as exc:
        return {"status": "failed", "operation": kind, "op_id": op_id, "phase": None, "detail": str(exc), "failed_step": None, "exit_code": 11}

    try:
        active = active_journal(sys_dir)
        if active is not None:
            raise JournalError(f"active journal exists for {active['op_id']}")
            
        if jpath.exists():
            records = read_journal(sys_dir)
            old_op_id = "unknown"
            for r in records:
                if "op_id" in r:
                    old_op_id = r["op_id"]
                    break
            _rotate_journal(jpath, old_op_id)
            
        ctx = OpContext(sys_dir, op_id, kind, paths, initial_data or {})
        seq = [0]
        append_record = _append_record_fn(jpath, seq, now)
        
        append_record("PHASE", name="PLANNED", op_id=op_id, kind=kind)
        append_record("PATHS", paths={k: str(v) for k, v in paths.items()})
        if initial_data:
            append_record("DATA", data=initial_data)
        
        group_a = [s for s in steps if s.group == "A"]
        group_b = [s for s in steps if s.group == "B"]
        append_record("POSTS", names=[s.name for s in group_b])
        append_record("PHASE", name="STEPS_RUNNING")

        started_a = []
        steps_state = {}
        
        for step in group_a:
            started_a.append(step)
            append_record("STEP", name=step.name, state="started")
            steps_state[step.name] = "started"
            if step.done and step.done(ctx):
                append_record("STEP", name=step.name, state="done", data=ctx.data)
                steps_state[step.name] = "done"
            else:
                try:
                    step.do(ctx)
                except SimulatedCrash:
                    raise
                except Exception as e:
                    append_record("STEP", name=step.name, state="failed", error=str(e))
                    steps_state[step.name] = "failed"
                    return _do_rollback(ctx, started_a, append_record, steps_state)
                append_record("STEP", name=step.name, state="done", data=ctx.data)
                steps_state[step.name] = "done"
                
            if crash_after == step.name:
                raise SimulatedCrash(f"Crash after {step.name}")

        append_record("PHASE", name="COMMITTED")
        
        post_failed = []
        for step in group_b:
            append_record("POST", name=step.name, state="started")
            if step.done and step.done(ctx):
                append_record("POST", name=step.name, state="done", data=ctx.data)
            else:
                try:
                    step.do(ctx)
                    append_record("POST", name=step.name, state="done", data=ctx.data)
                except SimulatedCrash:
                    raise
                except Exception as e:
                    append_record("POST", name=step.name, state="failed", error=str(e))
                    post_failed.append(step.name)
            if crash_after == step.name:
                raise SimulatedCrash(f"Crash after {step.name}")
                
        if post_failed:
            return {"status": "success", "operation": kind, "op_id": op_id, "phase": "COMMITTED", "detail": f"post steps failed: {post_failed}", "failed_step": post_failed[0], "post_failed": post_failed, "exit_code": 0}
        return {"status": "success", "operation": kind, "op_id": op_id, "phase": "COMMITTED", "detail": "success", "failed_step": None, "exit_code": 0}

    finally:
        lock_handle.release()


def resume(
    sys_dir: Path | str, steps_for: Callable[[dict], list[Step]], *, 
    now: Callable[[], str] = utc_now, lock_probe=None, crash_after: Optional[str] = None
) -> dict:
    sys_dir = Path(sys_dir)
    op_id = _peek_op_id(sys_dir)
    
    from core import env_lock
    try:
        lock_handle = env_lock.acquire(sys_dir, op_id, process_probe=lock_probe or env_lock.default_process_probe)
    except env_lock.EnvLockBusy as exc:
        return {"status": "failed", "operation": "unknown", "op_id": op_id, "phase": "unknown", "detail": str(exc), "failed_step": None, "exit_code": 11}

    try:
        records = read_journal(sys_dir)
        active = _parse_journal(records)
        if not active or active["phase"] == "ROLLED_BACK":
            raise JournalError("No active journal to resume")
        if active["phase"] == "COMMITTED" and not active["pending_post"]:
            raise JournalError("No active journal to resume")
            
        op_id = active["op_id"]
        kind = active["kind"]
        phase = active["phase"]
        paths_dict = active["paths"]
        
        ctx = OpContext(sys_dir, op_id, kind, {k: Path(v) for k, v in paths_dict.items()}, {})
        seq = [0]
        for r in records:
            seq[0] = max(seq[0], r.get("seq", 0))
            if "data" in r and isinstance(r["data"], dict):
                ctx.data.update(r["data"])

        jpath = journal_path(sys_dir)
        append_record = _append_record_fn(jpath, seq, now)

        steps = steps_for(active)
        group_a = [s for s in steps if s.group == "A"]
        group_b = [s for s in steps if s.group == "B"]
        steps_state = active["steps"].copy()
        
        if phase in ("PLANNED", "STEPS_RUNNING"):
            started_a = []
            for step in group_a:
                state = steps_state.get(step.name)
                started_a.append(step)
                if state == "done":
                    continue
                
                append_record("STEP", name=step.name, state="started")
                steps_state[step.name] = "started"
                if step.done and step.done(ctx):
                    append_record("STEP", name=step.name, state="done", data=ctx.data)
                    steps_state[step.name] = "done"
                else:
                    try:
                        step.do(ctx)
                    except SimulatedCrash:
                        raise
                    except Exception as e:
                        append_record("STEP", name=step.name, state="failed", error=str(e))
                        steps_state[step.name] = "failed"
                        return _do_rollback(ctx, started_a, append_record, steps_state)
                    append_record("STEP", name=step.name, state="done", data=ctx.data)
                    steps_state[step.name] = "done"
                
                if crash_after == step.name:
                    raise SimulatedCrash(f"Crash after {step.name}")

            append_record("PHASE", name="COMMITTED")
            phase = "COMMITTED"
            
        if phase == "COMMITTED":
            post_failed = []
            for step in group_b:
                state = steps_state.get(step.name)
                if state == "done":
                    continue
                append_record("POST", name=step.name, state="started")
                if step.done and step.done(ctx):
                    append_record("POST", name=step.name, state="done", data=ctx.data)
                else:
                    try:
                        step.do(ctx)
                        append_record("POST", name=step.name, state="done", data=ctx.data)
                    except SimulatedCrash:
                        raise
                    except Exception as e:
                        append_record("POST", name=step.name, state="failed", error=str(e))
                        post_failed.append(step.name)
                if crash_after == step.name:
                    raise SimulatedCrash(f"Crash after {step.name}")
            if post_failed:
                return {"status": "success", "operation": kind, "op_id": op_id, "phase": "COMMITTED", "detail": f"post steps failed: {post_failed}", "failed_step": post_failed[0], "post_failed": post_failed, "exit_code": 0}
            return {"status": "success", "operation": kind, "op_id": op_id, "phase": "COMMITTED", "detail": "success", "failed_step": None, "exit_code": 0}
            
        if phase in ("ROLLING_BACK", "ROLLBACK_FAILED"):
            started_a = [s for s in group_a if s.name in steps_state]
            return _do_rollback(ctx, started_a, append_record, steps_state)
            
        return {"status": "failed", "operation": kind, "op_id": op_id, "phase": phase, "detail": f"unhandled phase: {phase}", "failed_step": None, "exit_code": 1}
            
    finally:
        lock_handle.release()


def rollback(
    sys_dir: Path | str, steps_for: Callable[[dict], list[Step]], *, 
    now: Callable[[], str] = utc_now, lock_probe=None, crash_after: Optional[str] = None
) -> dict:
    sys_dir = Path(sys_dir)
    op_id = _peek_op_id(sys_dir)
            
    from core import env_lock
    try:
        lock_handle = env_lock.acquire(sys_dir, op_id, process_probe=lock_probe or env_lock.default_process_probe)
    except env_lock.EnvLockBusy as exc:
        return {"status": "failed", "operation": "unknown", "op_id": op_id, "phase": "unknown", "detail": str(exc), "failed_step": None, "exit_code": 11}

    try:
        records = read_journal(sys_dir)
        active = _parse_journal(records)
        if not active or active["phase"] == "ROLLED_BACK":
            raise JournalError("No active journal to rollback")
        if active["phase"] == "COMMITTED":
            raise JournalError("Cannot rollback a COMMITTED operation")
            
        op_id = active["op_id"]
        kind = active["kind"]
        paths_dict = active["paths"]
        
        ctx = OpContext(sys_dir, op_id, kind, {k: Path(v) for k, v in paths_dict.items()}, {})
        seq = [0]
        for r in records:
            seq[0] = max(seq[0], r.get("seq", 0))
            if "data" in r and isinstance(r["data"], dict):
                ctx.data.update(r["data"])

        jpath = journal_path(sys_dir)
        append_record = _append_record_fn(jpath, seq, now)
                
        steps = steps_for(active)
        group_a = [s for s in steps if s.group == "A"]
        steps_state = active["steps"].copy()
        started_a = [s for s in group_a if s.name in steps_state]
        return _do_rollback(ctx, started_a, append_record, steps_state)
    finally:
        lock_handle.release()
