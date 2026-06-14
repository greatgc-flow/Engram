# Lease Test Fix Plan
_Created: 2026-06-13 | Owner: cc | Status: ACTIVE_

## 1. Problem

Heartbeat leasing implementation (session 2026-06-13) replaced `subprocess.run`
with `subprocess.Popen` + communicate-loop in `action_ask()`. This broke 13 tests
that mock `subprocess.run` — the mock is never called, so the Popen execution path
hits real processes and fails.

### Broken tests

| File | Class | Test | Root Cause |
|---|---|---|---|
| test_hub.py | TestAsk | test_ask_gc_calls_subprocess | patches run, not Popen |
| test_hub.py | TestAsk | test_ask_cc_calls_subprocess | patches run, not Popen |
| test_hub.py | TestAsk | test_ask_strips_ansi | patches run, not Popen |
| test_hub.py | TestAsk | test_ask_timeout_exits | run side_effect; now needs Popen + time mock |
| test_hub.py | TestAsk | test_ask_query_file | patches run, not Popen |
| test_hub.py | TestAsk | test_ask_nonzero_exit_warns | patches run, not Popen |
| test_hub.py | TestAsk | test_ask_prepends_room_context_and_records_success | run.call_args.kwargs["input"] |
| test_hub.py | TestAsk | test_ask_success_recovers_yellow_peer | patches run, not Popen |
| test_hub.py | TestAsk | test_ask_eperm_marks_peer_red_and_blocks_next_call | patches run; assert_not_called |
| test_hub.py | TestAsk | test_ask_supports_literal_peer_env_vars | run.call_args.kwargs["env"] |
| test_hub.py | TestEnhancedCollaboration | test_ask_quiet_output_file_writes_response | run.call_args.kwargs["timeout"] |
| test_hub_v41_features.py | TestRoutingMetrics | test_action_ask_records_routing_metric_on_success | patches run, not Popen |
| test_hub_v41_features.py | TestRoutingMetrics | test_action_ask_records_routing_metric_on_nonzero_exit | patches run, not Popen |
| test_hub_v41_features.py | TestRoutingMetrics | test_action_ask_no_metric_when_ai_root_is_none | patches run, not Popen |

## 2. Root Cause Analysis

Old code:
```python
result = subprocess.run(cmd, input=query.encode(), capture_output=True, timeout=N, env=env)
# result.stdout, result.stderr, result.returncode
```

New code (Popen + heartbeat loop):
```python
proc = subprocess.Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, env=env)
_lease_open(ai_root, to, proc.pid, ...)
while True:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        _kill_process_tree(proc); raise TimeoutExpired(...)
    raw_out, raw_err = proc.communicate(input=input_bytes, timeout=min(heartbeat_sec, remaining))
    break
# proc.returncode checked after loop
```

Tests patched `subprocess.run` which is no longer called. The Popen path
runs real subprocess (e.g. `gemini`) which doesn't exist in CI → FileNotFoundError
→ outer `except Exception` → `sys.exit(1)`.

## 3. Fix Strategy

### 3.1 Helper function (add to BOTH test files)

```python
def _make_mock_proc(stdout=b"", stderr=b"", returncode=0):
    """Create a mock subprocess.Popen object for action_ask tests."""
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_proc.returncode = returncode
    mock_proc.communicate.return_value = (stdout, stderr)
    mock_proc.poll.return_value = returncode
    mock_proc.stdout.read.return_value = stdout
    mock_proc.stderr.read.return_value = stderr
    return mock_proc
```

### 3.2 Standard test pattern replacement

Before:
```python
mock_result = MagicMock()
mock_result.stdout = b"..."
mock_result.stderr = b""
mock_result.returncode = 0
with patch("subprocess.run", return_value=mock_result) as mock_run:
    hub.action_ask(...)
    call_args = mock_run.call_args[0][0]
```

After:
```python
mock_proc = _make_mock_proc(stdout=b"...", returncode=0)
with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
    hub.action_ask(...)
    call_args = mock_popen.call_args[0][0]
```

### 3.3 Assertion migrations

