# General — Session Management
> Source: protocol-session.md v4.2

---

## 1. Session Decision Tree (entry point)

```
Read .ai/state.json
  ├─ room_id exists + this peer in members + updated_at < 4h?
  │     → RESUME: hub.py init-session (rejoin) + read full handoff.md
  │
  ├─ room_id exists + 4h ≤ updated_at < 24h?
  │     → NEW + CONTEXT FILL:
  │       1. hub.py init-session (new join, same room_id)
  │       2. hub.py context-fill → inject into first prompt
  │
  ├─ room_id exists + updated_at ≥ 24h?
  │     → STALE + FULL FILL:
  │       1. hub.py end-session for stale members
  │       2. hub.py init-session (new session)
  │       3. hub.py context-fill (all fill sections)
  │
  └─ no room_id
        → COLD START: hub.py init-session (empty handoff)
```

---

## 2. Startup Contract (all peers — INV-05)

```
1. hub.py init-session --agent {peer_id}
2. hub.py health-update --peer {peer_id} --status GREEN
3. hub.py context-fill   ← zero-token local read, inject into first prompt
4. hub.py check --target {peer_id}   ← read mailbox
```

---

## 3. Handoff Structure (`handoff.md`)

6 rolling sections, max 12KB total:

| Section | Content | Max Items |
|---------|---------|:---------:|
| `[GOAL]` | Current mission | 1 |
| `[RECENT_COMPLETED]` | Done tasks | 5 |
| `[PENDING_ISSUES]` | Blockers | 3 |
| `[KEY_DECISIONS]` | Architecture choices | 3 |
| `[CONSENSUS_HISTORY]` | Round outcomes | 10 |
| `[ACTIVE_THREADS]` | In-flight threads | 5 |

Context-fill sections controlled by `protocol.json["session"]["context_fill_sections"]`.
`fill_depth_multiplier`: gc=3 (reads more), others=1.

---

## 4. Session Expiry

| Rule | Value | Config key |
|------|------:|:-----------|
| Resume window | 4h | `session.resume_window_hours` |
| Staleness threshold | 24h | `session.handoff_staleness_hours` |
| Consensus round timeout | 30m | `consensus.timeout_minutes` |

---

## 5. CLI Session Reuse (cx / gc)

`hub.py ask` reuses CLI process sessions across calls (scope_key = room_id).

| Peer | New session flag | Resume flag |
|------|-----------------|------------|
| cx | `codex exec -s workspace-write --json --ignore-rules` | `codex exec resume <thread_id> ...` |
| gc | `gemini --session-id <uuid> -p - -o text --approval-mode auto_edit --skip-trust` | `gemini --resume <uuid> ...` |

State file: `_sys/{peer_dir}/session_state.json` (gitignored).
On resume failure: retire old session → retry fresh once.
Topic boundary (`new-topic`, `clear-room`): all peer sessions retired.
Override: `hub.py ask --session-policy fresh` for independent cross-review calls.

---

## 6. Handoff Rolling Rule

When `handoff.md` exceeds **2KB**, trim as follows:
1. Move all items in `[RECENT_COMPLETED]` marked `[DONE]` to `_archive/handoff-{YYYYMMDD}.md` (append).
2. Keep a max of 3 items in `[RECENT_COMPLETED]` after trim.
3. `[CONSENSUS_HISTORY]` — keep last 5 rounds only; archive earlier rounds.
4. Never delete `[GOAL]`, `[PENDING_ISSUES]`, or `[ACTIVE_THREADS]` without human instruction.

Command: `hub.py checkpoint --agent {peer_id} --trim` triggers the rolling trim.

---

## 7. Zero-Token Local Reads (always exempt, all COLLAB_RATE levels)

These reads are **always zero-token** — no COLLAB_RATE gate applies:

| Resource | Why always exempt |
|----------|------------------|
| `_sys/{peer}/health.json` | Health check is a local file read, no model call |
| `.ai/sessions/{room}/handoff.md` | Re-orientation read at session start |
| `.ai/mailbox.json` | Inbox check at session start |
| `_sys/ai/runtime-directives.jsonl` | Active directive injection (observe phase) |
| `_sys/ai/user-directives.md` | Standing rules (observe phase) |

A read is NOT zero-token if it triggers a model call, network request, or side-effect write.

---

## 8. Stable Fingerprint

**Source:** `hub.py:_session_fingerprint(health_peer, exe_name)`

A short 8-char SHA-1 hash that identifies the *static* invocation flags for a peer session.
It is **stable across calls** and only changes when permission flags change.

### Canonical Input

```
raw = base_exe + "|" + ",".join(static_flags)
fingerprint = sha1(raw.encode()).hexdigest()[:8]
```

- `base_exe = os.path.basename(exe_name)` — filename only, never a full path.
  This prevents drift when the PATH root changes (e.g., USB drive letter change).
- `static_flags` per peer (hardcoded in `_build_session_cmd`):

| Peer | Static flags included | Dynamic values excluded |
|------|-----------------------|------------------------|
| `cx` | `-s workspace-write --json --ignore-rules` | *(none dynamic)* |
| `gc` | `-p - -o text --approval-mode auto_edit --skip-trust` | `--session-id <uuid>` |
| others | *(empty — no session reuse)* | — |

### Drift Detection

On every `hub.py ask` with session reuse:
1. Compute `current_fp = _session_fingerprint(health_peer, exe_name)`.
2. Load `existing_session = _get_active_session(health_peer, scope_key)`.
3. If `stored_fp` exists and `stored_fp != current_fp`:
   - Log: `[HUB:WARN] {peer} session fingerprint drift ({old} → {new}), retiring for fresh start`
   - Call `_retire_session(peer, scope_key, "fingerprint_drift")`
   - Proceed as if no existing session.

### Scope Key

Session state is keyed by `scope_key = explicit_scope ?? room_id ?? "default"`.
State file: `_sys/{peer_dir}/session_state.json` (gitignored).

---

## 9. Resume Failure Classification

**Source:** `hub.py:_classify_resume_failure(stderr)` → `"transient"` | `"permanent"`

Called when a session-resume attempt exits non-zero (`proc.returncode != 0 and is_resume_attempt`).

### Classification Rules

| Class | Trigger patterns in stderr | Behavior |
|-------|---------------------------|----------|
| **Transient** | `timeout`, `timed out`, `rate limit`, `quota`, `503`, `429`, `connection refused`, `network error`, `unable to reach` | Keep session alive. Report error. Exit. Caller retries later. |
| **Permanent** | Any other content — or empty stderr | Retire session → retry once with fresh session. |

> Empty stderr always maps to **permanent** (default).

### Permanent Failure Flow

```
proc.returncode != 0 AND is_resume_attempt AND fail_type == "permanent"
  → _retire_session(peer, scope_key, "resume_failed")
  → _build_session_cmd(peer, session_id=None, exe)   # fresh
  → subprocess.Popen(fresh_cmd)
  → communicate(query)
  → if success: _set_active_session(new_id, fingerprint=current_fp)
  → if failure: _record_ask_failure + exit
```

### Transient Failure Flow

```
proc.returncode != 0 AND is_resume_attempt AND fail_type == "transient"
  → session NOT retired (still active in session_state.json)
  → [HUB:WARN] ... keeping session for retry
  → _record_ask_failure
  → exit (no auto-retry — caller decides)
```
