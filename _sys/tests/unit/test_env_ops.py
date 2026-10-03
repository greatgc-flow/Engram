import pytest
from pathlib import Path
import hashlib
import concurrent.futures
import time
import builtins
from core.env_ops import (
    execute, resume, rollback, active_journal, journal_blocks, current_phase, read_journal,
    journal_path, Step, OpContext, SimulatedCrash, JournalError, new_op_id, JOURNAL_FILENAME
)

def test_happy_path(tmp_path):
    sys_dir = tmp_path / "sys"
    
    def do_s1(ctx): ctx.paths["f1"].write_text("s1")
    def undo_s1(ctx): ctx.paths["f1"].unlink()
    
    def do_s2(ctx): ctx.data["val"] = 42
    
    steps = [
        Step("s1", do_s1, undo_s1),
        Step("s2", do_s2, None),
        Step("post1", lambda c: None, group="B")
    ]
    paths = {"f1": tmp_path / "f1.txt"}
    
    res = execute(sys_dir, "test-op", steps, paths=paths)
    assert res["status"] == "success"
    assert res["phase"] == "COMMITTED"
    
    assert paths["f1"].read_text() == "s1"
    assert active_journal(sys_dir) is None
    assert journal_blocks(sys_dir) is None
    
    records = read_journal(sys_dir)
    events = [r["event"] for r in records]
    assert events == ["PHASE", "PATHS", "POSTS", "PHASE", "STEP", "STEP", "STEP", "STEP", "PHASE", "POST", "POST"]
    assert current_phase(sys_dir) == "COMMITTED"
    
    execute(sys_dir, "test-op2", [])
    done_files = list((sys_dir / "data" / "state").glob("*.done"))
    assert len(done_files) == 1

def test_torn_tail(tmp_path):
    sys_dir = tmp_path / "sys"
    execute(sys_dir, "test", [Step("s1", lambda c: None)])
    
    jpath = journal_path(sys_dir)
    with open(jpath, "a", encoding="utf-8") as f:
        f.write('{"seq": 99, "event": "BAD", "crc": "wrong"}\n')
        f.write('{"seq": 100\n')
        
    records = read_journal(sys_dir)
    assert all(r["event"] != "BAD" for r in records)

def test_lock_busy(tmp_path):
    sys_dir = tmp_path / "sys"
    from core import env_lock
    handle = env_lock.acquire(sys_dir, "other-op")
    try:
        res = execute(sys_dir, "test", [Step("s1", lambda c: None)])
        assert res["status"] == "failed"
        assert "lock busy" in res["detail"].lower() or "held" in res["detail"].lower()
    finally:
        handle.release()
    
def test_step_failure_rollback(tmp_path):
    sys_dir = tmp_path / "sys"
    def do_s1(ctx): ctx.paths["f1"].write_text("s1")
    def undo_s1(ctx): ctx.paths["f1"].unlink()
    
    def do_s2(ctx): raise ValueError("boom")
    
    steps = [Step("s1", do_s1, undo_s1), Step("s2", do_s2, None)]
    paths = {"f1": tmp_path / "f1.txt"}
    
    res = execute(sys_dir, "test-op", steps, paths=paths)
    assert res["status"] == "failed"
    assert res["phase"] == "ROLLED_BACK"
    assert not paths["f1"].exists()
    assert active_journal(sys_dir) is None

def test_undo_failure(tmp_path):
    sys_dir = tmp_path / "sys"
    def do_s1(ctx): ctx.paths["f1"].write_text("s1")
    def undo_s1(ctx): raise ValueError("undo fail")
    
    def do_s2(ctx): raise ValueError("boom")
    
    steps = [Step("s1", do_s1, undo_s1), Step("s2", do_s2, None)]
    paths = {"f1": tmp_path / "f1.txt"}
    
    res = execute(sys_dir, "test-op", steps, paths=paths)
    assert res["status"] == "failed"
    assert res["phase"] == "ROLLBACK_FAILED"
    
    with pytest.raises(JournalError):
        execute(sys_dir, "test2", [])

def test_group_b_failure(tmp_path):
    sys_dir = tmp_path / "sys"
    def do_s1(ctx): pass
    def do_post(ctx): raise ValueError("post fail")
    
    steps = [Step("s1", do_s1), Step("p1", do_post, group="B")]
    res = execute(sys_dir, "test-op", steps)
    assert res["status"] == "success"
    assert res["phase"] == "COMMITTED"
    assert res["failed_step"] == "p1"
    assert res["post_failed"] == ["p1"]