| Old assertion | New assertion |
|---|---|
| `mock_run.call_args[0][0]` | `mock_popen.call_args[0][0]` |
| `mock_run.call_args.kwargs["input"]` | `mock_proc.communicate.call_args.kwargs["input"]` |
| `mock_run.call_args.kwargs["env"]` | `mock_popen.call_args.kwargs["env"]` |
| `mock_run.call_args.kwargs["timeout"]` | remove or check `communicate.call_args.kwargs["timeout"]` |
| `mock_run.assert_not_called()` | `mock_popen.assert_not_called()` |

### 3.4 Timeout test (special case)

`test_ask_timeout_exits` needs `time.monotonic` to advance past the deadline.
Call sequence in `action_ask()`:
1. `t0 = time.monotonic()` → 0
2. `deadline = time.monotonic() + timeout_sec` → 0 + 120 = 120
3. Loop 1: `remaining = deadline - time.monotonic()` → 120 - 0 = 120 (> 0)
4. `proc.communicate(...)` raises `TimeoutExpired` → inner except
5. `proc.poll()` returns `None` → `_lease_renew()` (no-op, ai_root=None)
6. Loop 2: `remaining = deadline - time.monotonic()` → 120 - 200 = -80 (≤ 0)
7. `_kill_process_tree(proc)` → raise `TimeoutExpired`
8. Outer except → `sys.exit(1)`

Mock pattern:
```python
mock_proc = _make_mock_proc()
mock_proc.communicate.side_effect = subprocess.TimeoutExpired("gemini", 120)
mock_proc.poll.return_value = None
with patch("shutil.which", return_value="/usr/bin/gemini"), \
     patch("subprocess.Popen", return_value=mock_proc), \
     patch("hub.time.monotonic", side_effect=[0.0, 0.0, 0.0, 200.0, 200.0]), \
     patch("hub._kill_process_tree"):
    with pytest.raises(SystemExit):
        hub.action_ask("gc", "test", None, 120, None)
```

### 3.5 Timeout assertion in TestEnhancedCollaboration

`test_ask_quiet_output_file_writes_response` asserts `mock_run.call_args.kwargs["timeout"] == 7`.
With Popen, timeout_sec=0 → resolved to 7 from `_runtime_cfg`. Then:
`communicate(timeout=min(heartbeat_sec, remaining))` ≈ `min(30, ~7)` = ~7.
New assertion: `assert mock_proc.communicate.call_args.kwargs["timeout"] <= 7`

### 3.6 conftest.py

Add `leases.json` to the `ai_dir` fixture so `_lease_sweep` and `_lease_open`
don't attempt file creation on every call:
```python
(ai / "leases.json").write_text(json.dumps({}), encoding="utf-8")
```

### 3.7 New lease unit tests (bonus, add to test_hub_v41_features.py)

Add `TestLease` class:
- `test_lease_open_creates_entry` — verify `leases.json` gets the entry
- `test_lease_renew_updates_heartbeat_and_expires` — verify heartbeat_at updated
- `test_lease_close_sets_status` — verify status transitions
- `test_lease_sweep_closes_expired` — verify orphan detection
- `test_action_lease_status_prints_status` — verify dispatcher action

## 4. Execution Order

```
STEP 1  conftest.py           — add leases.json init to ai_dir fixture
STEP 2  test_hub.py           — add _make_mock_proc, fix 11 TestAsk/TestEnhanced tests
STEP 3  test_hub_v41_features — add _make_mock_proc, fix 3 TestRoutingMetrics tests
STEP 4  test_hub_v41_features — add TestLease class (5 tests)
STEP 5  Run: pytest test_hub.py test_hub_v41_features.py -q
STEP 6  Run: pytest _sys/tests/unit -q (full suite baseline)
STEP 7  Commit
STEP 8  Push
```

## 5. Peer Confirmation Required

Before execution, broadcast to gc and cx:
- Share this plan
- Confirm: no gaps, no alternative approach preferred
- Get ACK from both before proceeding

## 6. Success Criteria

- All 13 previously failing tests now pass
- Previously passing 95 tests still pass (no regressions)
- New `TestLease` class adds 5 tests
- Total: ≥ 108 tests passing in hub test files
- Full suite: pre-existing 23 failures unchanged, no new failures