def get_dir_state(d: Path) -> dict:
    st = {}
    if not d.exists(): return st
    for p in d.rglob("*"):
        if p.is_file():
            st[str(p.relative_to(d))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return st

@pytest.mark.parametrize("crash_at", ["s1", "s2", "s3", "s4", "s5", "s6"])
def test_t_f1_fault_injection_resume_and_rollback(tmp_path, crash_at):
    sys_dir = tmp_path / "sys"
    data_dir = tmp_path / "data_dir"
    data_dir.mkdir()
    
    initial_state = get_dir_state(data_dir)
    
    def mk_do(i):
        def do(ctx): 
            ctx.paths[f"f{i}"].write_text(f"v{i}")
        return do
        
    def mk_undo(i):
        def undo(ctx): 
            if ctx.paths[f"f{i}"].exists():
                ctx.paths[f"f{i}"].unlink()
        return undo
        
    steps = [Step(f"s{i}", mk_do(i), mk_undo(i)) for i in range(1, 7)]
    paths = {f"f{i}": data_dir / f"f{i}.txt" for i in range(1, 7)}
    
    with pytest.raises(SimulatedCrash):
        execute(sys_dir, "test", steps, paths=paths, crash_after=crash_at)
        
    assert active_journal(sys_dir) is not None
    
    # a) resume converges
    res = resume(sys_dir, lambda d: steps)
    assert res["phase"] == "COMMITTED"
    for i in range(1, 7):
        assert paths[f"f{i}"].read_text() == f"v{i}"
        
    # b) fresh crash + rollback restores
    sys_dir2 = tmp_path / "sys2"
    data_dir2 = tmp_path / "data_dir2"
    data_dir2.mkdir()
    paths2 = {f"f{i}": data_dir2 / f"f{i}_2.txt" for i in range(1, 7)}
    initial_state2 = get_dir_state(data_dir2)
    
    with pytest.raises(SimulatedCrash):
        execute(sys_dir2, "test", steps, paths=paths2, crash_after=crash_at)
        
    res2 = rollback(sys_dir2, lambda d: steps)
    assert res2["phase"] == "ROLLED_BACK"
    
    final_state2 = get_dir_state(data_dir2)
    assert final_state2 == initial_state2

def test_t_f3_crash_after_committed_rolls_forward(tmp_path):
    sys_dir = tmp_path / "sys"
    def do_p1_crash(ctx): raise SimulatedCrash("boom")
    steps_crash = [Step("s1", lambda c: None), Step("p1", do_p1_crash, group="B")]
    paths = {"p1": tmp_path / "p1.txt"}
    
    with pytest.raises(SimulatedCrash):
        execute(sys_dir, "test", steps_crash, paths=paths)
        
    active = active_journal(sys_dir)
    assert active is not None
    assert active["phase"] == "COMMITTED"
    assert "p1" in active["pending_post"]
    
    with pytest.raises(JournalError):
        execute(sys_dir, "test2", steps_crash)
        
    def do_p1(ctx): ctx.paths["p1"].write_text("p1")
    steps = [Step("s1", lambda c: None), Step("p1", do_p1, group="B")]
    
    res = resume(sys_dir, lambda d: steps)
    assert res["phase"] == "COMMITTED"
    assert paths["p1"].read_text() == "p1"
    
    with pytest.raises(JournalError):
        rollback(sys_dir, lambda d: steps)

def test_crash_between_group_b_steps(tmp_path):
    sys_dir = tmp_path / "sys"
    def do_p1(ctx): ctx.paths["p1"].write_text("p1")
    def do_p2_crash(ctx): raise SimulatedCrash("boom")
    
    steps_crash = [
        Step("s1", lambda c: None), 
        Step("p1", do_p1, group="B"),
        Step("p2", do_p2_crash, group="B"),
        Step("p3", lambda c: None, group="B")
    ]
    paths = {"p1": tmp_path / "p1.txt"}
    
    with pytest.raises(SimulatedCrash):
        execute(sys_dir, "test", steps_crash, paths=paths, crash_after="p1")
        
    active = active_journal(sys_dir)
    assert active is not None
    assert active["phase"] == "COMMITTED"
    assert "p1" not in active["pending_post"]
    assert "p2" in active["pending_post"]
    assert "p3" in active["pending_post"]

def test_done_probe_skips(tmp_path):
    sys_dir = tmp_path / "sys"
    executed = []
    def do_s1(ctx): executed.append("s1")
    def done_s1(ctx): return True
    
    steps = [Step("s1", do_s1, done=done_s1)]
    execute(sys_dir, "test", steps)
    assert executed == []

def test_data_persisted(tmp_path):
    sys_dir = tmp_path / "sys"
    def do_s1(ctx): ctx.data["x"] = 1
    def do_s2(ctx): raise SimulatedCrash("boom")
        
    steps = [Step("s1", do_s1), Step("s2", do_s2)]
    with pytest.raises(SimulatedCrash):
        execute(sys_dir, "test", steps)
        
    def do_s2_fix(ctx):
        assert ctx.data["x"] == 1
    steps_fix = [Step("s1", do_s1), Step("s2", do_s2_fix)]
    
    res = resume(sys_dir, lambda d: steps_fix)
    assert res["phase"] == "COMMITTED"

def test_done_rotation(tmp_path):
    sys_dir = tmp_path / "sys"
    for i in range(10):
        execute(sys_dir, f"test{i}", [Step(f"s{i}", lambda c: None)])
    
    done_files = list((sys_dir / "data" / "state").glob("*.done"))
    assert len(done_files) <= 5
    
def test_new_op_id():
    a = new_op_id("kind1")
    b = new_op_id("kind1")
    assert a != b
    assert "kind1" in a

def test_execute_concurrency_race(tmp_path):
    """Eight starters at once: the winner HOLDS the lock until every loser has been refused, so the
    outcome is deterministic (a loser that merely started late would legitimately succeed afterwards)."""
    import threading
    sys_dir = tmp_path / "sys"
    losers_done = threading.Semaphore(0)
    release = threading.Event()

    def holding_step(ctx):
        for _ in range(7):
            assert losers_done.acquire(timeout=30), "losers were never refused"
        release.set()

    results = []
    lock = threading.Lock()

    def run_exec(i):
        res = execute(sys_dir, "race", [Step("s1", holding_step)])
        with lock:
            results.append(res)
        if res["status"] == "failed":
            losers_done.release()

    threads = [threading.Thread(target=run_exec, args=(i,)) for i in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=60)
    assert release.is_set()
    successes = [r for r in results if r["status"] == "success"]
    failures = [r for r in results if r["status"] == "failed"]
    assert len(successes) == 1 and len(failures) == 7
    for f in failures:
        assert "lock busy" in f["detail"].lower() or "held" in f["detail"].lower()
    assert active_journal(sys_dir) is None


def test_resume_planned_phase(tmp_path):
    sys_dir = tmp_path / "sys"
    
    jpath = journal_path(sys_dir)
    jpath.parent.mkdir(parents=True, exist_ok=True)
    
    def append_raw(event, **kwargs):
        record = {"seq": 1, "ts": "2023-01-01T00:00:00Z", "event": event, **kwargs}
        import json, zlib
        text = json.dumps(record, sort_keys=True, separators=(',', ':'))
        record["crc"] = f"{zlib.crc32(text.encode('utf-8')):08x}"
        with open(jpath, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
            
    append_raw("PHASE", name="PLANNED", op_id="test-op", kind="test")
    append_raw("PATHS", paths={"f1": str(tmp_path / "f1.txt")})
    
    assert current_phase(sys_dir) == "PLANNED"
    
    def do_s1(ctx):
        ctx.paths["f1"].write_text("ok")
        
    steps = [Step("s1", do_s1)]
    
    res = resume(sys_dir, lambda d: steps)
    assert res["status"] == "success"
    assert res["phase"] == "COMMITTED"
    assert (tmp_path / "f1.txt").read_text() == "ok"
    
def test_post_step_failure_and_retry(tmp_path):
    sys_dir = tmp_path / "sys"
    
    p1_calls = [0]
    def do_p1(ctx):
        p1_calls[0] += 1
        if p1_calls[0] == 1:
            raise ValueError("post fail")
            
    steps = [Step("s1", lambda c: None), Step("p1", do_p1, group="B")]
    
    res = execute(sys_dir, "test", steps)
    assert res["status"] == "success"
    assert res["post_failed"] == ["p1"]
    
    assert active_journal(sys_dir) is None
    
    res_resume = resume(sys_dir, lambda d: steps)
    assert res_resume["status"] == "success"
    assert "post_failed" not in res_resume or not res_resume["post_failed"]
    
    res2 = execute(sys_dir, "test2", [Step("s2", lambda c: None)])
    assert res2["status"] == "success"

def test_read_journal_oserror(tmp_path, monkeypatch):
    sys_dir = tmp_path / "sys"
    execute(sys_dir, "test", [Step("s1", lambda c: None)])
    
    original_open = builtins.open
    def mock_open(*args, **kwargs):
        if str(args[0]).endswith(JOURNAL_FILENAME):
            raise PermissionError("Access denied")
        return original_open(*args, **kwargs)
        
    monkeypatch.setattr("builtins.open", mock_open)
    
    with pytest.raises(JournalError, match="Access denied"):
        read_journal(sys_dir)
