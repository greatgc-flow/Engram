"""
hub.py — Portable Dev Environment AI 협업 허브 (Protocol v4.1)
5-peer: cc, ca, gc, ag, cx — config-driven via orchestration.json + lifecycle_policy.json

v4.1: Layered policy (General/Specific/Connectors/Ambiguity). lifecycle_policy.json driven.
v4.0: N-Way Room + health-update/check/peer-status/context-fill/checkpoint actions.
v3.1: 실시간 협업 가시성 로그 (_log_p2p) 추가.
v3.0: N-Way Room 세션 기반 평등 권등 구조 구현.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore[assignment]

# Windows 콘솔 UTF-8 강제
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ─────────────────────────────────────────────────────────────
# .ai/ 프로젝트 루트 탐색
# ─────────────────────────────────────────────────────────────

def find_ai_root() -> Path:
    cwd = Path.cwd().resolve()
    candidate = cwd
    while True:
        if (candidate / ".ai").exists():
            return candidate / ".ai"
        if (candidate / ".git").exists():
            return candidate / ".ai"
        parent = candidate.parent
        if parent == candidate:
            return cwd / ".ai"
        candidate = parent


def _load_orchestration() -> dict:
    """_sys/ai/orchestration.json 로드 (hub 전용 상수 포함)."""
    path = Path(__file__).parent.parent / "ai" / "orchestration.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {}


def _load_protocol_cfg() -> dict:
    """_sys/ai/protocol.json 로드 (협업 정책 마스터 설정)."""
    path = Path(__file__).parent.parent / "ai" / "protocol.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {}


def _load_lifecycle_policy() -> dict:
    """Load config-driven peer lifecycle policy."""
    path = Path(__file__).parent.parent / "ai" / "lifecycle_policy.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {}


def _load_model_profiles() -> dict:
    """Load _sys/ai/model_profiles.json."""
    path = Path(__file__).parent.parent / "ai" / "model_profiles.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {}


def _resolve_profile_id(node_id: str) -> str | None:
    """Return the model_profiles.json profile_id for a given node_id, or None."""
    profiles = _load_model_profiles().get("profiles", {})
    nodes = _default_nodes()["nodes"]
    node = nodes.get(node_id, {})
    explicit = node.get("profile_id")
    if explicit and explicit in profiles:
        return explicit
    peer = node.get("peer") or node_id
    mode = node.get("profile_mode") or "default"
    for profile_id, profile in profiles.items():
        if profile.get("peer") == peer and profile.get("mode") == mode:
            return profile_id
    return None


def _node_to_peer_map() -> dict:
    policy = _load_lifecycle_policy()
    configured = policy.get("identity", {}).get("node_to_peer", {})
    if configured:
        return configured
    return {"cc": "claude", "ca": "claude", "gc": "gemini", "ag": "antigravity", "cx": "codex"}


def _peer_sys_dir(peer_id: str) -> Path:
    """peers.json의 sys_subdir로 _sys/{subdir}/ 해석 — 하드코딩 없음.

    node_id(cc, ca, gc, ag, cx) → peers.json key(claude, gemini, antigravity, codex) 매핑 포함.
    """
    # node_id → peers.json key 매핑 (orchestration.json 또는 기본값)
    peers = _load_peers()
    peer_data = peers.get("peers", peers)
    peer_key = _node_to_peer_map().get(peer_id, peer_id)
    cfg = peer_data.get(peer_key, {})
    subdir = cfg.get("sys_subdir", peer_key)
    return Path(__file__).parent.parent / subdir


def _load_peers() -> dict:
    """_sys/ai/peers.json 로드."""
    path = Path(__file__).parent.parent / "ai" / "peers.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("peers", {}) if path.exists() else {}
    except Exception:
        return {}


def _default_nodes() -> dict:
    """orchestration.json hub_nodes 배열에서 기본 노드 목록을 읽어 반환."""
    orch = _load_orchestration()
    nodes = {}
    for entry in orch.get("hub_nodes", []):
        if entry.get("enabled") is False:
            continue
        nid = entry.get("node_id")
        if nid:
            nodes[nid] = {k: v for k, v in entry.items() if k != "node_id"}
    if not nodes:
        # orchestration.json 없을 때 최소 fallback (claude만)
        nodes = {"cc": {"type": "peer", "invoke": "claude", "invoke_args": ["-p", "{query}"], "timeout": 0, "memory": "persistent"}}
    return {"version": "2", "nodes": nodes}


def ensure_ai_dir(ai_root: Path) -> Path:
    (ai_root / ".lock").mkdir(parents=True, exist_ok=True)
    (ai_root / "sessions").mkdir(parents=True, exist_ok=True)
    (ai_root / "consensus").mkdir(parents=True, exist_ok=True)
    (ai_root / "mailbox").mkdir(parents=True, exist_ok=True)  # Maildir storage
    if not _leases_path(ai_root).exists():
        _write_json(_leases_path(ai_root), {})
    if not (ai_root / "mailbox.json").exists():
        _write_json(ai_root / "mailbox.json", {"messages": [], "unread_count": 0})
    if not (ai_root / "state.json").exists():
        _write_state(ai_root, {
            "room_id": None,
            "members": {}, # {node_id: sid}
            "mission": None, "blocked": None, "phase": None,
            "active_coordinator": None,
            "human_interface_peer": None,
            "role_assignments": {},
            "updated_at": None
        })
    if not (ai_root / "task_registry.json").exists():
        _write_json(ai_root / "task_registry.json", {})
    if not (ai_root / "nodes.json").exists():
        _write_json(ai_root / "nodes.json", _default_nodes())
    # Provenance logs — touch only; schema documented below as constants
    for log_name in ("ask_history.jsonl", "routing_metrics.jsonl"):
        if not (ai_root / log_name).exists():
            (ai_root / log_name).write_text("", encoding="utf-8")
    return ai_root


# ask_history.jsonl entry schema (append-only JSONL):
# {"ts": ISO8601, "peer_id": str, "profile_id": str|null, "query_file": str|null,
#  "output_file": str|null, "elapsed_sec": int|null, "health_state_at_ask": str,
#  "success": bool, "failure_reason": str|null}
#
# routing_metrics.jsonl entry schema (append-only JSONL):
# {"ts": ISO8601, "task_type": str, "selected_peer": str, "profile_id": str|null,
#  "outcome": "success"|"failure"|"degraded", "latency_sec": float|null}


# ─────────────────────────────────────────────────────────────
# JSON / 유틸리티
# ─────────────────────────────────────────────────────────────

def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _validate_state(state: dict) -> None:
    if not isinstance(state, dict):
        raise ValueError("state must be an object")
    for key in ("active_coordinator", "leader"):
        if key in state and state[key] is not None and not isinstance(state[key], str):
            raise ValueError(f"state.{key} must be a string or null")
    leadership = state.get("leadership")
    if leadership is not None:
        if not isinstance(leadership, dict):
            raise ValueError("state.leadership must be an object")
        status = leadership.get("status")
        if status is not None and status not in {"ACTIVE", "VACANT", "YIELDED"}:
            raise ValueError("state.leadership.status is invalid")
    assignments = state.get("role_assignments")
    if assignments is not None:
        if not isinstance(assignments, dict):
            raise ValueError("state.role_assignments must be an object")
        for role, info in assignments.items():
            if not isinstance(role, str) or not isinstance(info, dict) or not isinstance(info.get("peer"), str):
                raise ValueError("state.role_assignments entries must include peer strings")


def _write_state(ai_root: Path, state: dict) -> None:
    _validate_state(state)
    _write_json(ai_root / "state.json", state)


def _validate_task_registry(data: dict) -> None:
    if not isinstance(data, dict):
        raise ValueError("task registry must be an object")
    for task_id, task in data.items():
        if not isinstance(task_id, str) or not isinstance(task, dict):
            raise ValueError("task registry entries must be objects")
        if task.get("task_id") != task_id:
            raise ValueError("task_id mismatch")
        if task.get("status") not in {"ACTIVE", "BLOCKED", "DONE", "TRANSFERRED"}:
            raise ValueError("task status is invalid")
        checkpoints = task.get("checkpoints", [])
        if not isinstance(checkpoints, list):
            raise ValueError("task checkpoints must be a list")
        for cp in checkpoints:
            if not isinstance(cp, dict) or not cp.get("peer") or not cp.get("note") or not cp.get("at"):
                raise ValueError("task checkpoint entries require peer, note, and at")


def _write_task_registry(ai_root: Path, data: dict) -> None:
    _validate_task_registry(data)
    _write_json(_task_registry_path(ai_root), data)


def _append_jsonl(path: Path, item: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _short_id(prefix: str = "") -> str:
    return prefix + uuid.uuid4().hex[:4]


def _log_p2p(action: str, details: str, from_node: str | None = None, to_node: str | None = None) -> None:
    """실시간 협업 가시성을 위한 정형화된 로그 출력."""
    if os.environ.get("P2P_VERBOSE") != "1":
        # 루틴한 폴링/상태 조회는 기본적으로 숨김
        routine = action.lower() in ("check", "status", "check-gate", "mark-read", "list-nodes", "consensus-check")
        if routine: return
    
    n_from = from_node.upper() if from_node else "SYS"
    n_to = to_node.upper() if to_node else "ALL"
    
    # [P2P] 프리픽스로 가시성 확보
    print(f"  ━━ P2P [{n_from} → {n_to}] {action}: {details}", file=sys.stderr)


def _strip_ansi(text: str) -> str:
    return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)


def _extract_jsonl_text(raw: str, peer_id: str, ai_root: Path | None) -> str:
    """JSONL 스트림(--json 플래그)에서 텍스트만 추출, .ai/out/<peer>.last.md에 저장.

    지원 이벤트 형식:
    - codex: {"type":"item.completed","item":{"text":"..."}}
    - codex delta: {"type":"item.delta","item":{"type":"text","text":"..."}}
    - codex message: {"type":"message","role":"assistant","content":[{"type":"text","text":"..."}]}
    - 일반: {"text":"..."} / {"content":"..."} / {"message":"..."}
    """
    texts: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = obj.get("type", "")
        # codex item.completed
        if t == "item.completed":
            item = obj.get("item", {})
            val = item.get("text") or item.get("content", "")
            if val:
                texts.append(val)
        # codex item.delta (streaming)
        elif t == "item.delta":
            delta = obj.get("item", {})
            if delta.get("type") == "text":
                val = delta.get("text", "")
                if val:
                    texts.append(val)
        # codex / openai message event
        elif t == "message":
            role = obj.get("role", "")
            if role in ("assistant", ""):
                content = obj.get("content", "")
                if isinstance(content, str) and content:
                    texts.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            val = block.get("text", "")
                            if val:
                                texts.append(val)
        # 일반 플랫 필드
        elif "text" in obj and obj["text"]:
            texts.append(obj["text"])
        elif "content" in obj and isinstance(obj["content"], str) and obj["content"]:
            texts.append(obj["content"])
        elif "message" in obj and isinstance(obj["message"], str) and obj["message"]:
            texts.append(obj["message"])

    # delta 누적은 그대로, completed는 마지막 것만 의미 있으므로 중복 제거
    seen: set[str] = set()
    deduped = [t for t in texts if not (t in seen or seen.add(t))]  # type: ignore[func-returns-value]
    result = "\n\n".join(deduped).strip() or raw.strip()

    # .ai/out/<peer>.last.md 에 저장
    if ai_root:
        out_dir = ai_root / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{peer_id}.last.md").write_text(result, encoding="utf-8")
    return result


# ─────────────────────────────────────────────────────────────
# filelock 헬퍼
# ─────────────────────────────────────────────────────────────

def _get_lock(ai_root: Path, resource: str):
    from filelock import FileLock
    lock_path = ai_root / ".lock" / f"{resource}.lock"
    os.makedirs(ai_root / ".lock", exist_ok=True)
    return FileLock(str(lock_path), timeout=10)


# ─────────────────────────────────────────────────────────────
# nodes.json 관리
# ─────────────────────────────────────────────────────────────

def _load_nodes(ai_root: Path) -> dict:
    """orchestration.json을 base로 로드. nodes.json은 custom 추가 노드만 병합."""
    base = _default_nodes()["nodes"]
    nodes_path = ai_root / "nodes.json"
    if nodes_path.exists():
        data = _read_json(nodes_path)
        custom = data.get("nodes", {})
        # orchestration 노드가 우선, custom은 신규 노드만 추가
        return {**custom, **base}
    return base


# ─────────────────────────────────────────────────────────────
# 설정 및 상수
# ─────────────────────────────────────────────────────────────

def load_config() -> dict:
    cfg_path = Path(__file__).parent / "hub_config.json"
    defaults = {
        "limits": {
            "mailbox_max": 500,
            "handoff_max_chars": 12000,
            "handoff_max_completed": 5,
            "handoff_max_issues": 3,
            "handoff_max_decisions": 3,
            "handoff_max_consensus": 10,
            "handoff_max_threads": 5,
            "large_payload_threshold": 4000
        }
    }
    if not cfg_path.exists():
        return defaults
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        # Merge defaults
        for k, v in defaults["limits"].items():
            cfg.setdefault("limits", {})
            if k not in cfg["limits"]:
                cfg["limits"][k] = v
        return cfg
    except Exception:
        return defaults

_CFG = load_config()
_LIMITS = _CFG["limits"]

HANDOFF_MAX_CHARS = _LIMITS["handoff_max_chars"]
HANDOFF_MAX_COMPLETED = _LIMITS["handoff_max_completed"]
HANDOFF_MAX_ISSUES = _LIMITS["handoff_max_issues"]
HANDOFF_MAX_DECISIONS = _LIMITS["handoff_max_decisions"]
HANDOFF_MAX_CONSENSUS = _LIMITS["handoff_max_consensus"]
HANDOFF_MAX_THREADS = _LIMITS["handoff_max_threads"]

_MAILBOX_MAX = _LIMITS["mailbox_max"]
_LARGE_PAYLOAD_THRESHOLD = _LIMITS["large_payload_threshold"]

_HANDOFF_SECTIONS = [
    "GOAL", "RECENT_COMPLETED", "PENDING_ISSUES", "KEY_DECISIONS",
    "CONSENSUS_HISTORY", "ACTIVE_THREADS"
]


def _parse_handoff(text: str) -> dict:
    sections: dict[str, list[str]] = {s: [] for s in _HANDOFF_SECTIONS}
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        for sec in _HANDOFF_SECTIONS:
            if stripped == f"## [{sec}]":
                current = sec
                break
        else:
            if current and stripped.startswith("- "):
                val = stripped[2:]
                if val != "(없음)":
                    sections[current].append(val)
    return sections


def _render_handoff(sections: dict) -> str:
    lines = []
    for sec in _HANDOFF_SECTIONS:
        lines.append(f"## [{sec}]")
        items = sections.get(sec, [])
        lines += [f"- {x}" for x in items] or ["- (없음)"]
        lines.append("")
    return "\n".join(lines)


def _read_handoff(session_dir: Path) -> dict:
    path = session_dir / "handoff.md"
    if not path.exists():
        return {s: [] for s in _HANDOFF_SECTIONS}
    return _parse_handoff(path.read_text(encoding="utf-8"))


def _write_handoff(session_dir: Path, sections: dict) -> None:
    sections["RECENT_COMPLETED"] = sections.get("RECENT_COMPLETED", [])[-HANDOFF_MAX_COMPLETED:]
    sections["PENDING_ISSUES"]   = sections.get("PENDING_ISSUES", [])[-HANDOFF_MAX_ISSUES:]
    sections["KEY_DECISIONS"]    = sections.get("KEY_DECISIONS", [])[-HANDOFF_MAX_DECISIONS:]
    sections["CONSENSUS_HISTORY"] = sections.get("CONSENSUS_HISTORY", [])[-HANDOFF_MAX_CONSENSUS:]
    sections["ACTIVE_THREADS"]    = sections.get("ACTIVE_THREADS", [])[-HANDOFF_MAX_THREADS:]
    text = _render_handoff(sections)
    while len(text) > HANDOFF_MAX_CHARS and sections["RECENT_COMPLETED"]:
        sections["RECENT_COMPLETED"].pop(0)
        text = _render_handoff(sections)
    (session_dir / "handoff.md").write_text(text, encoding="utf-8")


# ─────────────────────────────────────────────────────────────
# Write 액션 (filelock)
# ─────────────────────────────────────────────────────────────

def action_init_session(ai_root: Path, agent: str, room_id: str | None = None) -> None:
    _lease_sweep(ai_root)
    sid = _short_id(agent[:1])
    with _get_lock(ai_root, "state"):
        state = _read_json(ai_root / "state.json")
        if room_id: state["room_id"] = room_id
        elif not state.get("room_id"): state["room_id"] = _short_id("room-")
        members = state.get("members", {})
        members[agent] = sid
        state["members"] = members
        state["updated_at"] = _now()
        _write_state(ai_root, state)
        _log_p2p("JOIN", f"Room={state['room_id']} SID={sid}", from_node=agent)
    session_dir = ai_root / "sessions" / state["room_id"]
    session_dir.mkdir(parents=True, exist_ok=True)
    print(sid)


def action_end_session(ai_root: Path, agent: str) -> None:
    with _get_lock(ai_root, "state"):
        state = _read_json(ai_root / "state.json")
        room_id = state.get("room_id")
        ts = _now()
        members = state.get("members", {})
        if agent in members: del members[agent]
        state["members"] = members
        state["updated_at"] = ts
        _write_state(ai_root, state)
        _log_p2p("EXIT", "Session ended", from_node=agent)
    if room_id:
        session_dir = ai_root / "sessions" / room_id
        session_dir.mkdir(parents=True, exist_ok=True)
        handoff = _read_handoff(session_dir)
        handoff.setdefault("RECENT_COMPLETED", []).append(f"{ts[:10]} {agent}: 세션 종료")
        _write_handoff(session_dir, handoff)
    with _get_lock(ai_root, "mailbox"):
        mb = _read_json(ai_root / "mailbox.json")
        msgs = [m for m in mb.get("messages", []) if m.get("status") != "read"]
        mb["messages"] = msgs
        mb["unread_count"] = sum(1 for m in msgs if m.get("status") == "unread")
        _write_json(ai_root / "mailbox.json", mb)
    print(f"[END] {agent} 세션 종료 완료")


def _prune_mailbox_messages(messages: list[dict], send_policy: dict | None = None) -> list[dict]:
    send_policy = send_policy or _load_lifecycle_policy().get("messaging", {}).get("send", {})
    ttl_by_priority = send_policy.get("ttl_hours_by_priority", {})
    if not ttl_by_priority:
        return messages
    now = datetime.now()
    kept: list[dict] = []
    default_priority = send_policy.get("default_priority", "INFO")
    for msg in messages:
        priority = msg.get("priority") or msg.get("type") or default_priority
        ttl_hours = ttl_by_priority.get(priority)
        if ttl_hours is None:
            kept.append(msg)
            continue
        try:
            ts = datetime.fromisoformat(str(msg.get("timestamp", "")))
        except ValueError:
            kept.append(msg)
            continue
        if (now - ts).total_seconds() <= float(ttl_hours) * 3600:
            kept.append(msg)
    return kept


def _payload_ids_from_messages(messages: list[dict]) -> set[str]:
    ids: set[str] = set()
    for msg in messages:
        content = str(msg.get("content", ""))
        if content.startswith("payload://"):
            ids.add(content.replace("payload://", "", 1))
    return ids


def _gc_unreferenced_payloads(ai_root: Path, messages: list[dict]) -> None:
    payload_dir = ai_root / "payloads"
    if not payload_dir.exists():
        return
    referenced = _payload_ids_from_messages(messages)
    for payload_path in payload_dir.glob("*.json"):
        if payload_path.stem not in referenced:
            try:
                payload_path.unlink()
            except OSError:
                pass


def action_send(
    ai_root: Path, from_: str, to: str, msg: str,
    thread_id: str | None = None,
    msg_type: str = "MSG",
    cc_list: list[str] | None = None,
    ref_id: int | None = None,
    priority: str | None = None,
) -> None:
    if cc_list is None: cc_list = []
    send_policy = _load_lifecycle_policy().get("messaging", {}).get("send", {})
    if send_policy.get("mode") in ("disabled", "remove"):
        print("[HUB:ERR] send is disabled by lifecycle_policy.json", file=sys.stderr)
        sys.exit(1)
    allowed_types = set(send_policy.get("allowed_types", []))
    if allowed_types and msg_type not in allowed_types:
        print(f"[HUB:ERR] send type '{msg_type}' is not allowed by lifecycle_policy.json", file=sys.stderr)
        sys.exit(1)
    auto_thread = thread_id or _short_id("t-")
    ttl_by_priority = send_policy.get("ttl_hours_by_priority", {})
    priority = priority or (msg_type if msg_type in ttl_by_priority else None)
    priority = priority or send_policy.get("default_priority", "INFO")

    # 대용량 페이로드 오프로드 (Threshold 초과 시)
    if len(msg) > _LARGE_PAYLOAD_THRESHOLD and msg_type == "MSG":
        payload_id = _short_id("p-")
        payload_dir = ai_root / "payloads"
        payload_dir.mkdir(parents=True, exist_ok=True)
        payload_path = payload_dir / f"{payload_id}.json"
        _write_json(payload_path, {"from": from_, "to": to, "content": msg, "timestamp": _now()})
        
        msg = f"payload://{payload_id}"
        msg_type = "PAYLOAD_REF"
        _log_p2p("OFFLOAD", f"Large msg saved to payloads/{payload_id}.json", from_node=from_)

    with _get_lock(ai_root, "mailbox"):
        mb = _read_json(ai_root / "mailbox.json")
        msgs = _prune_mailbox_messages(mb.get("messages", []), send_policy)
        if len(msgs) >= _MAILBOX_MAX:
            msgs = [m for m in msgs if m.get("status") != "read"]
            if len(msgs) >= _MAILBOX_MAX:
                msgs = msgs[-(  _MAILBOX_MAX - 1):]
        new_id = (msgs[-1]["id"] + 1) if msgs else 1
        msg_uuid = uuid.uuid4().hex[:8]
        new_msg = {
            "id": new_id, "_uuid": msg_uuid, "thread_id": auto_thread, "type": msg_type,
            "from": from_, "to": to, "cc": cc_list, "content": msg,
            "status": "unread", "timestamp": _now(), "ref": ref_id,
            "priority": priority,
        }
        msgs.append(new_msg)
        mb["messages"] = msgs
        mb["unread_count"] = sum(1 for m in msgs if m.get("status") == "unread")
        _write_json(ai_root / "mailbox.json", mb)
        _maildir_write(ai_root, new_msg)   # Maildir: durable per-message file
        _gc_unreferenced_payloads(ai_root, msgs)
        _log_p2p("SEND", f"({msg_type}) {msg[:60]}...", from_node=from_, to_node=to)
    cc_str = f" cc={','.join(cc_list)}" if cc_list else ""
    ref_str = f" ref={ref_id}" if ref_id else ""
    print(f"[HUB] SENT  {from_}→{to} | thread={auto_thread} | id={new_id} type={msg_type}{cc_str}{ref_str}")


def action_broadcast(
    ai_root: Path,
    from_: str,
    msg: str,
    targets: list[str] | None = None,
    msg_type: str = "MSG",
    priority: str | None = None,
) -> None:
    policy = _load_lifecycle_policy().get("messaging", {}).get("broadcast", {})
    if policy.get("mode") in ("disabled", "remove"):
        print("[HUB:ERR] broadcast is disabled by lifecycle_policy.json", file=sys.stderr)
        sys.exit(1)
    if targets is None:
        state = _read_json(ai_root / "state.json")
        targets = [node for node in state.get("members", {}).keys() if node != from_]
    targets = [target for target in dict.fromkeys(targets) if target and target != from_]
    if not targets:
        print("[HUB] BROADCAST no targets")
        return
    thread_id = _short_id("b-")
    if len(msg) > _LARGE_PAYLOAD_THRESHOLD and msg_type == "MSG":
        payload_id = _short_id("p-")
        payload_dir = ai_root / "payloads"
        payload_dir.mkdir(parents=True, exist_ok=True)
        _write_json(payload_dir / f"{payload_id}.json", {
            "from": from_,
            "to": targets,
            "content": msg,
            "timestamp": _now(),
        })
        msg = f"payload://{payload_id}"
        msg_type = "PAYLOAD_REF"
        _log_p2p("OFFLOAD", f"Broadcast saved to payloads/{payload_id}.json", from_node=from_)
    for target in targets:
        action_send(ai_root, from_, target, msg, thread_id, msg_type, [], None, priority)
    print(f"[HUB] BROADCAST {from_} -> {','.join(targets)} | thread={thread_id}")


def action_mark_read(ai_root: Path, target: str, all_: bool, msg_id: int | None) -> None:
    with _get_lock(ai_root, "mailbox"):
        mb = _read_json(ai_root / "mailbox.json")
        msgs = mb.get("messages", [])
        count = 0
        for m in msgs:
            if m.get("to") == target and m.get("status") == "unread":
                if all_ or m.get("id") == msg_id:
                    m["status"] = "read"; count += 1
        mb["unread_count"] = sum(1 for m in msgs if m.get("status") == "unread")
        _write_json(ai_root / "mailbox.json", mb)
        _maildir_mark_read(ai_root, msg_id, target, all_)   # sync maildir files
    print(f"[READ] {count}개 메시지 읽음 처리")


def action_append_log(ai_root: Path, axis: str, script: str, status: str, detail: str) -> None:
    log_path = ai_root / "log.jsonl"
    entry = {"ts": _now(), "axis": axis, "script": script, "status": status, "detail": detail}
    with _get_lock(ai_root, "log"):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"[LOG] {axis} {script} → {status}")


def action_archive_file(ai_root: Path, name: str, file_path: str) -> None:
    src = Path(file_path)
    if not src.exists(): sys.exit(1)
    archive_dir = ai_root.parent / "_archive"
    archive_dir.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    shutil.copy2(src, archive_dir / f"{name}-{date_str}.json")
    shutil.copy2(src, archive_dir / f"{name}-latest.json")
    print(f"[ARCHIVE] {name} → {name}-latest.json")


def action_update_status(ai_root: Path, mission: str, blocked: str | None, phase: str | None) -> None:
    with _get_lock(ai_root, "state"):
        state = _read_json(ai_root / "state.json")
        state["mission"] = mission
        if blocked is not None: state["blocked"] = blocked if blocked else None
        if phase is not None: state["phase"] = phase
        state["updated_at"] = _now()
        _write_state(ai_root, state)
        _log_p2p("STATUS", f"Mission={mission} Phase={phase}", from_node="SYSTEM")
    print(f"[STATUS] mission={mission}")


# ─────────────────────────────────────────────────────────────
# Read 액션 (Lock-Free)
# ─────────────────────────────────────────────────────────────

def action_check(ai_root: Path, target: str) -> None:
    maildir_msgs = _maildir_read_all(ai_root)
    if maildir_msgs:
        all_msgs = maildir_msgs
    else:
        mb = _read_json(ai_root / "mailbox.json")
        all_msgs = mb.get("messages", [])
    unread = [m for m in all_msgs if (m.get("to") == target or target in m.get("cc", [])) and m.get("status") == "unread"]
    if not unread: print(f"[HUB] READ  0 messages for {target} (inbox empty)"); return
    print(f"[HUB] READ  {len(unread)} messages for {target}\n")
    for m in unread:
        ts = m.get("timestamp", "")[:16]
        content = m.get("content", "")
        
        # Payload dereference
        if content.startswith("payload://"):
            payload_id = content.replace("payload://", "")
            payload_path = ai_root / "payloads" / f"{payload_id}.json"
            if payload_path.exists():
                pdata = _read_json(payload_path)
                content = pdata.get("content", content) + f"\n\n(Payload loaded from {payload_id}.json)"
            else:
                content = f"[ERROR: Payload {payload_id} not found]"

        print(f"**[{m['id']}]** From: **{m['from']}** | {ts} | type={m.get('type','MSG')}\n{content}\n---")


def action_list_nodes(ai_root: Path) -> None:
    nodes = _load_nodes(ai_root)
    print(f"[HUB] NODES ({len(nodes)})")
    for nid, cfg in nodes.items():
        print(f"  {nid}: tier={cfg.get('tier', '-')} type={cfg.get('type', '-')} invoke={cfg.get('invoke', '-')}")


def action_register_node(
    ai_root: Path,
    node_id: str,
    tier: int,
    node_type: str,
    invoke: str,
    invoke_args_str: str,
    memory: str,
    timeout: int,
) -> None:
    invoke_args = [a.strip() for a in invoke_args_str.split(",") if a.strip()]
    with _get_lock(ai_root, "nodes"):
        data = _read_json(ai_root / "nodes.json") if (ai_root / "nodes.json").exists() else _default_nodes()
        data.setdefault("nodes", {})[node_id] = {
            "tier": tier, "type": node_type,
            "invoke": invoke, "invoke_args": invoke_args,
            "memory": memory, "timeout": timeout,
        }
        _write_json(ai_root / "nodes.json", data)
    print(f"[REGISTER] {node_id} (tier={tier}, invoke={invoke})")


def action_status(ai_root: Path) -> None:
    _lease_sweep(ai_root)
    state = _read_json(ai_root / "state.json")
    mb = _read_json(ai_root / "mailbox.json")
    unread_count = mb.get("unread_count", 0)
    
    print("### [ROOM STATUS]")
    print(f"**Room ID**: {state.get('room_id') or '없음'}")
    leadership = state.get("leadership", {})
    active_coordinator = state.get("active_coordinator") or state.get("leader")
    print(f"**Leader**: {active_coordinator or 'VACANT (공석)'}")
    if leadership:
        print(f"**Leader Reason**: {leadership.get('reason') or '없음'}")
    print(f"**Members**: {', '.join(state.get('members', {}).keys()) or '없음'}")
    roles = state.get("role_assignments") or state.get("roles") or {}
    if roles:
        role_text = []
        for role, value in roles.items():
            peer = value.get("peer") if isinstance(value, dict) else value
            role_text.append(f"{role}={peer}")
        print(f"**Roles**: {', '.join(role_text)}")
    print(f"**Mission**: {state.get('mission') or '없음'}")
    print(f"**Blocked**: {state.get('blocked') or '없음'}")
    print(f"**Phase**: {state.get('phase') or '없음'}")
    print(f"**Updated**: {state.get('updated_at') or '없음'}")
    print(f"**Mailbox**: {unread_count} unread")
    task_path = _task_registry_path(ai_root)
    tasks = _read_json(task_path) if task_path.exists() else {}
    if tasks:
        active_tasks = [k for k, v in tasks.items() if isinstance(v, dict) and v.get("status") == "ACTIVE"]
        print(f"**Tasks**: {len(active_tasks)} active / {len(tasks)} total")
    lock_path = _file_locks_path(ai_root)
    locks = _read_json(lock_path) if lock_path.exists() else {}
    if locks:
        print(f"**Locks**: {len(locks)} active")
    
    consensus_dir = ai_root / "consensus"
    if consensus_dir.exists():
        active = []
        for f in sorted(consensus_dir.glob("*.json")):
            r = _read_json(f)
            if r.get("status") == "voting":
                active.append(f"  - {r['round_id']}: {r.get('subject','?')} [{sum(1 for v in r['votes'].values() if v is not None)}/{len(r['voters'])}]")
        if active:
            print("\n### [CONSENSUS — ACTIVE]")
            print("\n".join(active))

    room_id = state.get("room_id")
    if room_id:
        handoff_path = ai_root / "sessions" / room_id / "handoff.md"
        if handoff_path.exists():
            print("\n### [HANDOFF]")
            print(handoff_path.read_text(encoding="utf-8"))


def action_check_gate(ai_root: Path, agent: str) -> None:
    peers = _load_peers()
    gate = None
    # agent는 node_id(gc) 또는 peer_id(gemini) 둘 다 허용
    for peer_id, peer_cfg in peers.items():
        if peer_id == agent or peer_cfg.get("sys_subdir") == agent:
            gate = peer_cfg.get("gate")
            break
    if gate:
        sys_dir = Path(__file__).parent.parent
        status_path = sys_dir / gate["status_file"]
        if status_path.exists():
            data = _read_json(status_path)
            if data.get(gate["mode_key"]) == gate["mode_on_value"]:
                print(f"[GATE] {agent}=ON"); sys.exit(0)
        print(f"[GATE] {agent}=OFF"); sys.exit(1)
    print(f"[GATE] {agent}=ON"); sys.exit(0)


# ─────────────────────────────────────────────────────────────
# ask 액션
# ─────────────────────────────────────────────────────────────

def _decode_output(data: bytes) -> str:
    if not data:
        return ""
    
    # 1. BOM Check
    if data.startswith(b'\xff\xfe'): # UTF-16-LE BOM
        return data[2:].decode("utf-16-le", errors="replace").replace("\r\n", "\n")
    if data.startswith(b'\xfe\xff'): # UTF-16-BE BOM
        return data[2:].decode("utf-16-be", errors="replace").replace("\r\n", "\n")
    if data.startswith(b'\xef\xbb\xbf'): # UTF-8 BOM
        return data[3:].decode("utf-8", errors="replace").replace("\r\n", "\n")

    # 2. Heuristic for UTF-16 if null bytes are present (common in Windows pipes)
    if b'\x00' in data:
        try:
            # decode as utf-16-le and remove any residual nulls
            return data.decode("utf-16-le").replace("\x00", "").replace("\r\n", "\n")
        except UnicodeDecodeError:
            try:
                return data.decode("utf-16-be").replace("\x00", "").replace("\r\n", "\n")
            except UnicodeDecodeError:
                pass
            
    # 3. Standard encodings
    for enc in ["utf-8", "cp949"]:
        try:
            return data.decode(enc).replace("\r\n", "\n")
        except UnicodeDecodeError:
            continue
            
    # 4. Fallback
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n")


def _classify_ask_failure(text: str) -> tuple[str, dict]:
    lower = text.lower()
    policy = _load_lifecycle_policy().get("ask_failure_classification", {})
    for rule in policy.get("patterns", []):
        needles = [str(x).lower() for x in rule.get("match_any", [])]
        if any(needle in lower for needle in needles):
            extra = dict(rule.get("availability", {}))
            retry_marker = str(rule.get("capture_retry_hint_when_contains", "")).lower()
            if retry_marker and retry_marker in lower:
                extra["retry_hint"] = text.strip().splitlines()[0][:200]
            return rule.get("reason", "nonzero_exit"), extra
    return policy.get("default_reason", "nonzero_exit"), {}


def _read_peer_health(peer_id: str) -> tuple[Path, dict]:
    health_path = _peer_sys_dir(peer_id) / "health.json"
    data = _read_json(health_path) if health_path.exists() else {}
    data.setdefault("_version", "1.0")
    data.setdefault("peer_id", peer_id)
    data.setdefault("context_health", {})
    data.setdefault("session_health", {})
    data.setdefault("availability", {})
    return health_path, data


def _write_peer_health(peer_id: str, data: dict, ai_root: Path | None) -> None:
    health_path = _peer_sys_dir(peer_id) / "health.json"
    health_path.parent.mkdir(parents=True, exist_ok=True)
    lock_root = ai_root if ai_root else find_ai_root()
    with _get_lock(lock_root, f"health_{peer_id}"):
        health_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _ask_health_precheck(peer_id: str, ai_root: Path | None) -> None:
    if ai_root is None:
        return
    status, data = _peer_effective_health(peer_id)
    availability = data.get("availability", {})
    if status == "RED" or availability.get("gate_open") is False:
        reason = data.get("session_health", {}).get("last_failure_reason") or "health_gate_closed"
        print(f"[HUB:SKIP] {peer_id} health blocked | status={status} reason={reason}", file=sys.stderr)
        sys.exit(2)


def _record_ask_success(peer_id: str, elapsed: int, ai_root: Path | None) -> None:
    if ai_root is None:
        return
    _, data = _read_peer_health(peer_id)
    ctx = data.setdefault("context_health", {})
    previous_reason = data.get("session_health", {}).get("last_failure_reason")
    transient_red = set(_load_lifecycle_policy().get("health_lifecycle", {}).get(
        "transient_red_recovery_reasons",
        ["sandbox_spawn_eperm", "rate_or_session_limit", "cli_not_found"],
    ))
    if ctx.get("status") == "YELLOW" or (ctx.get("status") == "RED" and previous_reason in transient_red):
        ctx["status"] = "GREEN"
    ctx["checked_at"] = datetime.now().strftime("%Y%m%dT%H%M%S")
    sh = data.setdefault("session_health", {})
    today = datetime.now().strftime("%Y%m%d")
    if sh.get("session_date") != today:
        sh["session_count_today"] = 0
        sh["session_date"] = today
    sh["consecutive_failures"] = 0
    sh["last_failure_reason"] = None
    sh["last_success_at"] = _now()
    sh["session_count_today"] = int(sh.get("session_count_today", 0)) + 1
    availability = data.setdefault("availability", {})
    availability["gate_open"] = True
    availability["last_invocation_exit_code"] = 0
    availability["last_invocation_duration_ms"] = elapsed * 1000
    availability["rate_limit_state"] = "ok"
    availability.pop("sandbox_blocked", None)
    availability.pop("workspace_not_trusted", None)
    availability.pop("retry_hint", None)
    _write_peer_health(peer_id, data, ai_root)


def _record_ask_failure(
    peer_id: str,
    reason: str,
    detail: str,
    elapsed: int | None,
    ai_root: Path | None,
    extra: dict | None = None,
) -> None:
    if ai_root is None:
        return
    _, data = _read_peer_health(peer_id)
    sh = data.setdefault("session_health", {})
    failures = int(sh.get("consecutive_failures", 0)) + 1
    sh["consecutive_failures"] = failures
    sh["last_failure_reason"] = reason
    sh["last_failure_detail"] = detail.strip()[:500]
    sh["last_failure_at"] = _now()
    today = datetime.now().strftime("%Y%m%d")
    if sh.get("session_date") != today:
        sh["session_count_today"] = 0
        sh["session_date"] = today
    ctx = data.setdefault("context_health", {})
    lifecycle = _load_lifecycle_policy().get("health_lifecycle", {})
    critical_reasons = set(lifecycle.get("critical_reasons", ["sandbox_spawn_eperm", "rate_or_session_limit", "cli_not_found"]))
    failure_warn = int(lifecycle.get("failure_warn", 3))
    failure_error = int(lifecycle.get("failure_error", 5))
    if reason in critical_reasons or failures >= failure_error:
        ctx["status"] = "RED"
    elif failures >= failure_warn:
        ctx["status"] = "YELLOW"
    ctx["checked_at"] = datetime.now().strftime("%Y%m%dT%H%M%S")
    availability = data.setdefault("availability", {})
    availability["last_invocation_exit_code"] = 1
    if elapsed is not None:
        availability["last_invocation_duration_ms"] = elapsed * 1000
    if extra:
        availability.update(extra)
    if reason in critical_reasons:
        availability["gate_open"] = False
    _write_peer_health(peer_id, data, ai_root)


def _build_ask_query_with_context(ai_root: Path | None, query: str) -> str:
    if ai_root is None:
        return query
    state = _read_json(ai_root / "state.json")
    room_id = state.get("room_id")
    if not room_id:
        return query
    lines = [
        "[HUB CONTEXT]",
        f"Room ID: {room_id}",
        f"Members: {', '.join(state.get('members', {}).keys()) or 'none'}",
        f"Mission: {state.get('mission') or 'none'}",
        f"Blocked: {state.get('blocked') or 'none'}",
        f"Phase: {state.get('phase') or 'none'}",
    ]
    # ── User Directives 주입 (_sys/ai/user-directives.md) ────────
    directives_path = Path(__file__).parent.parent / "ai" / "user-directives.md"
    if directives_path.exists():
        directives = directives_path.read_text(encoding="utf-8", errors="replace").strip()
        if directives:
            lines.extend(["", "[USER DIRECTIVES]", directives])
    handoff_path = ai_root / "sessions" / room_id / "handoff.md"
    if handoff_path.exists():
        handoff = handoff_path.read_text(encoding="utf-8", errors="replace").strip()
        if handoff:
            lines.extend(["", "[HANDOFF]", handoff])
    lines.extend(["", "[USER QUERY]", query])
    return "\n".join(lines)


def _archive_text(ai_root: Path, category: str, name: str, content: str) -> Path:
    archive_dir = ai_root.parent / "_archive" / category
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = archive_dir / f"{stamp}_{name}"
    path.write_text(content, encoding="utf-8")
    return path


def _append_handoff_item(ai_root: Path, section: str, item: str) -> None:
    state = _read_json(ai_root / "state.json")
    room_id = state.get("room_id")
    if not room_id:
        return
    session_dir = ai_root / "sessions" / room_id
    session_dir.mkdir(parents=True, exist_ok=True)
    with _get_lock(ai_root, "handoff"):
        handoff = _read_handoff(session_dir)
        handoff.setdefault(section, []).append(item)
        _write_handoff(session_dir, handoff)


def _parse_compact_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y%m%dT%H%M%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(value)[:19], fmt)
        except ValueError:
            pass
    return None


def _peer_effective_health(peer_id: str, stale_minutes: int | None = None) -> tuple[str, dict]:
    if stale_minutes is None:
        stale_minutes = int(_load_protocol_cfg().get("leader_election", {}).get("health_stale_minutes", 120) or 120)
    _, data = _read_peer_health(peer_id)
    status = data.get("context_health", {}).get("status", "UNKNOWN")
    checked_at = data.get("context_health", {}).get("checked_at")
    checked_dt = _parse_compact_ts(checked_at)
    if checked_dt and (datetime.now() - checked_dt).total_seconds() > stale_minutes * 60:
        status = "STALE"
    if data.get("availability", {}).get("quarantined"):
        status = "RED"
    return status, data


def _healthy_peer(peer_id: str) -> bool:
    status, data = _peer_effective_health(peer_id)
    return status not in {"RED", "STALE"} and data.get("availability", {}).get("gate_open") is not False


def _role_guard(ai_root: Path, peer: str, action: str, allowed_roles: set[str], force_tier0: bool = False) -> None:
    if force_tier0 or not peer or peer == "unknown":
        return
    cfg = _load_protocol_cfg().get("leader_election", {}).get("role_enforcement", {})
    if not cfg.get("enabled", True):
        return
    state = _read_json(ai_root / "state.json")
    assignments = state.get("role_assignments") or {}
    if not assignments:
        return
    peer_roles = set()
    for role, info in assignments.items():
        if isinstance(info, dict) and info.get("peer") == peer and info.get("status") == "ACTIVE":
            peer_roles.add(role)
        elif isinstance(info, str) and info == peer:
            peer_roles.add(role)
    if not peer_roles:
        print(f"[HUB:BLOCK] peer {peer} has no active role for action {action}", file=sys.stderr)
        sys.exit(3)
    if peer_roles.isdisjoint(allowed_roles):
        print(f"[HUB:BLOCK] peer {peer} roles={','.join(sorted(peer_roles))} cannot perform {action}", file=sys.stderr)
        sys.exit(3)


def _matching_peers(needs: str, effort: str = "mid") -> list[dict]:
    proto_cfg = _load_protocol_cfg()
    election_cfg = proto_cfg.get("leader_election", {}).get("election_score", {})
    capability_registry = proto_cfg.get("workload", {}).get("capability_registry", {})
    role_registry = _load_orchestration().get("roles_registry", {})
    nodes = {
        node["node_id"]: node
        for node in _load_orchestration().get("hub_nodes", [])
        if node.get("enabled") is not False
    }
    tier_weight = {"low": 1, "mid": 2, "medium": 2, "high": 3}
    effort_weight = {"low": 1, "mid": 2, "medium": 2, "high": 3, "xhigh": 4, "max": 5}
    requested_effort = effort_weight.get(str(effort).lower(), 2)
    needs_lower = str(needs or "").lower()
    try:
        state = _read_json(find_ai_root() / "state.json")
    except Exception:
        state = {}
    active = state.get("active_coordinator") or state.get("leader")
    health_score_cfg = election_cfg.get("health_score", {})
    cost_penalty_cfg = election_cfg.get("cost_penalty", {})
    capability_max = int(election_cfg.get("capability_match_max", 10) or 10)
    continuity_bonus_max = int(election_cfg.get("continuity_bonus_max", 2) or 2)
    console_bonus_max = int(election_cfg.get("console_fit_bonus_max", 1) or 1)
    cold_start_penalty_max = int(election_cfg.get("cold_start_penalty_max", 1) or 1)
    matches: list[dict] = []
    for node_id, node_info in nodes.items():
        status, h_data = _peer_effective_health(node_id)
        if status == "RED":
            continue
        profile = h_data.get("profile", {})
        capabilities = list(profile.get("capabilities", []))
        capabilities.extend(capability_registry.get(node_id, []))
        for role, peers in role_registry.items():
            if node_id in peers:
                capabilities.append(role)
        aliases = [str(a).lower() for a in node_info.get("aliases", [])]
        if not needs_lower:
            capability_score = 1
        elif needs_lower == node_id.lower() or needs_lower in aliases:
            capability_score = capability_max
        else:
            cap_scores = []
            for cap in capabilities:
                cap_lower = str(cap).lower()
                if cap_lower == needs_lower:
                    cap_scores.append(capability_max)
                elif needs_lower in cap_lower or cap_lower in needs_lower:
                    cap_scores.append(max(1, capability_max - 3))
            capability_score = max(cap_scores) if cap_scores else 0
        matched = (
            not needs_lower
            or needs_lower == node_id.lower()
            or needs_lower in aliases
            or capability_score > 0
        )
        if not matched:
            continue
        cost_tier = str(profile.get("cost_tier", "mid")).lower()
        model_tier = str(profile.get("tier", "mid")).lower()
        if requested_effort >= 3 and tier_weight.get(model_tier, 2) < 2:
            continue
        raw_health_score = health_score_cfg.get(status, 0)
        health_score = -999 if raw_health_score == "blocked" else int(raw_health_score or 0)
        continuity_bonus = continuity_bonus_max if node_id == active and status not in {"RED", "STALE"} else 0
        recommended = proto_cfg.get("leader_election", {}).get("recommended_console_by_task", {})
        console_bonus = console_bonus_max if recommended.get(needs_lower) == node_id else 0
        cost_penalty = int(cost_penalty_cfg.get(cost_tier, 1) or 0)
        session_count = h_data.get("session_health", {}).get("session_count_today")
        cold_start_penalty = cold_start_penalty_max if session_count == 0 else 0
        score = capability_score + health_score + continuity_bonus + console_bonus - cost_penalty - cold_start_penalty
        matches.append({
            "node_id": node_id,
            "status": status,
            "cost_tier": cost_tier,
            "model_tier": model_tier,
            "capabilities": sorted(set(str(c) for c in capabilities)),
            "score": score,
        })
    matches.sort(key=lambda x: (x["score"], x["status"] == "GREEN", -tier_weight.get(x["cost_tier"], 2)), reverse=True)
    return matches


def _new_member_sids(members: dict) -> dict:
    return {agent: _short_id(agent[:1]) for agent in members.keys()}


def action_peer_quarantine(ai_root: Path, peer_id: str, reason: str) -> None:
    _, data = _read_peer_health(peer_id)
    data.setdefault("context_health", {})["status"] = "RED"
    data["context_health"]["checked_at"] = datetime.now().strftime("%Y%m%dT%H%M%S")
    sh = data.setdefault("session_health", {})
    sh["last_failure_reason"] = reason or "manual_quarantine"
    sh["last_failure_at"] = _now()
    availability = data.setdefault("availability", {})
    availability["gate_open"] = False
    availability["quarantined"] = True
    _write_peer_health(peer_id, data, ai_root)
    _append_handoff_item(ai_root, "PENDING_ISSUES", f"{_now()} {peer_id}: quarantined ({reason or 'manual'})")
    print(f"[HUB] PEER-QUARANTINE {peer_id} | reason={reason or 'manual'}")


def action_peer_recover(ai_root: Path, peer_id: str, reason: str) -> None:
    _, data = _read_peer_health(peer_id)
    data.setdefault("context_health", {})["status"] = "GREEN"
    data["context_health"]["checked_at"] = datetime.now().strftime("%Y%m%dT%H%M%S")
    sh = data.setdefault("session_health", {})
    sh["consecutive_failures"] = 0
    sh["last_failure_reason"] = None
    sh["last_success_at"] = _now()
    availability = data.setdefault("availability", {})
    availability["gate_open"] = True
    availability["quarantined"] = False
    availability["rate_limit_state"] = "ok"
    availability.pop("sandbox_blocked", None)
    availability.pop("workspace_not_trusted", None)
    availability.pop("retry_hint", None)
    _write_peer_health(peer_id, data, ai_root)
    _append_handoff_item(ai_root, "RECENT_COMPLETED", f"{_now()} {peer_id}: recovered ({reason or 'manual'})")
    print(f"[HUB] PEER-RECOVER {peer_id} | reason={reason or 'manual'}")


def action_new_topic(ai_root: Path, subject: str) -> None:
    policy = _load_lifecycle_policy().get("room_lifecycle", {}).get("new_topic", {})
    state = _read_json(ai_root / "state.json")
    old_room = state.get("room_id")
    old_members = state.get("members", {})
    carried = {s: [] for s in _HANDOFF_SECTIONS}
    if old_room:
        old_dir = ai_root / "sessions" / old_room
        old_handoff_path = old_dir / "handoff.md"
        if old_handoff_path.exists():
            old_text = old_handoff_path.read_text(encoding="utf-8")
            if policy.get("archive_current_handoff", True):
                _archive_text(ai_root, "rooms", f"{old_room}_handoff.md", old_text)
            old_sections = _parse_handoff(old_text)
            for sec in policy.get("carry_sections", ["KEY_DECISIONS"]):
                carried[sec] = old_sections.get(sec, [])
    new_room = _short_id("room-")
    carried["GOAL"] = [subject or "new topic"]
    carried["ACTIVE_THREADS"] = [f"{_now()} system: new topic from {old_room or 'none'}"]
    with _get_lock(ai_root, "state"):
        state["room_id"] = new_room
        state["members"] = _new_member_sids(old_members)
        state["mission"] = subject or None
        state["blocked"] = None
        state["phase"] = "new-topic"
        state["updated_at"] = _now()
        _write_state(ai_root, state)
    new_dir = ai_root / "sessions" / new_room
    new_dir.mkdir(parents=True, exist_ok=True)
    _write_handoff(new_dir, carried)
    # Clear peer sessions on topic change (old scope_key = old room no longer valid)
    for pid in ("cx", "gc", "cc"):
        _clear_peer_sessions(pid, f"new-topic:{new_room}", ai_root)
    print(f"[HUB] NEW-TOPIC {new_room} | from={old_room or 'none'} | subject={subject}")


def action_clear_room(ai_root: Path, subject: str) -> None:
    policy = _load_lifecycle_policy().get("room_lifecycle", {}).get("clear_room", {})
    state = _read_json(ai_root / "state.json")
    old_room = state.get("room_id")
    old_members = state.get("members", {})
    mailbox_path = ai_root / "mailbox.json"
    if policy.get("archive_mailbox", True) and mailbox_path.exists():
        _archive_text(ai_root, "mailbox", f"{old_room or 'no-room'}_mailbox.json", mailbox_path.read_text(encoding="utf-8"))
    with _get_lock(ai_root, "mailbox"):
        _write_json(mailbox_path, {"messages": [], "unread_count": 0})
        _gc_unreferenced_payloads(ai_root, [])
    new_room = _short_id("room-")
    sections = {s: [] for s in _HANDOFF_SECTIONS}
    sections["GOAL"] = [subject or "cleared room"]
    sections["ACTIVE_THREADS"] = [f"{_now()} system: clear-room from {old_room or 'none'}"]
    with _get_lock(ai_root, "state"):
        state["room_id"] = new_room
        state["members"] = _new_member_sids(old_members)
        state["mission"] = subject or None
        state["blocked"] = None
        state["phase"] = "clear-room"
        state["updated_at"] = _now()
        _write_state(ai_root, state)
    new_dir = ai_root / "sessions" / new_room
    new_dir.mkdir(parents=True, exist_ok=True)
    _write_handoff(new_dir, sections)
    for pid in ("cx", "gc", "cc"):
        _clear_peer_sessions(pid, f"clear-room:{new_room}", ai_root)
    print(f"[HUB] CLEAR-ROOM {new_room} | from={old_room or 'none'} | subject={subject}")


def _ask_with_pty(cmd: list[str], node_id: str, timeout_sec: int, process_env: dict, quiet: bool = False) -> tuple[str, int]:
    """pywinpty로 pseudo-TTY 실행 — WriteConsole() API 우회 (agy 등 TUI CLI 전용)."""
    try:
        import winpty as _winpty
    except ImportError:
        print(f"[HUB:ERROR] pywinpty not installed (required for {node_id})", file=sys.stderr)
        sys.exit(1)

    p = _winpty.PtyProcess.spawn(cmd, env=process_env)
    chunks: list[str] = []
    lease = int(_runtime_cfg().get("pty_lease_sec", 300) or 300)
    deadline = time.monotonic() + (timeout_sec if timeout_sec > 0 else lease)
    t0 = time.monotonic()

    while time.monotonic() < deadline:
        try:
            chunk = p.read(4096)
            if chunk:
                chunks.append(chunk)
        except EOFError:
            break

    try:
        p.close()
    except Exception:
        pass

    elapsed = int(time.monotonic() - t0)
    output = _strip_ansi("".join(chunks))
    if not quiet:
        print(f"[HUB] REPLY {node_id} | chars={len(output)} | elapsed={elapsed}s\n{output.strip()}")
    return output, elapsed


def _append_ask_history(ai_root: Path | None, peer_id: str, query_file_path: str | None, output_file: str | None, elapsed_sec: int | None, success: bool, failure_reason: str | None) -> None:
    """Append a provenance record to .ai/ask_history.jsonl."""
    if not ai_root:
        return
    try:
        h = _read_json(ai_root / "state.json")
        coordinator = h.get("active_coordinator", "unknown")
        peers_data = _load_peers()
        peer_cfg = peers_data.get(peer_id, {})
        subdir = peer_cfg.get("sys_subdir", peer_id)
        health_path = Path(__file__).parent.parent / subdir / "health.json"
        health_state = "unknown"
        if health_path.exists():
            health_state = _read_json(health_path).get("context_health", {}).get("status", "unknown")
        entry = {
            "ts": _now(),
            "peer_id": peer_id,
            "profile_id": _resolve_profile_id(peer_id),
            "query_file": query_file_path,
            "output_file": output_file,
            "elapsed_sec": elapsed_sec,
            "health_state_at_ask": health_state,
            "success": success,
            "failure_reason": failure_reason,
        }
        log_path = ai_root / "ask_history.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# Session State Management
# ─────────────────────────────────────────────────────────────

def _session_state_path(peer_id: str) -> Path:
    return _peer_sys_dir(peer_id) / "session_state.json"


def _load_session_state(peer_id: str) -> dict:
    path = _session_state_path(peer_id)
    if path.exists():
        return _read_json(path)
    return {"_version": "1.0", "peer_id": peer_id, "active": {}, "history": []}


def _save_session_state(peer_id: str, data: dict, ai_root: Path | None = None) -> None:
    path = _session_state_path(peer_id)
    lock_root = ai_root if ai_root else find_ai_root()
    with _get_lock(lock_root, f"ss_{peer_id}"):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_active_session(peer_id: str, scope_key: str) -> dict | None:
    entry = _load_session_state(peer_id).get("active", {}).get(scope_key)
    return entry if entry and entry.get("status") == "active" else None


def _set_active_session(peer_id: str, scope_key: str, session_id: str, ask_id: str, ai_root: Path | None = None) -> None:
    data = _load_session_state(peer_id)
    existing = data.get("active", {}).get(scope_key, {})
    data.setdefault("active", {})[scope_key] = {
        "session_id": session_id,
        "scope_key": scope_key,
        "created_at": existing.get("created_at") or _now(),
        "last_used_at": _now(),
        "last_ask_id": ask_id,
        "status": "active",
    }
    _save_session_state(peer_id, data, ai_root)


def _retire_session(peer_id: str, scope_key: str, reason: str, ai_root: Path | None = None) -> None:
    data = _load_session_state(peer_id)
    entry = data.get("active", {}).pop(scope_key, None)
    if entry:
        entry["status"] = "retired"
        entry["retired_at"] = _now()
        entry["retire_reason"] = reason
        hist = data.setdefault("history", [])
        hist.append(entry)
        data["history"] = hist[-50:]
        _save_session_state(peer_id, data, ai_root)


def _clear_peer_sessions(peer_id: str, reason: str, ai_root: Path | None = None) -> None:
    data = _load_session_state(peer_id)
    for scope_key in list(data.get("active", {}).keys()):
        _retire_session(peer_id, scope_key, reason, ai_root)


def _extract_jsonl_thread_id(raw: str) -> str | None:
    """codex --json JSONL에서 thread.started 이벤트의 thread_id 추출."""
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if obj.get("type") == "thread.started":
                tid = obj.get("thread_id")
                if tid:
                    return str(tid)
        except json.JSONDecodeError:
            continue
    return None


def _compute_scope_key(ai_root: Path | None, explicit_scope: str | None = None) -> str:
    """세션 스코프 키: explicit_scope > room_id > 'default'."""
    if explicit_scope:
        return explicit_scope
    if ai_root:
        room_id = _read_json(ai_root / "state.json").get("room_id")
        if room_id:
            return room_id
    return "default"


def _build_session_cmd(health_peer: str, session_id: str | None, exe: str) -> tuple[list[str], bool, str | None]:
    """세션 재사용/신규 생성 명령 반환. (cmd_args, use_stdin, gc_new_session_id)"""
    _CX_BASE = ["-s", "workspace-write", "--json", "--ignore-rules"]
    if health_peer == "cx":
        if session_id:
            return ["exec", "resume", session_id, "-"] + _CX_BASE, True, None
        return ["exec", "-"] + _CX_BASE, True, None
    if health_peer == "gc":
        if session_id:
            return ["--resume", session_id, "-p", "-", "-o", "text", "--approval-mode", "auto_edit", "--skip-trust"], True, None
        new_uuid = str(uuid.uuid4())
        return ["--session-id", new_uuid, "-p", "-", "-o", "text", "--approval-mode", "auto_edit", "--skip-trust"], True, new_uuid
    return [], False, None


def action_ask(to: str, query: str, query_file: str | None, timeout_sec: int, ai_root: Path | None, quiet: bool = False, output_file: str | None = None, include_context: bool = True, session_policy: str = "auto", explicit_scope: str | None = None) -> None:
    saved_query_file_path = query_file
    if query_file:
        qf = Path(query_file)
        if not qf.exists(): sys.exit(1)
        query = qf.read_text(encoding="utf-8")
        qf.unlink()

    nodes = _load_nodes(ai_root) if ai_root else _default_nodes()["nodes"]
    disabled_nodes = {
        entry.get("node_id")
        for entry in _load_orchestration().get("hub_nodes", [])
        if entry.get("enabled") is False and entry.get("node_id")
    }
    if to not in nodes:
        for nid, ncfg in nodes.items():
            if to in ncfg.get("aliases", []):
                to = nid
                break
    if to in disabled_nodes:
        print(f"[ERROR] ask target disabled by default: {to}", file=sys.stderr)
        sys.exit(1)
    node = nodes.get(to, {})
    if not node:
        print(f"[ERROR] unknown ask target: {to}", file=sys.stderr)
        sys.exit(1)
    exe_name = node.get("invoke", to)
    raw_args = node.get("invoke_args", ["-p", "{query}"])
    requires_pty = node.get("requires_pty", False)
    health_peer = node.get("peer") or to

    if not timeout_sec or timeout_sec <= 0:
        try:
            if requires_pty:
                timeout_sec = int(_runtime_cfg().get("pty_lease_sec", 300) or 300)
            else:
                timeout_sec = 0  # unlimited; heartbeat loop monitors for dead processes
        except Exception:
            timeout_sec = 0

    _lease_sweep(ai_root)
    _ask_health_precheck(health_peer, ai_root)
    if include_context:
        query = _build_ask_query_with_context(ai_root, query)

    # ── Session reuse ──────────────────────────────────────────
    session_mode = node.get("session_mode", "none")
    # session_policy arg overrides node config; "auto" means use node config
    effective_policy = session_policy if session_policy != "auto" else session_mode
    use_session = effective_policy in ("auto", "reuse") and health_peer in ("cx", "gc") and not requires_pty
    scope_key: str | None = None
    existing_session: dict | None = None
    gc_new_session_id: str | None = None

    if use_session:
        scope_key = _compute_scope_key(ai_root, explicit_scope)
        existing_session = _get_active_session(health_peer, scope_key)

    # ── Command construction ───────────────────────────────────
    cmd_args: list[str] = []
    use_stdin = False

    if use_session:
        session_id = existing_session["session_id"] if existing_session else None
        cmd_args, use_stdin, gc_new_session_id = _build_session_cmd(health_peer, session_id, exe_name)
        is_resume_attempt = session_id is not None
    else:
        is_resume_attempt = False
        for arg in raw_args:
            if "{query}" in arg:
                if requires_pty:
                    cmd_args.append(arg.replace("{query}", query))
                else:
                    cmd_args.append(arg.replace("{query}", "-"))
                    use_stdin = True
            else:
                cmd_args.append(arg)

    exe = shutil.which(exe_name)
    if not exe:
        print(f"[ERROR] {exe_name} CLI not found in PATH", file=sys.stderr)
        _record_ask_failure(health_peer, "cli_not_found", f"{exe_name} CLI not found in PATH", None, ai_root)
        sys.exit(1)

    cmd = [exe] + cmd_args

    # ── Environment Variable Injection ─────────────────────────
    process_env = {**os.environ, "PYTHONUTF8": "1"}
    peers = _load_peers()
    target_peer_id = None
    target_peer_cfg = None
    mapped_peer = _node_to_peer_map().get(to, to)
    if mapped_peer in peers:
        target_peer_id = mapped_peer
        target_peer_cfg = peers[mapped_peer]
    else:
        for pid, pcfg in peers.items():
            native = pcfg.get("native_binary")
            if native and native.get("bin_name") == exe_name:
                target_peer_id = pid
                target_peer_cfg = pcfg
                break
            if pcfg.get("npm_package") and (to in pid or pid in to):
                target_peer_id = pid
                target_peer_cfg = pcfg
                break
    if target_peer_cfg:
        sys_dir = Path(__file__).parent.parent
        peer_subdir = sys_dir / target_peer_cfg.get("sys_subdir", target_peer_id)
        for k, rel in target_peer_cfg.get("env_vars", {}).items():
            if isinstance(rel, bool):
                process_env[k] = "true" if rel else "false"
            elif isinstance(rel, str) and rel.lower() in ("true", "false"):
                process_env[k] = rel.lower()
            else:
                process_env[k] = str((peer_subdir / rel).resolve())

    # ── PTY path ───────────────────────────────────────────────
    if requires_pty and sys.platform == "win32":
        output, elapsed = _ask_with_pty(cmd, to, timeout_sec, process_env, quiet)
        _record_ask_success(health_peer, elapsed, ai_root)
        _append_ask_history(ai_root, to, saved_query_file_path, output_file, elapsed, True, None)
        if ai_root:
            _record_routing_metric(ai_root, "direct_ask", selected_peer=to, profile_id=_resolve_profile_id(to), outcome="success", latency_sec=elapsed)
        if output_file:
            try:
                base = ai_root if ai_root else Path.cwd()
                out_path = _portable_state_path(base, output_file)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(output, encoding="utf-8")
                if not quiet:
                    print(f"[HUB] REPLY {to} | chars={len(output)} | elapsed={elapsed}s | output={out_path}")
            except Exception as e:
                print(f"[HUB:ERROR] failed to write output file: {e}", file=sys.stderr)
                sys.exit(1)
        elif quiet:
            print(output, end="")
        return

    # ── Subprocess path (with optional session-retry) ──────────
    heartbeat_sec, lease_timeout_sec = _lease_cfg()
    ask_id = _short_id("ask-")
    lease_status = "open"
    t0 = time.monotonic()
    proc = None  # ensure defined for finally

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if use_stdin else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=process_env,
        )
        _lease_open(ai_root, to, proc.pid, lease_timeout_sec, ask_id=ask_id, ask_query_file=saved_query_file_path)

        input_bytes = query.encode("utf-8") if use_stdin else None
        deadline = time.monotonic() + (timeout_sec if timeout_sec > 0 else float("inf"))
        raw_out = b""
        raw_err = b""

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                lease_status = "timeout"
                _kill_process_tree(proc)
                raise subprocess.TimeoutExpired(cmd, timeout_sec)
            try:
                raw_out, raw_err = proc.communicate(input=input_bytes, timeout=min(heartbeat_sec, remaining))
                break
            except subprocess.TimeoutExpired:
                input_bytes = None
                if proc.poll() is not None:
                    raw_out = proc.stdout.read() if proc.stdout else b""
                    raw_err = proc.stderr.read() if proc.stderr else b""
                    break
                _lease_renew(ai_root, to, lease_timeout_sec)

        elapsed = int(time.monotonic() - t0)
        lease_status = "closed"
        raw_text = _strip_ansi(_decode_output(raw_out))

        # JSONL 처리: session-aware cx OR 원래 --json 노드
        uses_json = use_session and health_peer == "cx" or (node.get("invoke_args") and "--json" in node.get("invoke_args", []))
        output = _extract_jsonl_text(raw_text, to, ai_root) if uses_json else raw_text

        # ── Session resume failure → fallback to fresh ─────────
        if proc.returncode != 0 and is_resume_attempt and scope_key:
            clean_err_r = _strip_ansi(_decode_output(raw_err))
            print(f"[HUB:WARN] {to} session resume failed (exit={proc.returncode}), retrying fresh", file=sys.stderr)
            _retire_session(health_peer, scope_key, "resume_failed", ai_root)
            _lease_close(ai_root, to, proc.pid, "retry")

            fresh_args, _, gc_new_session_id = _build_session_cmd(health_peer, None, exe_name)
            fresh_cmd = [exe] + fresh_args
            proc = subprocess.Popen(fresh_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=process_env)
            _lease_open(ai_root, to, proc.pid, lease_timeout_sec, ask_id=ask_id + "-r")
            t1 = time.monotonic()
            try:
                raw_out, raw_err = proc.communicate(input=query.encode("utf-8"), timeout=timeout_sec if timeout_sec > 0 else None)
            except subprocess.TimeoutExpired:
                _kill_process_tree(proc)
                raise
            elapsed = int(time.monotonic() - t0)
            raw_text = _strip_ansi(_decode_output(raw_out))
            output = _extract_jsonl_text(raw_text, to, ai_root) if health_peer == "cx" else raw_text
            is_resume_attempt = False
            if proc.returncode == 0:
                _record_ask_success(health_peer, elapsed, ai_root)
                _append_ask_history(ai_root, to, saved_query_file_path, output_file, elapsed, True, None)
                _record_routing_metric(ai_root, "direct_ask", selected_peer=to, profile_id=_resolve_profile_id(to), outcome="success", latency_sec=elapsed) if ai_root else None
                if use_session and scope_key:
                    if health_peer == "cx":
                        tid = _extract_jsonl_thread_id(raw_text)
                        if tid:
                            _set_active_session(health_peer, scope_key, tid, ask_id + "-r", ai_root)
                    elif health_peer == "gc" and gc_new_session_id:
                        _set_active_session(health_peer, scope_key, gc_new_session_id, ask_id + "-r", ai_root)
            else:
                clean_err = _strip_ansi(_decode_output(raw_err))
                reason, extra = _classify_ask_failure(clean_err + "\n" + output)
                extra["session_recovered"] = False
                lease_status = "failed"
                _record_ask_failure(health_peer, reason, clean_err or output, elapsed, ai_root, extra)
                _append_ask_history(ai_root, to, saved_query_file_path, output_file, elapsed, False, reason)
                print(f"[HUB:ERROR] {to} exited {proc.returncode}\n{clean_err}", file=sys.stderr)
                sys.exit(1)

        elif proc.returncode != 0:
            clean_err = _strip_ansi(_decode_output(raw_err))
            reason, extra = _classify_ask_failure(clean_err + "\n" + output)
            lease_status = "failed"
            _record_ask_failure(health_peer, reason, clean_err or output, elapsed, ai_root, extra)
            _append_ask_history(ai_root, to, saved_query_file_path, output_file, elapsed, False, reason)
            if ai_root:
                _record_routing_metric(ai_root, "direct_ask", selected_peer=to, profile_id=_resolve_profile_id(to), outcome="failure", latency_sec=elapsed, failure_reason=reason)
            print(f"[HUB:ERROR] {to} exited {proc.returncode}\n{clean_err}", file=sys.stderr)
            sys.exit(1)
        else:
            _record_ask_success(health_peer, elapsed, ai_root)
            _append_ask_history(ai_root, to, saved_query_file_path, output_file, elapsed, True, None)
            if ai_root:
                _record_routing_metric(ai_root, "direct_ask", selected_peer=to, profile_id=_resolve_profile_id(to), outcome="success", latency_sec=elapsed)

            # ── Session state update on success ─────────────────
            if use_session and scope_key and proc.returncode == 0:
                if health_peer == "cx":
                    thread_id = _extract_jsonl_thread_id(raw_text)
                    if thread_id:
                        _set_active_session(health_peer, scope_key, thread_id, ask_id, ai_root)
                        _log_p2p("SESSION", f"cx thread stored scope={scope_key} id={thread_id[:8]}...", to_node="cx")
                elif health_peer == "gc":
                    sid = gc_new_session_id or (existing_session or {}).get("session_id")
                    if sid:
                        _set_active_session(health_peer, scope_key, sid, ask_id, ai_root)
                        _log_p2p("SESSION", f"gc session stored scope={scope_key} id={sid[:8]}...", to_node="gc")

        if output_file:
            try:
                base = ai_root if ai_root else Path.cwd()
                out_path = _portable_state_path(base, output_file)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(output, encoding="utf-8")
                if not quiet:
                    print(f"[HUB] REPLY {to} | chars={len(output)} | elapsed={elapsed}s | output={out_path}")
            except Exception as e:
                print(f"[HUB:ERROR] failed to write output file: {e}", file=sys.stderr)
                sys.exit(1)
        elif quiet:
            print(output, end="")
        else:
            print(f"[HUB] REPLY {to} | chars={len(output)} | elapsed={elapsed}s\n{output.strip()}")
    except subprocess.TimeoutExpired:
        elapsed = int(time.monotonic() - t0)
        lease_status = "timeout"
        detail = f"ask timeout after {timeout_sec}s"
        _record_ask_failure(health_peer, "timeout", detail, timeout_sec, ai_root)
        _append_ask_history(ai_root, to, saved_query_file_path, output_file, timeout_sec, False, "timeout")
        if ai_root:
            _record_routing_metric(ai_root, "direct_ask", selected_peer=to, profile_id=_resolve_profile_id(to), outcome="failure", latency_sec=timeout_sec, failure_reason="timeout")
        print(f"[HUB:ERROR] {detail}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        elapsed = int(time.monotonic() - t0)
        lease_status = "failed"
        reason, extra = _classify_ask_failure(str(e))
        _record_ask_failure(health_peer, reason, str(e), None, ai_root, extra)
        _append_ask_history(ai_root, to, saved_query_file_path, output_file, None, False, reason)
        if ai_root:
            _record_routing_metric(ai_root, "direct_ask", selected_peer=to, profile_id=_resolve_profile_id(to), outcome="failure", latency_sec=None, failure_reason=reason)
        print(f"[HUB:ERROR] ask 실패: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        pid = proc.pid if proc is not None else -1
        _lease_close(ai_root, to, pid, lease_status)


def _read_query_arg(query: str, query_file: str | None) -> str:
    if query_file:
        qf = Path(query_file)
        if not qf.exists():
            sys.exit(1)
        text = qf.read_text(encoding="utf-8")
        qf.unlink()
        return text
    return query or ""


def _thin_forward_envelope(ai_root: Path, query: str, coordinator: str, from_peer: str) -> str:
    state = _read_json(ai_root / "state.json")
    room_id = state.get("room_id") or "none"
    cfg = _load_protocol_cfg().get("leader_election", {}).get("forwarding_contract", {})
    max_chars = int(cfg.get("max_forward_chars", 800) or 800)
    refs = [str(ref).replace("{room_id}", room_id) for ref in cfg.get("preferred_refs", [])]
    roles = state.get("roles") or {}
    meta = "\n".join([
        f"ROOM: {room_id}",
        f"FROM: {from_peer or 'unknown'}",
        f"ACTIVE_COORDINATOR: {coordinator}",
        "FORWARDING: thin_envelope; single_hop=true; no_credentials=true",
        "STATE_REFS:",
        *[f"- {ref}" for ref in refs],
        f"ROLES: {json.dumps(roles, ensure_ascii=False)}",
        "REQUEST: coordinate using state refs; do not require full chat history.",
    ])
    if len(meta) > max_chars:
        meta = meta[: max_chars - 20] + "\n...[truncated]"
    return f"{meta}\n\nUSER_QUERY:\n{query}"


def action_ask_coordinator(ai_root: Path, query: str, query_file: str | None, timeout_sec: int, from_peer: str, quiet: bool = False, output_file: str | None = None) -> None:
    query_text = _read_query_arg(query, query_file)
    state = _read_json(ai_root / "state.json")
    coordinator = state.get("active_coordinator") or state.get("leader")
    if not coordinator:
        coordinator = _load_orchestration().get("consensus", {}).get("default_proposer", "cc")
    if not _healthy_peer(coordinator):
        print(f"[HUB:ERROR] active coordinator {coordinator} is not healthy", file=sys.stderr)
        sys.exit(2)
    if "ask-coordinator" in query_text.lower():
        print("[HUB:ERROR] nested ask-coordinator forwarding is not allowed", file=sys.stderr)
        sys.exit(1)
    envelope = _thin_forward_envelope(ai_root, query_text, coordinator, from_peer)
    _record_routing_metric(ai_root, "ask_coordinator", from_peer=from_peer, coordinator=coordinator, query_chars=len(query_text), envelope_chars=len(envelope))
    action_ask(coordinator, envelope, None, timeout_sec, ai_root, quiet=quiet, output_file=output_file, include_context=False)


# ─────────────────────────────────────────────────────────────
# Consensus 프로토콜
# ─────────────────────────────────────────────────────────────

def action_consensus_propose(ai_root: Path, subject: str, voters: list[str], proposed_by: str) -> None:
    round_id = _short_id("r-")
    data = {"round_id": round_id, "subject": subject, "proposed_by": proposed_by, "proposed_at": _now(), 
            "status": "voting", "voters": voters, "votes": {v: None for v in voters}}
    _write_json(ai_root / "consensus" / f"{round_id}.json", data)
    _log_p2p("PROPOSE", f"ID={round_id} Subject='{subject}'", from_node=proposed_by)
    print(f"[HUB] PROPOSE {round_id} | subject={subject} | voters={','.join(voters)}")


def action_consensus_vote(ai_root: Path, round_id: str, voter: str, vote_val: str, reason: str) -> None:
    _VALID_VOTES = {"agree", "disagree", "abstain"}
    if vote_val not in _VALID_VOTES:
        print(f"[HUB:ERROR] invalid vote value '{vote_val}'; must be one of {sorted(_VALID_VOTES)}", file=sys.stderr)
        sys.exit(1)
    rpath = ai_root / "consensus" / f"{round_id}.json"
    if not rpath.exists(): sys.exit(1)
    with _get_lock(ai_root, f"consensus_{round_id}"):
        data = _read_json(rpath)
        if data.get("status") in ("finalized", "escalated"):
            print(f"[HUB:ERR] round {round_id} is already closed", file=sys.stderr)
            sys.exit(1)
        if voter not in data.get("voters", []):
            print(f"[HUB:ERR] {voter} is not a registered voter for {round_id}", file=sys.stderr)
            sys.exit(1)
        votes = data.get("votes", {})
        votes[voter] = {"vote": vote_val, "reason": reason, "ts": _now()}
        data["votes"] = votes
        total, cast = len(data["voters"]), sum(1 for v in votes.values() if v is not None)
        
        _log_p2p("VOTE", f"ID={round_id} Vote={vote_val} ({cast}/{total})", from_node=voter)
        print(f"[HUB] VOTE {round_id} | voter={voter} {vote_val} | {cast}/{total}")
        
        if cast == total:
            has_disagree = any(v["vote"] == "disagree" for v in votes.values())
            all_agree = all(v["vote"] == "agree" for v in votes.values())
            if has_disagree:
                data["status"] = "escalated"
                data["outcome"] = "human_gate"
            elif all_agree:
                data["status"] = "finalized"
                data["outcome"] = "unanimous"
            else:
                data["status"] = "finalized"
                data["outcome"] = "abstain"
            _write_json(rpath, data)
            _log_p2p("DECISION", f"ID={round_id} Status={data['status'].upper()} Outcome={data['outcome']}", from_node="SYSTEM")
            print(f"[HUB] DECISION {round_id} {data['status'].upper()} | {data['outcome']}")
            _append_consensus_history(ai_root, round_id, data["subject"], data["status"].upper())
        else: _write_json(rpath, data)


def _append_consensus_history(ai_root: Path, round_id: str, subject: str, outcome: str) -> None:
    state = _read_json(ai_root / "state.json")
    room_id = state.get("room_id")
    if not room_id: return
    session_dir = ai_root / "sessions" / room_id
    session_dir.mkdir(parents=True, exist_ok=True)
    handoff = _read_handoff(session_dir)
    handoff.setdefault("CONSENSUS_HISTORY", []).append(f"{round_id}: {subject} — {outcome} {_now()[:10]}")
    _write_handoff(session_dir, handoff)


def action_consensus_check(ai_root: Path, round_id: str | None) -> None:
    consensus_dir = ai_root / "consensus"
    if not consensus_dir.exists(): return
    files = [consensus_dir / f"{round_id}.json"] if round_id else sorted(consensus_dir.glob("*.json"))
    for f in files:
        if not f.exists(): continue
        r = _read_json(f)
        print(f"\n### [{r['round_id']}] {r['status'].upper()} - {r['subject']}")
        for v, d in r['votes'].items(): print(f"  - {v}: {d['vote'] if d else '(pending)'}")


def action_consensus_sweep(ai_root: Path, timeout_minutes: int = 30) -> None:
    """Auto-escalate stalled voting rounds older than timeout_minutes."""
    consensus_dir = ai_root / "consensus"
    if not consensus_dir.exists(): return
    now = datetime.now()
    swept = 0
    for f in sorted(consensus_dir.glob("*.json")):
        r = _read_json(f)
        if r.get("status") != "voting": continue
        proposed_at_str = r.get("proposed_at", "")
        try:
            proposed_at = datetime.fromisoformat(proposed_at_str)
            age_minutes = (now - proposed_at).total_seconds() / 60
        except Exception:
            age_minutes = 0
        if age_minutes >= timeout_minutes:
            with _get_lock(ai_root, f"consensus_{r['round_id']}"):
                r = _read_json(f)
                if r.get("status") != "voting": continue
                r["status"] = "escalated"
                r["outcome"] = "timeout"
                r["outcome_at"] = _now()
                _write_json(f, r)
            _log_p2p("DECISION", f"ID={r['round_id']} Status=ESCALATED Outcome=timeout (age={age_minutes:.0f}m)", from_node="SYSTEM")
            print(f"[HUB] SWEEP {r['round_id']} ESCALATED | timeout after {age_minutes:.0f}m | {r['subject'][:50]}")
            _append_consensus_history(ai_root, r["round_id"], r["subject"], "ESCALATED(timeout)")
            swept += 1
    if swept == 0:
        print(f"[HUB] SWEEP: no stalled rounds (timeout={timeout_minutes}m)")


# ─────────────────────────────────────────────────────────────
# 건강 관리 액션 (Protocol v4.0)
# ─────────────────────────────────────────────────────────────

def action_health_update(peer_id: str, status: str, jsonl_mb: float = 0.0, failures: int = 0, extra: dict | None = None, availability: dict | None = None) -> None:
    """피어 건강 파일 갱신 — 제로토큰, 로컬 파일만.

    availability 딕셔너리가 전달되면 health.json["availability"] 섹션도 병합 갱신.
    GREEN+failures=0 시 entrypoint_ok/authenticated 자동 반영 (cx 버그 픽스).
    """
    peer_dir = _peer_sys_dir(peer_id)
    health_path = peer_dir / "health.json"
    with _get_lock(peer_dir.parent.parent / ".ai", f"health_{peer_id}"):
        data: dict = {}
        if health_path.exists():
            try:
                data = json.loads(health_path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        cfg = _load_protocol_cfg()
        thresholds = cfg.get("health", {}).get("thresholds", {})
        peer_name = _node_to_peer_map().get(peer_id, peer_id)
        if peer_name not in thresholds:
            peer_name = peer_id
        th = thresholds.get(peer_name, {"green_mb": 0.6, "yellow_mb": 1.2})
        computed_status = str(status or "GREEN").upper()
        if computed_status == "AUTO":
            if jsonl_mb >= th["yellow_mb"]:
                computed_status = "RED"
            elif jsonl_mb >= th["green_mb"]:
                computed_status = "YELLOW"
            else:
                computed_status = "GREEN"
        ctx = data.setdefault("context_health", {})
        ctx["status"] = computed_status
        ctx["jsonl_mb"] = jsonl_mb
        ctx["checked_at"] = datetime.now().strftime("%Y%m%dT%H%M%S")
        ctx["source"] = "self"
        sh = data.setdefault("session_health", {})
        sh["consecutive_failures"] = failures
        today = datetime.now().strftime("%Y%m%d")
        if sh.get("session_date") != today:
            sh["session_count_today"] = 0
            sh["session_date"] = today
        if computed_status in ("GREEN", "YELLOW") and failures == 0:
            sh["last_success_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            sh["session_count_today"] = sh.get("session_count_today", 0) + 1
        if extra:
            ctx.update(extra)
        # availability 섹션 갱신: 명시적 dict 또는 GREEN 성공 시 자동 추론
        avail = data.setdefault("availability", {})
        if availability:
            avail.update(availability)
        elif computed_status == "GREEN" and failures == 0:
            # 성공적 실행 시 entrypoint_ok/authenticated 자동 true 설정
            avail["entrypoint_ok"] = True
            avail["authenticated"] = True
            avail["gate_open"] = True
        elif computed_status == "RED":
            avail["entrypoint_ok"] = False
            avail["gate_open"] = False
        elif computed_status == "YELLOW":
            avail.setdefault("gate_open", True)
        health_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _log_p2p("HEALTH", f"peer={peer_id} status={computed_status} jsonl={jsonl_mb:.2f}MB failures={failures}")
    print(f"[HUB] HEALTH-UPDATE {peer_id} | status={computed_status} jsonl={jsonl_mb:.2f}MB")


def _pid_alive(pid: int) -> bool:
    """PID가 현재 살아있는지 확인 (제로토큰)."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def action_health_check(peer_filter: str | None = None) -> None:
    """전체(또는 특정) 피어 건강 상태 출력. GREEN이지만 PID 종료 시 STALE로 표시."""
    peers_data = _load_peers()
    all_peers_cfg = peers_data.get("peers", peers_data)
    results = []
    targets = [peer_filter] if peer_filter else list(all_peers_cfg.keys())
    for peer_name in targets:
        peer_dir = Path(__file__).parent.parent / all_peers_cfg.get(peer_name, {}).get("sys_subdir", peer_name)
        health_path = peer_dir / "health.json"
        if not health_path.exists():
            results.append(f"{peer_name}=UNKNOWN")
            continue
        try:
            h = json.loads(health_path.read_text(encoding="utf-8"))
            ctx = h.get("context_health", {})
            st = ctx.get("status", "UNKNOWN")
            mb = ctx.get("jsonl_mb", 0.0)
            effective_st, _ = _peer_effective_health(peer_name)
            if effective_st == "STALE" and st != "STALE":
                st = "STALE"
                h.setdefault("context_health", {})["status"] = "STALE"
                h["context_health"]["stale_marked_at"] = _now()
                health_path.write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding="utf-8")
            # lazy PID 검증: GREEN인데 active_pid가 죽어있으면 STALE로 표시 후 갱신
            active_pid = h.get("availability", {}).get("active_pid")
            if st == "GREEN" and active_pid and not _pid_alive(active_pid):
                st = "STALE"
                h.setdefault("context_health", {})["status"] = "STALE"
                h["context_health"]["stale_marked_at"] = _now()
                h.setdefault("availability", {}).pop("active_pid", None)
                health_path.write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding="utf-8")
            results.append(f"{peer_name}={st}({mb:.1f}MB)")
        except Exception:
            results.append(f"{peer_name}=ERROR")
    print(f"[HUB:GATE] HEALTH | {' '.join(results)}")


def _run_status_check(check: dict) -> tuple[bool, str]:
    """Run a single safe status check command. Returns (success, output)."""
    safe_classes = {"version_only", "local_config_presence", "local_session_listing"}
    if check.get("class") not in safe_classes:
        return False, f"skipped (class={check.get('class')} not in safe set)"
    cmd_str = check.get("command", "")
    if not cmd_str:
        return False, "no command"
    try:
        parts = cmd_str.split()
        # On Windows, .CMD/.BAT wrappers require shell=True or resolved path
        exe = shutil.which(parts[0])
        if exe:
            parts[0] = exe
        result = subprocess.run(
            parts,
            capture_output=True, timeout=10,
            env={**os.environ, "PYTHONUTF8": "1"},
            shell=(sys.platform == "win32" and exe is None),
        )
        out = result.stdout.decode("utf-8", errors="replace").strip()
        return result.returncode == 0, out or result.stderr.decode("utf-8", errors="replace").strip()
    except FileNotFoundError:
        return False, "cli_not_found"
    except Exception as e:
        return False, str(e)


def _derive_gate_state(check_results: dict, gate_rule: dict) -> str:
    """Derive gate_state from check results and derived_gate_rule."""
    if not gate_rule:
        all_passed = all(ok for ok, _ in check_results.values())
        return "open" if all_passed else "degraded"
    closed_conditions = gate_rule.get("closed_if_any", [])
    degraded_conditions = gate_rule.get("degraded_if_any", [])
    open_conditions = gate_rule.get("open_if", [])
    failed_ids = {cid for cid, (ok, _) in check_results.items() if not ok}
    if any(c in failed_ids for c in closed_conditions):
        return "closed"
    if any(c in failed_ids for c in degraded_conditions):
        return "degraded"
    if open_conditions and all(c not in failed_ids for c in open_conditions):
        return "open"
    return "unknown"


def action_peer_status(node_id: str | None = None) -> None:
    """피어 상태 체크 — status_checks.json 선언적 엔진 + health.json 통합 테이블."""
    sys_dir = Path(__file__).parent.parent
    status_checks_path = sys_dir / "ai" / "status_checks.json"
    checks_cfg = {}
    if status_checks_path.exists():
        try:
            checks_cfg = json.loads(status_checks_path.read_text(encoding="utf-8")).get("peers", {})
        except Exception:
            pass

    peers_data = _load_peers()
    all_peers_cfg = peers_data.get("peers", peers_data)

    if node_id:
        target_peers = {k: v for k, v in all_peers_cfg.items() if k == node_id}
        if not target_peers:
            print(f"[HUB:ERROR] unknown peer: {node_id}", file=sys.stderr)
            return
    else:
        target_peers = {k: v for k, v in all_peers_cfg.items() if v.get("enabled", True)}

    print("┌─────────────────────────────────────────────────────────────┐")
    print("│  PEER STATUS (Protocol v4.1)                                │")
    print("├──────────┬──────────┬──────────┬──────────┬─────────────────┤")
    print("│ Peer     │ Gate     │ Health   │ Version  │ Details         │")
    print("├──────────┼──────────┼──────────┼──────────┼─────────────────┤")

    for peer_name, pcfg in target_peers.items():
        sys_subdir = pcfg.get("sys_subdir", peer_name)
        peer_dir = sys_dir / sys_subdir

        # 기존 gate 파일 확인
        gate_cfg = pcfg.get("gate")
        if gate_cfg:
            gate_file = sys_dir / gate_cfg["status_file"]
            try:
                gd = json.loads(gate_file.read_text(encoding="utf-8"))
                gate = "ON" if gd.get(gate_cfg["mode_key"]) == gate_cfg["mode_on_value"] else "OFF"
            except Exception:
                gate = "?"
        else:
            gate = "OPEN"

        # health.json 확인
        health_path = peer_dir / "health.json"
        if health_path.exists():
            try:
                h = json.loads(health_path.read_text(encoding="utf-8"))
                ctx = h.get("context_health", {})
                health = ctx.get("status", "?")
                mb = ctx.get("jsonl_mb", 0.0)
                details = f"{mb:.1f}MB"
            except Exception:
                health, details = "ERR", ""
        else:
            health, details = "NO FILE", ""

        # status_checks.json 선언적 체크 (version_only 클래스만)
        # peers.json 키는 "claude"/"gemini"/etc이지만 status_checks.json 키는 "cc"/"gc"/etc
        # lifecycle_policy.json node_to_peer 역방향 매핑으로 연결
        version_str = ""
        lp = _load_lifecycle_policy()
        node_to_peer_map = lp.get("identity", {}).get("node_to_peer", {})
        peer_to_node = {v: k for k, v in node_to_peer_map.items() if k not in ("ca",)}
        node_id_for_peer = peer_to_node.get(peer_name, peer_name)
        peer_checks = checks_cfg.get(node_id_for_peer, {})
        if peer_checks:
            check_results = {}
            gate_rule = peer_checks.get("derived_gate_rule", {})
            for check in peer_checks.get("safe_checks", []):
                if check.get("class") == "version_only":
                    ok, out = _run_status_check(check)
                    check_results[check["id"]] = (ok, out)
                    if ok and out:
                        version_str = out.split("\n")[0][:8]
            if check_results and not gate_cfg:
                derived = _derive_gate_state(check_results, gate_rule)
                gate = derived[:8]

        print(f"│ {peer_name:<8} │ {gate:<8} │ {health:<8} │ {version_str:<8} │ {details:<15} │")

    print("└──────────┴──────────┴──────────┴──────────┴─────────────────┘")


def _task_registry_path(ai_root: Path) -> Path:
    return ai_root / "task_registry.json"


def _file_locks_path(ai_root: Path) -> Path:
    return ai_root / "file_locks.json"


def _routing_metrics_path(ai_root: Path) -> Path:
    return ai_root / "routing_metrics.jsonl"


def _record_routing_metric(ai_root: Path, event: str, **fields) -> None:
    item = {"ts": _now(), "event": event}
    item.update(fields)
    _append_jsonl(_routing_metrics_path(ai_root), item)


def _checkpoint_active_tasks(ai_root: Path, peer: str, note: str) -> None:
    path = _task_registry_path(ai_root)
    if not path.exists():
        return
    with _get_lock(ai_root, "task_registry"):
        data = _read_json(path)
        changed = False
        for task in data.values():
            if isinstance(task, dict) and task.get("status") == "ACTIVE" and task.get("owner") == peer:
                task.setdefault("checkpoints", []).append({"peer": peer, "note": note, "at": _now()})
                task["updated_at"] = _now()
                changed = True
        if changed:
            _write_task_registry(ai_root, data)
            _append_handoff_item(ai_root, "ACTIVE_THREADS", f"{_now()} {peer}: checkpoint-before-yield recorded")


def action_leader_yield(ai_root: Path, agent: str, reason: str = "") -> None:
    """현재 리더가 리더십을 양도하여 공석(VACANT)으로 변경."""
    state_path = ai_root / "state.json"
    pressure_reasons = ("context", "health", "rate", "limit", "failure", "degraded")
    if any(token in (reason or "").lower() for token in pressure_reasons):
        _checkpoint_active_tasks(ai_root, agent, f"checkpoint-before-yield: {reason or 'unspecified'}")
    with _get_lock(ai_root, "state"):
        state = _read_json(state_path)
        current_leader = state.get("active_coordinator") or state.get("leader")
        
        if current_leader and current_leader != agent:
            print(f"[HUB:WARN] {agent} tried to yield leadership, but current leader is {current_leader}", file=sys.stderr)
            
        state["leader"] = None
        state["active_coordinator"] = None
        state["leadership"] = {
            "peer": None,
            "status": "VACANT",
            "yielded_by": agent,
            "yielded_at": _now(),
            "reason": reason or "none",
        }
        state["updated_at"] = _now()
        _write_state(ai_root, state)
        
    entry = f"[{_now()}] ({agent}) [YIELD] yielded leadership. Reason: {reason or 'none'}"
    _append_handoff_item(ai_root, "ACTIVE_THREADS", entry)
    
    _log_p2p("LEADER-YIELD", f"agent={agent} reason={reason or 'none'}", from_node=agent)
    print(f"[HUB] LEADER-YIELD {agent} | status=VACANT | reason={reason or 'none'}")


def action_leader_claim(ai_root: Path, agent: str, reason: str = "", domain: str = "") -> None:
    """새로운 피어가 리더십을 획득."""
    state_path = ai_root / "state.json"
    with _get_lock(ai_root, "state"):
        state = _read_json(state_path)
        current_leader = state.get("active_coordinator") or state.get("leader")
        
        if current_leader and current_leader != agent:
            status, _ = _peer_effective_health(current_leader)
            
            if status != "RED" and status != "STALE":
                print(f"[HUB:ERR] Cannot claim leadership. {current_leader} is still active and healthy ({status}).", file=sys.stderr)
                sys.exit(1)
                
        state["leader"] = agent
        state["active_coordinator"] = agent
        state["leadership"] = {
            "peer": agent,
            "status": "ACTIVE",
            "domain": domain or reason or "general",
            "reason": reason or "manual_claim",
            "claimed_at": _now(),
        }
        state["updated_at"] = _now()
        _write_state(ai_root, state)
        
    entry = f"[{_now()}] ({agent}) [CLAIM] claimed leadership. Domain: {domain or 'general'} Reason: {reason or 'manual_claim'}"
    _append_handoff_item(ai_root, "ACTIVE_THREADS", entry)
    
    _log_p2p("LEADER-CLAIM", f"agent={agent} domain={domain or 'general'} reason={reason or 'manual_claim'}", from_node=agent)
    print(f"[HUB] LEADER-CLAIM {agent} | domain={domain or 'general'} | reason={reason or 'manual_claim'}")


def action_discover(ai_root: Path, needs: str, effort: str = "mid") -> None:
    """피어 역할/기능 검색 — 요구되는 기능(needs)과 노력(effort)에 적합한 피어 추천."""
    proto_cfg = _load_protocol_cfg()
    matches = _matching_peers(needs, effort)
    if not matches:
        fallback = proto_cfg.get("consensus", {}).get("default_proposer", "cc")
        print(f"[HUB:DISCOVER] No matching peers found for needs='{needs}'. Fallback to default proposer: {fallback}")
        return
        
    print(f"[HUB:DISCOVER] Found {len(matches)} matching peer(s) for needs='{needs}':")
    for m in matches:
        print(f"  - {m['node_id']} (Score: {m.get('score', 0)}, Status: {m['status']}, Cost: {m['cost_tier']}, Tier: {m['model_tier']}) | Capabilities: {', '.join(m['capabilities'])}")


def action_elect_leader(ai_root: Path, needs: str, effort: str = "mid", reason: str = "") -> None:
    matches = _matching_peers(needs, effort)
    if not matches:
        candidate = _load_orchestration().get("consensus", {}).get("default_proposer", "cc")
    else:
        candidate = matches[0]["node_id"]
    _record_routing_metric(ai_root, "elect_leader", needs=needs or "general", effort=effort, selected=candidate, candidates=[{"node_id": m["node_id"], "score": m.get("score")} for m in matches])
    action_leader_claim(ai_root, candidate, reason or f"elected_for:{needs or 'general'}", needs or "general")


def action_checkpoint(ai_root: Path, agent: str, note: str) -> None:
    """세션 중간에 handoff.md에 체크포인트 항목 추가 — 다른 피어가 즉시 확인 가능."""
    state = _read_json(ai_root / "state.json")
    room_id = state.get("room_id")
    if not room_id:
        print("[HUB] CHECKPOINT: no active room", file=sys.stderr)
        sys.exit(1)
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    entry = f"[{ts}] ({agent}) {note}"
    _append_handoff_item(ai_root, "ACTIVE_THREADS", entry)
    _log_p2p("CHECKPOINT", f"agent={agent} room={room_id} note={note[:60]}")
    print(f"[HUB] CHECKPOINT {agent} | room={room_id} | {note[:80]}")


def action_context_fill(ai_root: Path, sections: list[str] | None = None) -> None:
    """handoff.md에서 지정 섹션만 읽어 컨텍스트 채우기용 블록 출력 — 제로토큰."""
    cfg = _load_protocol_cfg()
    default_sections = cfg.get("session", {}).get("context_fill_sections", ["GOAL", "PENDING_ISSUES", "KEY_DECISIONS", "ACTIVE_THREADS"])
    wanted = set(sections or default_sections)
    state = _read_json(ai_root / "state.json")
    room_id = state.get("room_id")
    if not room_id:
        print("[HUB] CONTEXT-FILL: no active room")
        return
    handoff_path = ai_root / "sessions" / room_id / "handoff.md"
    if not handoff_path.exists():
        print("[HUB] CONTEXT-FILL: no handoff.md found")
        return
    parsed = _parse_handoff(handoff_path.read_text(encoding="utf-8"))
    print(f"<!-- context-fill | room={room_id} | sections={','.join(wanted)} -->")
    for section, content in parsed.items():
        section_text = "\n".join(content).strip() if isinstance(content, list) else str(content).strip()
        if section in wanted and section_text:
            print(f"\n## [{section}]\n{section_text}")
    print("<!-- /context-fill -->")


# ─────────────────────────────────────────────────────────────
# CLI 진입점
# ─────────────────────────────────────────────────────────────

def _operational_guard_cfg() -> dict:
    return _load_protocol_cfg().get("operational_guard", {})


def _current_phase(ai_root: Path) -> str | None:
    phase = _read_json(ai_root / "state.json").get("phase")
    return str(phase).strip().lower() if phase is not None else None


def _is_mutating_action(action: str) -> bool:
    return action in set(_operational_guard_cfg().get("mutating_hub_actions", []))


def _current_coordinator_health(ai_root: Path) -> str:
    """Return the health state of the active coordinator peer, or MISSING if unknown."""
    try:
        state = _read_json(ai_root / "state.json")
        coordinator = state.get("active_coordinator") or state.get("leader")
        if not coordinator:
            return "MISSING"
        sys_dir = Path(__file__).parent.parent
        peers_data = _load_peers()
        peer_cfg = peers_data.get(coordinator, {})
        subdir = peer_cfg.get("sys_subdir", coordinator)
        health_path = sys_dir / subdir / "health.json"
        if not health_path.exists():
            return "MISSING"
        h = _read_json(health_path)
        return h.get("context_health", {}).get("status", "MISSING")
    except Exception:
        return "MISSING"


def _runtime_cfg() -> dict:
    return _load_protocol_cfg().get("runtime", {})


def _portable_state_path(ai_root: Path, rel: str) -> Path:
    path = Path(rel)
    if path.is_absolute():
        return path
    return (ai_root / path).resolve()


def _action_group(action: str) -> str:
    cfg = _operational_guard_cfg()
    for group in ("read_only_hub_actions", "recovery_hub_actions", "semi_governed_hub_actions", "mutating_hub_actions"):
        if action in set(cfg.get(group, [])):
            return group
    return "unknown_actions"


def _has_finalized_consensus(ai_root: Path) -> bool:
    consensus_dir = ai_root / "consensus"
    if not consensus_dir.exists():
        return False
    for f in consensus_dir.glob("*.json"):
        try:
            data = _read_json(f)
            if data.get("status") == "finalized":
                return True
        except Exception:
            pass
    return False


def _guard_action(ai_root: Path, action: str, force_tier0: bool = False) -> None:
    cfg = _operational_guard_cfg()
    if not cfg.get("enabled", False) or force_tier0:
        if force_tier0:
            _log_p2p("WARN", f"force-tier0 bypass for action={action}", from_node="TIER0")
        return
    try:
        rate_guard = cfg.get("collab_rate_guard", {})
        current = int(_load_protocol_cfg().get("collab_rate", {}).get("current", 0) or 0)
        threshold = int(rate_guard.get("threshold", 10) or 10)
        exempt = set(rate_guard.get("exempt_actions", []))
        if (
            rate_guard.get("enabled", False)
            and current >= threshold
            and action not in exempt
            and _is_mutating_action(action)
            and rate_guard.get("require_finalized_consensus", True)
            and not _has_finalized_consensus(ai_root)
        ):
            print(f"[HUB:BLOCK] action '{action}' requires finalized consensus at collab_rate {current}. Use --force-tier0 only for Tier0 recovery.", file=sys.stderr)
            sys.exit(3)
    except SystemExit:
        raise
    except Exception as e:
        print(f"[HUB:WARN] collab_rate guard check error: {e}", file=sys.stderr)
    group = _action_group(action)

    # semi_governed actions: exempt only during RED/STALE/rate-limited recovery
    if group == "semi_governed_hub_actions":
        peer_state = _current_coordinator_health(ai_root)
        if peer_state not in ("RED", "STALE", "RATE_LIMITED", "MISSING"):
            if rate_guard.get("enabled", False) and current >= threshold and not _has_finalized_consensus(ai_root):
                print(f"[HUB:BLOCK] action '{action}' is semi-governed and requires finalized consensus when coordinator is {peer_state}.", file=sys.stderr)
                sys.exit(3)
        # Always write audit record for semi-governed actions
        _log_p2p("AUDIT", f"semi-governed action={action} coordinator_state={peer_state}", from_node="GUARD")

    phase = _current_phase(ai_root)
    if not phase:
        if cfg.get("missing_phase_policy") == "allow_with_warning":
            print(f"[HUB:WARN] phase is unset; allowing action '{action}'", file=sys.stderr)
        elif not cfg.get("allow_missing_phase", True):
            print(f"[HUB:BLOCK] phase is unset; refusing action '{action}'", file=sys.stderr)
            sys.exit(3)
        return
    matrix = cfg.get("phase_action_matrix", {})
    matrix_key = "no_code" if phase in set(cfg.get("no_code_phases", [])) else "default"
    decision = matrix.get(matrix_key, matrix.get("default", {})).get(group, "allow")
    if decision == "block":
        flag = cfg.get("force_tier0_flag", "--force-tier0")
        print(f"[HUB:BLOCK] action '{action}' is blocked during phase '{phase}'. Use {flag} only for Tier0 recovery.", file=sys.stderr)
        sys.exit(3)
    if decision == "requires_classification":
        print(f"[HUB:BLOCK] action '{action}' has no phase policy during phase '{phase}'", file=sys.stderr)
        sys.exit(3)


def _regex_match(pattern: str, text: str) -> bool:
    try:
        return re.search(pattern, text, re.IGNORECASE | re.MULTILINE) is not None
    except re.error:
        return False


def _classify_command(cmd: str, shell: str | None = None) -> dict:
    cfg = _operational_guard_cfg()
    preflight = cfg.get("preflight", {})
    active_shell = (shell or cfg.get("default_shell") or "powershell").lower()
    command = (cmd or "").strip()
    result = {
        "command": command,
        "shell": active_shell,
        "classification": "requires_classification",
        "allowed": False,
        "matched_rule": None,
        "reason": preflight.get("unknown_policy", "requires_classification"),
    }
    for rule in preflight.get("shell_rules", {}).get(active_shell, {}).get("blocked_patterns", []):
        if _regex_match(rule.get("pattern", ""), command):
            result.update({
                "classification": "blocked_shell_mismatch",
                "matched_rule": rule.get("id"),
                "reason": rule.get("reason", "shell mismatch"),
            })
            return result
    for rule in preflight.get("mutating_patterns", []):
        if _regex_match(rule.get("pattern", ""), command):
            result.update({
                "classification": "mutating",
                "matched_rule": rule.get("id"),
                "reason": rule.get("reason", "mutating command"),
            })
            return result
    for rule in preflight.get("read_only_patterns", []):
        if _regex_match(rule.get("pattern", ""), command):
            result.update({
                "classification": "read_only",
                "allowed": True,
                "matched_rule": rule.get("id"),
                "reason": "read-only allowlist",
            })
            return result
    return result


def _operational_error_path(ai_root: Path) -> Path:
    rel = _operational_guard_cfg().get("error_memory", {}).get("path", "../_sys/data/operational_errors.jsonl")
    return (ai_root / rel).resolve()


def action_report_error(ai_root: Path, peer: str, pattern: str, detail: str = "", severity: str = "warn") -> None:
    path = _operational_error_path(ai_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": _now(),
        "peer": peer or "unknown",
        "pattern": pattern or "unknown",
        "severity": severity or "warn",
        "detail": detail or "",
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    count = 0
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            if item.get("peer") == event["peer"] and item.get("pattern") == event["pattern"]:
                count += 1
    except Exception:
        count = 1
    threshold = int(_operational_guard_cfg().get("error_memory", {}).get("quarantine_after", 3) or 3)
    if event["peer"] != "unknown" and threshold > 0 and count >= threshold:
        action_peer_quarantine(ai_root, event["peer"], f"operational_error:{event['pattern']}")
    print(f"[HUB] operational-error recorded peer={event['peer']} pattern={event['pattern']} count={count}")


def action_preflight(ai_root: Path, cmd: str, shell: str | None = None, peer: str | None = None) -> None:
    result = _classify_command(cmd, shell)
    if peer and not result.get("allowed"):
        action_report_error(ai_root, peer, result.get("matched_rule") or result.get("classification"), result.get("reason", ""), "warn")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _hash_read(path: Path, normalize_newlines: bool) -> bytes:
    if not path.exists():
        return b"<missing>"
    text = path.read_text(encoding="utf-8", errors="replace")
    if normalize_newlines:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.encode("utf-8")


def _compute_context_hash(ai_root: Path) -> str:
    cfg = _operational_guard_cfg().get("context_ack", {})
    algo = cfg.get("hash_algorithm", "sha256")
    normalize = bool(cfg.get("normalize_newlines", True))
    state = _read_json(ai_root / "state.json")
    room_id = state.get("room_id") or ""
    h = hashlib.new(algo)
    for source in cfg.get("sources", ["state.json"]):
        rel = source.replace("{room_id}", room_id)
        path = (ai_root / rel).resolve()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(_hash_read(path, normalize))
        h.update(b"\0")
    return h.hexdigest()


def action_context_hash(ai_root: Path) -> None:
    print(_compute_context_hash(ai_root))


def action_context_ack(ai_root: Path, peer: str, context_hash: str | None = None) -> None:
    key = peer or "unknown"
    path = ai_root / "context_ack.json"
    data = _read_json(path)
    state = _read_json(ai_root / "state.json")
    data[key] = {
        "hash": context_hash or _compute_context_hash(ai_root),
        "room_id": state.get("room_id"),
        "acked_at": _now(),
    }
    _write_json(path, data)
    print(f"[HUB] context-ack peer={key} hash={data[key]['hash']}")


def _feedback_path(ai_root: Path) -> Path:
    cfg = _load_protocol_cfg().get("feedback_loop", {})
    return _portable_state_path(ai_root, cfg.get("path", cfg.get("storage_path", "feedback.jsonl")))


def action_feedback_add(ai_root: Path, source_peer: str, category: str, severity: str, title: str, detail: str) -> None:
    fb_path = _feedback_path(ai_root)
    fb_path.parent.mkdir(parents=True, exist_ok=True)
    prefix = f"GAP-{datetime.now().strftime('%Y%m%d')}-"
    seq = 1
    if fb_path.exists():
        for line in fb_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            fid = item.get("id", "")
            if fid.startswith(prefix):
                try:
                    seq = max(seq, int(fid[len(prefix):]) + 1)
                except ValueError:
                    pass
    event = {
        "id": f"{prefix}{seq:03d}",
        "ts": _now(),
        "source_peer": source_peer or "unknown",
        "category": category or "other",
        "severity": severity or "medium",
        "title": title or "untitled",
        "detail": detail or "",
        "status": "open",
        "owner": None,
    }
    with _get_lock(ai_root, "feedback"):
        with fb_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    print(f"[HUB] FEEDBACK-ADD {event['id']} | peer={event['source_peer']} | title={event['title']}")


def action_feedback_list(ai_root: Path) -> None:
    fb_path = _feedback_path(ai_root)
    if not fb_path.exists():
        print("No feedback records found.")
        return
    print("id\tstatus\tseverity\tcategory\ttitle")
    for line in fb_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        print(f"{item.get('id','')}\t{item.get('status','')}\t{item.get('severity','')}\t{item.get('category','')}\t{item.get('title','')}")


def action_feedback_resolve(ai_root: Path, feedback_id: str, status: str = "done", owner: str | None = None) -> None:
    fb_path = _feedback_path(ai_root)
    if not fb_path.exists():
        print("[HUB:ERROR] feedback file not found", file=sys.stderr)
        sys.exit(1)
    updated = False
    output = []
    with _get_lock(ai_root, "feedback"):
        for line in fb_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("id") == feedback_id:
                item["status"] = status or "done"
                item["resolved_at"] = _now()
                if owner:
                    item["owner"] = owner
                updated = True
            output.append(json.dumps(item, ensure_ascii=False))
        if not updated:
            print(f"[HUB:ERROR] feedback ID {feedback_id} not found", file=sys.stderr)
            sys.exit(1)
        fb_path.write_text("\n".join(output) + "\n", encoding="utf-8")
    print(f"[HUB] FEEDBACK-RESOLVE {feedback_id} | status={status}")


def _leases_path(ai_root: Path) -> Path:
    return ai_root / "leases.json"


def _lease_cfg() -> tuple[int, int]:
    """Return (heartbeat_sec, lease_timeout_sec) from communication_policy."""
    comm = _load_protocol_cfg().get("communication_policy", {})
    h = max(5, int(comm.get("heartbeat_sec", 30) or 30))
    l = max(h + 30, int(comm.get("lease_timeout_sec", 300) or 300))
    return h, l


def _lease_open(ai_root: Path | None, peer_id: str, pid: int, lease_timeout_sec: int, ask_id: str | None = None, ask_query_file: str | None = None) -> None:
    if not ai_root:
        return
    state = _read_json(ai_root / "state.json") if (ai_root / "state.json").exists() else {}
    room_id = state.get("room_id")
    started = _now()
    from datetime import timedelta
    expires = (datetime.fromisoformat(started) + timedelta(seconds=lease_timeout_sec)).isoformat()[:19]
    entry = {
        "ask_id": ask_id or _short_id("ask-"),
        "peer_id": peer_id,
        "pid": pid,
        "room_id": room_id,
        "started_at": started,
        "expires_at": expires,
        "heartbeat_at": None,
        "status": "open",
        "ask_query_file": ask_query_file,
    }
    with _get_lock(ai_root, "leases"):
        data = _read_json(_leases_path(ai_root)) if _leases_path(ai_root).exists() else {}
        data[peer_id] = entry
        _write_json(_leases_path(ai_root), data)


def _lease_renew(ai_root: Path | None, peer_id: str, lease_timeout_sec: int) -> None:
    if not ai_root:
        return
    from datetime import timedelta
    now = _now()
    expires = (datetime.fromisoformat(now) + timedelta(seconds=lease_timeout_sec)).isoformat()[:19]
    with _get_lock(ai_root, "leases"):
        data = _read_json(_leases_path(ai_root)) if _leases_path(ai_root).exists() else {}
        if peer_id in data:
            data[peer_id]["heartbeat_at"] = now
            data[peer_id]["expires_at"] = expires
            _write_json(_leases_path(ai_root), data)


def _lease_close(ai_root: Path | None, peer_id: str, pid: int, status: str) -> None:
    if not ai_root:
        return
    with _get_lock(ai_root, "leases"):
        data = _read_json(_leases_path(ai_root)) if _leases_path(ai_root).exists() else {}
        if peer_id in data and data[peer_id].get("pid") == pid:
            data[peer_id]["status"] = status
            _write_json(_leases_path(ai_root), data)


def _kill_process_tree(proc: "subprocess.Popen") -> None:
    """Kill process tree (children first, then parent). Windows-safe."""
    try:
        parent = psutil.Process(proc.pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        try:
            parent.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
        pass
    try:
        proc.communicate(timeout=5)
    except Exception:
        pass


def _lease_sweep(ai_root: Path | None) -> None:
    """Kill orphaned open leases whose expires_at has passed. Updates health to STALE."""
    if not ai_root or not _leases_path(ai_root).exists():
        return
    now_dt = datetime.fromisoformat(_now())
    with _get_lock(ai_root, "leases"):
        data = _read_json(_leases_path(ai_root))
        changed = False
        for peer_id, entry in data.items():
            if entry.get("status") != "open":
                continue
            expires_str = entry.get("expires_at", "")
            if not expires_str:
                continue
            try:
                if datetime.fromisoformat(expires_str) < now_dt:
                    pid = entry.get("pid")
                    if pid:
                        try:
                            parent = psutil.Process(pid)
                            for child in parent.children(recursive=True):
                                try: child.kill()
                                except (psutil.NoSuchProcess, psutil.AccessDenied): pass
                            try: parent.kill()
                            except (psutil.NoSuchProcess, psutil.AccessDenied): pass
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                    entry["status"] = "expired"
                    changed = True
                    _record_ask_failure(peer_id, "lease_expired", f"lease expired at {expires_str}", None, ai_root)
                    _log_p2p("SWEEP", f"lease expired for {peer_id} pid={pid}", from_node="HUB")
            except Exception:
                pass
        if changed:
            _write_json(_leases_path(ai_root), data)


def _maildir_path(ai_root: Path) -> Path:
    return ai_root / "mailbox"


def _maildir_write(ai_root: Path, message: dict) -> None:
    """Write a single message as msg-{id}-{uuid}.json in the maildir."""
    maildir = _maildir_path(ai_root)
    maildir.mkdir(parents=True, exist_ok=True)
    fname = f"msg-{message['id']}-{message.get('_uuid', uuid.uuid4().hex[:8])}.json"
    _write_json(maildir / fname, message)


def _maildir_read_all(ai_root: Path) -> list[dict]:
    """Read all msg-*.json files from maildir, sorted by message id."""
    maildir = _maildir_path(ai_root)
    if not maildir.exists():
        return []
    messages = []
    for path in sorted(maildir.glob("msg-*.json")):
        try:
            messages.append(_read_json(path))
        except Exception:
            pass
    messages.sort(key=lambda m: m.get("id", 0))
    return messages


def _maildir_mark_read(ai_root: Path, msg_id: int | None, target: str, all_: bool) -> int:
    """Mark maildir message files as read. Returns count changed."""
    maildir = _maildir_path(ai_root)
    if not maildir.exists():
        return 0
    count = 0
    for path in maildir.glob("msg-*.json"):
        try:
            m = _read_json(path)
            if m.get("to") == target and m.get("status") == "unread":
                if all_ or m.get("id") == msg_id:
                    m["status"] = "read"
                    _write_json(path, m)
                    count += 1
        except Exception:
            pass
    return count


def _artifact_path(ai_root: Path) -> Path:
    cfg = _load_protocol_cfg().get("artifact_workflow", {})
    return _portable_state_path(ai_root, cfg.get("path", cfg.get("storage_path", "artifacts.json")))


def _is_workspace_local(ai_root: Path, path_str: str) -> bool:
    """Return True if path_str resolves within the workspace root (ai_root.parent)."""
    workspace_root = ai_root.parent.resolve()
    try:
        resolved = Path(path_str).resolve()
        return resolved == workspace_root or workspace_root in resolved.parents
    except Exception:
        return False


def action_artifact_claim(ai_root: Path, artifact_name: str, owner: str) -> None:
    art_path = _artifact_path(ai_root)
    art_path.parent.mkdir(parents=True, exist_ok=True)
    with _get_lock(ai_root, "artifact"):
        data = _read_json(art_path) if art_path.exists() else {}
        existing = data.get(artifact_name, {})
        if existing.get("owner") and existing.get("owner") != owner and existing.get("status") != "finalized":
            print(f"[HUB:ERROR] artifact {artifact_name} is already claimed by {existing.get('owner')}", file=sys.stderr)
            sys.exit(1)
        data[artifact_name] = {
            "artifact": artifact_name,
            "owner": owner or "unknown",
            "mode": _load_protocol_cfg().get("artifact_workflow", {}).get("default_mode", "single_owner_merge"),
            "drafts": existing.get("drafts", {}),
            "status": "claimed",
            "claimed_at": existing.get("claimed_at") or _now(),
            "hash": existing.get("hash", ""),
        }
        _write_json(art_path, data)
    print(f"[HUB] ARTIFACT-CLAIM {artifact_name} | owner={owner or 'unknown'}")


def action_artifact_status(ai_root: Path, artifact_name: str | None, register_peer: str | None = None, draft_path: str | None = None) -> None:
    art_path = _artifact_path(ai_root)
    if not art_path.exists():
        print("No artifact metadata records found.")
        return
    with _get_lock(ai_root, "artifact"):
        data = _read_json(art_path)
        if register_peer and draft_path and artifact_name:
            if artifact_name not in data:
                print(f"[HUB:ERROR] artifact {artifact_name} has not been claimed yet", file=sys.stderr)
                sys.exit(1)
            if not _is_workspace_local(ai_root, draft_path):
                print(f"[HUB:WARN] artifact draft path is outside workspace: {draft_path}", file=sys.stderr)
            data[artifact_name].setdefault("drafts", {})[register_peer] = draft_path
            data[artifact_name]["status"] = "draft"
            data[artifact_name]["external_draft_warned"] = not _is_workspace_local(ai_root, draft_path)
            _write_json(art_path, data)
            print(f"[HUB] ARTIFACT-DRAFT {artifact_name} | peer={register_peer} | path={draft_path}")
            return
    if artifact_name:
        print(json.dumps(data.get(artifact_name, {}), ensure_ascii=False, indent=2))
        return
    print("artifact\towner\tstatus\tclaimed_at")
    for key, item in data.items():
        print(f"{key}\t{item.get('owner','')}\t{item.get('status','')}\t{item.get('claimed_at','')}")


def action_artifact_finalize(ai_root: Path, artifact_name: str, file_path: str) -> None:
    actual_file = Path(file_path)
    if not actual_file.exists():
        print(f"[HUB:ERROR] file {file_path} not found for finalization", file=sys.stderr)
        sys.exit(1)
    if not _is_workspace_local(ai_root, file_path):
        print(f"[HUB:WARN] artifact final path is outside workspace: {file_path}", file=sys.stderr)
    sha_str = f"sha256:{hashlib.sha256(actual_file.read_bytes()).hexdigest()}"
    art_path = _artifact_path(ai_root)
    with _get_lock(ai_root, "artifact"):
        data = _read_json(art_path) if art_path.exists() else {}
        if artifact_name not in data:
            print(f"[HUB:ERROR] artifact {artifact_name} has not been claimed yet", file=sys.stderr)
            sys.exit(1)
        data[artifact_name]["status"] = "finalized"
        data[artifact_name]["hash"] = sha_str
        data[artifact_name]["finalized_at"] = _now()
        data[artifact_name]["actual_path"] = str(actual_file.resolve())
        _write_json(art_path, data)
    print(f"[HUB] ARTIFACT-FINALIZE {artifact_name} | hash={sha_str}")


def action_assign_role(ai_root: Path, role: str, peer: str) -> None:
    if not role or not peer:
        print("[HUB:ERROR] assign-role requires --role and --peer", file=sys.stderr)
        sys.exit(1)
    if not _healthy_peer(peer):
        status, _ = _peer_effective_health(peer)
        print(f"[HUB:ERROR] cannot assign role to unhealthy peer {peer} status={status}", file=sys.stderr)
        sys.exit(2)
    with _get_lock(ai_root, "state"):
        state = _read_json(ai_root / "state.json")
        assignments = state.setdefault("role_assignments", {})
        assignments[role] = {
            "peer": peer,
            "status": "ACTIVE",
            "assigned_at": _now(),
        }
        state["roles"] = {k: v.get("peer") for k, v in assignments.items() if isinstance(v, dict)}
        state["updated_at"] = _now()
        _write_state(ai_root, state)
    _append_handoff_item(ai_root, "ACTIVE_THREADS", f"{_now()} role:{role} assigned to {peer}")
    print(f"[HUB] ASSIGN-ROLE {role} -> {peer}")


def action_role_status(ai_root: Path) -> None:
    state = _read_json(ai_root / "state.json")
    assignments = state.get("role_assignments") or {}
    if not assignments:
        print("No active role assignments.")
        return
    print("role\tpeer\tstatus\tassigned_at")
    for role, info in assignments.items():
        if isinstance(info, dict):
            print(f"{role}\t{info.get('peer','')}\t{info.get('status','')}\t{info.get('assigned_at','')}")
        else:
            print(f"{role}\t{info}\tACTIVE\t")

def action_health_precheck(ai_root: Path, needs: str | None = None, peers: str | None = None) -> None:
    orch = _load_orchestration()
    selected: list[str] | None = None
    explicit_peers = peers is not None
    if peers:
        selected = [p.strip() for p in peers.split(",") if p.strip()]
    elif needs:
        selected = [m["node_id"] for m in _matching_peers(needs)]
        if not selected:
            selected = []
    critical_failed = False
    checked = 0
    eligible = 0
    for node in orch.get("hub_nodes", []):
        if node.get("enabled") is False and not peers:
            continue
        peer = node.get("node_id")
        if selected is not None and peer not in selected:
            continue
        checked += 1
        sys_subdir = _peer_sys_dir(peer)
        h_file = sys_subdir / "health.json"
        if h_file.exists():
            h_data = _read_json(h_file)
            status, h_data = _peer_effective_health(peer)
            gate = h_data.get("availability", {}).get("gate_open", True)
            if status == "YELLOW":
                print(f"[HUB:WARN] Pre-check warning for {peer}: status={status}, gate_open={gate}")
            if status == "STALE":
                print(f"[HUB:WARN] Pre-check stale for {peer}: status={status}, gate_open={gate}")
                if explicit_peers:
                    critical_failed = True
            if status == "RED" or gate is False:
                print(f"[HUB:WARN] Pre-check failed for {peer}: status={status}, gate_open={gate}")
                critical_failed = True
            elif status in {"GREEN", "YELLOW"}:
                eligible += 1
        else:
            print(f"[HUB:WARN] Pre-check missing health file for {peer}")
            if explicit_peers:
                critical_failed = True
    if selected is not None and (checked == 0 or eligible == 0):
        critical_failed = True
    if critical_failed:
        scope = needs or peers or "all"
        print(f"[HUB:ERROR] Governance Health Pre-Check FAILED. Scope={scope}", file=sys.stderr)
        sys.exit(1)
    else:
        scope = needs or peers or "all"
        print(f"[HUB] PRE-CHECK OK: scope={scope}")

def action_append_handoff(ai_root: Path, section: str, text: str) -> None:
    if not section or not text:
        print("[HUB:ERROR] append-handoff requires --section and --text", file=sys.stderr)
        sys.exit(1)
    state = _read_json(ai_root / "state.json")
    room_id = state.get("room_id")
    if not room_id:
        print("[HUB:ERROR] No active room", file=sys.stderr)
        sys.exit(1)
    handoff_path = ai_root / "sessions" / room_id / "handoff.md"
    if not handoff_path.exists():
        print(f"[HUB:ERROR] {handoff_path} not found", file=sys.stderr)
        sys.exit(1)
    lines = handoff_path.read_text(encoding="utf-8").splitlines()
    out = []
    inserted = False
    for line in lines:
        out.append(line)
        if line.strip() == f"## [{section.upper()}]":
            out.append(f"- {text}")
            inserted = True
    if not inserted:
        out.append(f"## [{section.upper()}]")
        out.append(f"- {text}")
    handoff_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"[HUB] APPEND-HANDOFF to [{section.upper()}]")


def action_task_checkpoint(ai_root: Path, task_id: str, peer: str, note: str) -> None:
    if not task_id or not peer or not note:
        print("[HUB:ERROR] task-checkpoint requires --id, --peer/--agent, and --msg", file=sys.stderr)
        sys.exit(1)
    _role_guard(ai_root, peer, "task-checkpoint", {"coordinator", "implementer", "documenter"})
    path = _task_registry_path(ai_root)
    with _get_lock(ai_root, "task_registry"):
        data = _read_json(path) if path.exists() else {}
        task = data.setdefault(task_id, {"task_id": task_id, "created_at": _now(), "checkpoints": []})
        task["owner"] = peer
        task["status"] = "ACTIVE"
        task["updated_at"] = _now()
        task.setdefault("checkpoints", []).append({"peer": peer, "note": note, "at": _now()})
        _write_task_registry(ai_root, data)
    _append_handoff_item(ai_root, "ACTIVE_THREADS", f"{_now()} task:{task_id} checkpoint by {peer}: {note[:120]}")
    print(f"[HUB] TASK-CHECKPOINT {task_id} | peer={peer}")


def action_task_status(ai_root: Path, task_id: str | None = None) -> None:
    path = _task_registry_path(ai_root)
    if not path.exists():
        print("No task registry records found.")
        return
    data = _read_json(path)
    if task_id:
        print(json.dumps(data.get(task_id, {}), ensure_ascii=False, indent=2))
        return
    print("task_id\towner\tstatus\tupdated_at\tcheckpoints")
    for key, item in data.items():
        print(f"{key}\t{item.get('owner','')}\t{item.get('status','')}\t{item.get('updated_at','')}\t{len(item.get('checkpoints', []))}")


def action_role_release(ai_root: Path, role: str, peer: str = "") -> None:
    if not role:
        print("[HUB:ERROR] release-role requires --role", file=sys.stderr)
        sys.exit(1)
    with _get_lock(ai_root, "state"):
        state = _read_json(ai_root / "state.json")
        assignments = state.get("role_assignments") or {}
        current = assignments.get(role)
        if not current:
            print(f"[HUB:WARN] role {role} is not assigned")
            return
        if peer and isinstance(current, dict) and current.get("peer") != peer:
            print(f"[HUB:ERROR] role {role} belongs to {current.get('peer')}, not {peer}", file=sys.stderr)
            sys.exit(1)
        assignments.pop(role, None)
        state["role_assignments"] = assignments
        state["roles"] = {k: v.get("peer") for k, v in assignments.items() if isinstance(v, dict)}
        state["updated_at"] = _now()
        _write_state(ai_root, state)
    _append_handoff_item(ai_root, "ACTIVE_THREADS", f"{_now()} role:{role} released")
    print(f"[HUB] RELEASE-ROLE {role}")


def action_task_failover(ai_root: Path, task_id: str, to_peer: str, reason: str = "") -> None:
    if not task_id or not to_peer:
        print("[HUB:ERROR] task-failover requires --task-id and --peer", file=sys.stderr)
        sys.exit(1)
    if not _healthy_peer(to_peer):
        status, _ = _peer_effective_health(to_peer)
        print(f"[HUB:ERROR] failover target {to_peer} is not healthy status={status}", file=sys.stderr)
        sys.exit(2)
    path = _task_registry_path(ai_root)
    with _get_lock(ai_root, "task_registry"):
        data = _read_json(path) if path.exists() else {}
        task = data.get(task_id)
        if not task:
            print(f"[HUB:ERROR] task {task_id} not found", file=sys.stderr)
            sys.exit(1)
        old_owner = task.get("owner")
        task["owner"] = to_peer
        task["status"] = "ACTIVE"
        task["updated_at"] = _now()
        task.setdefault("checkpoints", []).append({
            "peer": to_peer,
            "note": f"failover from {old_owner or 'unknown'}: {reason or 'manual'}",
            "at": _now(),
        })
        _write_task_registry(ai_root, data)
    _append_handoff_item(ai_root, "ACTIVE_THREADS", f"{_now()} task:{task_id} failover {old_owner or 'unknown'} -> {to_peer} ({reason or 'manual'})")
    print(f"[HUB] TASK-FAILOVER {task_id} | {old_owner or 'unknown'} -> {to_peer}")


def action_file_lock(ai_root: Path, name: str, owner: str, scope: str = "") -> None:
    if not name or not owner:
        print("[HUB:ERROR] file-lock requires --name and --peer/--agent", file=sys.stderr)
        sys.exit(1)
    path = _file_locks_path(ai_root)
    with _get_lock(ai_root, "file_locks"):
        data = _read_json(path) if path.exists() else {}
        existing = data.get(name)
        if existing and existing.get("owner") != owner:
            print(f"[HUB:ERROR] {name} is locked by {existing.get('owner')}", file=sys.stderr)
            sys.exit(1)
        data[name] = {"name": name, "owner": owner, "scope": scope or "file", "locked_at": existing.get("locked_at") if existing else _now()}
        _write_json(path, data)
    print(f"[HUB] FILE-LOCK {name} | owner={owner}")


def action_file_unlock(ai_root: Path, name: str, owner: str = "") -> None:
    if not name:
        print("[HUB:ERROR] file-unlock requires --name", file=sys.stderr)
        sys.exit(1)
    path = _file_locks_path(ai_root)
    with _get_lock(ai_root, "file_locks"):
        data = _read_json(path) if path.exists() else {}
        existing = data.get(name)
        if not existing:
            print(f"[HUB:WARN] {name} is not locked")
            return
        if owner and existing.get("owner") != owner:
            print(f"[HUB:ERROR] {name} is locked by {existing.get('owner')}, not {owner}", file=sys.stderr)
            sys.exit(1)
        data.pop(name, None)
        _write_json(path, data)
    print(f"[HUB] FILE-UNLOCK {name}")


def action_lock_status(ai_root: Path) -> None:
    path = _file_locks_path(ai_root)
    data = _read_json(path) if path.exists() else {}
    if not data:
        print("No active file locks.")
        return
    print("name\towner\tscope\tlocked_at")
    for name, item in data.items():
        print(f"{name}\t{item.get('owner','')}\t{item.get('scope','')}\t{item.get('locked_at','')}")


def action_health_sweep(ai_root: Path) -> None:
    swept = 0
    for node in _load_orchestration().get("hub_nodes", []):
        if node.get("enabled") is False:
            continue
        peer = node.get("node_id")
        status, data = _peer_effective_health(peer)
        if status == "STALE":
            was_stale = data.get("context_health", {}).get("status") == "STALE"
            data.setdefault("context_health", {})["status"] = "STALE"
            data["context_health"]["stale_marked_at"] = _now()
            _write_peer_health(peer, data, ai_root)
            if not was_stale:
                _append_handoff_item(ai_root, "PENDING_ISSUES", f"{_now()} {peer}: health marked STALE by health-sweep")
            swept += 1
    print(f"[HUB] HEALTH-SWEEP stale={swept}")


def action_validate_profiles(node_id: str | None = None) -> None:
    """Cross-check model_profiles.json against status_checks.json for each node."""
    errors = []
    profiles = _load_model_profiles().get("profiles", {})
    checks_path = Path(__file__).parent.parent / "ai" / "status_checks.json"
    checks_cfg = _read_json(checks_path).get("peers", {})
    nodes = _default_nodes()["nodes"]
    targets = [node_id] if node_id and node_id in nodes else list(nodes.keys())

    for target in targets:
        node = nodes.get(target)
        if not node:
            errors.append(f"{target}: unknown node")
            continue
        if not node.get("enabled", True):
            continue
        profile_id = _resolve_profile_id(target)
        profile = profiles.get(profile_id or "")
        if not profile:
            errors.append(f"{target}: no matching model profile (resolved={profile_id})")
            continue
        peer = node.get("peer") or profile.get("peer") or target
        status = checks_cfg.get(peer)
        if not status:
            errors.append(f"{target}: no status_checks entry for peer '{peer}'")
            continue
        if profile.get("peer") and profile.get("peer") != peer:
            errors.append(f"{target}: profile.peer={profile.get('peer')} != node.peer={peer}")
        routing_state = profile.get("routing_state")
        declared_status = status.get("status")
        if routing_state == "eligible" and declared_status not in ("eligible", "degraded"):
            errors.append(f"{target}: profile routing_state=eligible but status_checks.status={declared_status}")
        known_overrides = status.get("known_overrides", {})
        for key in profile.get("invoke_overrides", {}):
            expected = f"{key}_flag"
            if expected not in known_overrides:
                errors.append(f"{target}: invoke_override '{key}' not in status_checks known_overrides.{expected}")

    if errors:
        for err in errors:
            print(f"[HUB:PROFILE:ERR] {err}", file=sys.stderr)
        sys.exit(1)
    print(f"[HUB] PROFILE-VALIDATE OK ({len(targets)} nodes checked)")


def action_lease_status(ai_root: Path) -> None:
    """Show current lease state and whether each PID is still alive."""
    leases_path = _leases_path(ai_root)
    if not leases_path.exists():
        print("[HUB] No leases.json found.")
        return
    data = _read_json(leases_path)
    if not data:
        print("[HUB] No active leases.")
        return
    print(f"{'Peer':<8} {'Status':<10} {'PID':<8} {'Alive':<6} {'Expires':<20} {'Heartbeat':<20}")
    print("-" * 78)
    now_dt = datetime.fromisoformat(_now())
    for peer_id, entry in data.items():
        pid = entry.get("pid", 0)
        status = entry.get("status", "?")
        expires = entry.get("expires_at", "")[:19]
        hb = (entry.get("heartbeat_at") or "")[:19]
        alive = "?"
        if pid:
            try:
                alive = "YES" if psutil.pid_exists(pid) else "NO"
            except Exception:
                alive = "ERR"
        expired_flag = ""
        if status == "open" and expires:
            try:
                if datetime.fromisoformat(expires) < now_dt:
                    expired_flag = " !"
            except Exception:
                pass
        print(f"{peer_id:<8} {status + expired_flag:<10} {pid:<8} {alive:<6} {expires:<20} {hb:<20}")


def action_model_status() -> None:
    print("peer\tstatus\tcost\ttier\tcontext\tcapabilities")
    for node in _load_orchestration().get("hub_nodes", []):
        if node.get("enabled") is False:
            continue
        peer = node.get("node_id")
        status, data = _peer_effective_health(peer)
        profile = data.get("profile", {})
        caps = ",".join(str(c) for c in profile.get("capabilities", []))
        print(f"{peer}\t{status}\t{profile.get('cost_tier','')}\t{profile.get('tier','')}\t{profile.get('context_window','')}\t{caps}")


def action_transient_scan(ai_root: Path) -> None:
    root = ai_root.parent
    candidates = []
    for path in root.iterdir():
        if path.is_file() and re.match(r"^[A-Za-z0-9_-]{4,12}\.(tmp|log|txt)$", path.name):
            candidates.append(path.name)
    if not candidates:
        print("No transient root-file candidates found.")
        return
    print("transient-candidates")
    for name in candidates:
        print(name)


def action_approval_request(ai_root: Path, from_peer: str, action: str, auth_needed: str, scope: str, risk: str, fallback: str = "") -> None:
    _role_guard(ai_root, from_peer or "unknown", "approval-request", {"coordinator", "implementer", "researcher", "documenter"})
    state = _read_json(ai_root / "state.json")
    target = state.get("human_interface_peer") or state.get("active_console_peer") or "cx"
    content = "\n".join([
        "APPROVAL_REQUEST:",
        f"REQUESTING_PEER: {from_peer or 'unknown'}",
        f"EXECUTING_PEER: {from_peer or 'unknown'}",
        f"ACTION: {action or 'unspecified'}",
        f"AUTH_NEEDED: {auth_needed or 'unspecified'}",
        f"SCOPE: {scope or 'unspecified'}",
        f"RISK: {risk or 'unspecified'}",
        f"FALLBACK: {fallback or 'none'}",
    ])
    action_send(ai_root, from_peer or "unknown", target, content, None, "APPROVAL_REQUEST", [], None, "CRITICAL")
    _append_handoff_item(ai_root, "PENDING_ISSUES", f"{_now()} approval requested by {from_peer or 'unknown'} for {action or 'unspecified'}")
    print(f"[HUB] APPROVAL-REQUEST {from_peer or 'unknown'} -> {target}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="hub", description="AI 협업 허브 — Protocol v4.1")
    parser.add_argument("action", choices=["init-session", "end-session", "send", "broadcast", "mark-read", "append-log", "archive-file", "update-status", "check", "status", "check-gate", "ask", "ask-coordinator", "consensus-propose", "consensus-vote", "consensus-check", "consensus-sweep", "register-node", "list-nodes", "health-update", "health-check", "peer-status", "context-fill", "checkpoint", "peer-quarantine", "peer-recover", "new-topic", "clear-room", "preflight", "context-hash", "context-ack", "report-error", "feedback-add", "feedback-list", "feedback-resolve", "artifact-claim", "artifact-status", "artifact-finalize", "leader-yield", "leader-claim", "elect-leader", "discover", "assign-role", "release-role", "role-status", "health-precheck", "health-sweep", "append-handoff", "task-checkpoint", "task-status", "task-failover", "approval-request", "file-lock", "file-unlock", "lock-status", "profile-validate", "lease-status", "lease-sweep", "model-status", "transient-scan"])
    parser.add_argument("--needs")
    parser.add_argument("--effort", default="mid")
    parser.add_argument("--agent")
    parser.add_argument("--room")
    parser.add_argument("--from", dest="from_")
    parser.add_argument("--to", dest="to_")
    parser.add_argument("--msg")
    parser.add_argument("--thread-id")
    parser.add_argument("--type", default="MSG")
    parser.add_argument("--priority")
    parser.add_argument("--cc")
    parser.add_argument("--ref", type=int)
    parser.add_argument("--query", default="")
    parser.add_argument("--query-file")
    parser.add_argument("--target")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--id", type=int)
    parser.add_argument("--axis")
    parser.add_argument("--script")
    parser.add_argument("--status", dest="status_val")
    parser.add_argument("--detail", default="")
    parser.add_argument("--name")
    parser.add_argument("--file", dest="file_path")
    parser.add_argument("--mission")
    parser.add_argument("--blocked")
    parser.add_argument("--phase")
    parser.add_argument("--round-id")
    parser.add_argument("--subject")
    parser.add_argument("--voters")
    parser.add_argument("--voter")
    parser.add_argument("--vote", dest="vote_val")
    parser.add_argument("--reason", default="")
    parser.add_argument("--timeout", type=int, default=0)
    parser.add_argument("--tier", type=int, default=4)
    parser.add_argument("--node-type", dest="node_type", default="agent")
    parser.add_argument("--invoke", default="")
    parser.add_argument("--invoke-args", dest="invoke_args_str", default="-p,{query}")
    parser.add_argument("--memory", default="short-term")
    parser.add_argument("--peer")
    parser.add_argument("--cmd")
    parser.add_argument("--shell")
    parser.add_argument("--context-hash")
    parser.add_argument("--pattern")
    parser.add_argument("--severity", default="warn")
    parser.add_argument("--force-tier0", action="store_true")
    parser.add_argument("--jsonl-mb", dest="jsonl_mb", type=float, default=0.0)
    parser.add_argument("--failures", type=int, default=0)
    parser.add_argument("--sections")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--output-file")
    parser.add_argument("--category")
    parser.add_argument("--draft-path")
    parser.add_argument("--feedback-id")
    parser.add_argument("--role")
    parser.add_argument("--section")
    parser.add_argument("--text")
    parser.add_argument("--task-id")
    parser.add_argument("--auth-needed")
    parser.add_argument("--scope")
    parser.add_argument("--fallback")
    parser.add_argument("--session-policy", dest="session_policy", default="auto",
                        choices=["auto", "reuse", "fresh", "none"],
                        help="Session reuse policy: auto=use node config, reuse=always reuse, fresh=always new, none=disable")

    args = parser.parse_args()
    if args.action == "ask":
        ai_root_opt = None
        try: ai_root_opt = find_ai_root()
        except: pass
        action_ask(args.to_, args.query, args.query_file, args.timeout, ai_root_opt, quiet=args.quiet, output_file=args.output_file, session_policy=args.session_policy, explicit_scope=args.scope)
        return

    ai_root = find_ai_root()
    ensure_ai_dir(ai_root)
    act = args.action
    _guard_action(ai_root, act, args.force_tier0)
    if act == "ask-coordinator":
        action_ask_coordinator(ai_root, args.query, args.query_file, args.timeout, args.from_ or args.peer or args.agent or "unknown", quiet=args.quiet, output_file=args.output_file)
        return
    if act == "init-session": action_init_session(ai_root, args.agent or "cc", args.room)
    elif act == "end-session": action_end_session(ai_root, args.agent or "cc")
    elif act == "send": 
        cc_list = [x.strip() for x in args.cc.split(",") if x.strip()] if args.cc else []
        action_send(ai_root, args.from_, args.to_, args.msg, args.thread_id, args.type, cc_list, args.ref, args.priority)
    elif act == "broadcast":
        targets = [x.strip() for x in args.to_.split(",") if x.strip()] if args.to_ else None
        action_broadcast(ai_root, args.from_ or "system", args.msg or "", targets, args.type, args.priority)
    elif act == "mark-read": action_mark_read(ai_root, args.target, args.all, args.id)
    elif act == "append-log": action_append_log(ai_root, args.axis, args.script, args.status_val, args.detail)
    elif act == "archive-file": action_archive_file(ai_root, args.name, args.file_path)
    elif act == "update-status": action_update_status(ai_root, args.mission, args.blocked, args.phase)
    elif act == "check": action_check(ai_root, args.target)
    elif act == "status": action_status(ai_root)
    elif act == "check-gate":
        orch = _load_orchestration()
        default_gate_agent = orch.get("check_gate", {}).get("default_agent", "gc")
        action_check_gate(ai_root, args.agent or default_gate_agent)
    elif act == "consensus-propose":
        proto_cfg = _load_protocol_cfg()
        consensus_cfg = proto_cfg.get("consensus", {})
        canonical_voters = consensus_cfg.get("r10_voters", ["cc", "ca", "gc", "ag", "cx"])
        default_proposer = consensus_cfg.get("default_proposer", "cc")
        if args.voters:
            voters = [v.strip() for v in args.voters.split(",") if v.strip()]
        else:
            voters = canonical_voters
        action_consensus_propose(ai_root, args.subject, voters, args.from_ or default_proposer)
    elif act == "consensus-vote": action_consensus_vote(ai_root, args.round_id, args.voter, args.vote_val, args.reason)
    elif act == "consensus-check": action_consensus_check(ai_root, args.round_id)
    elif act == "consensus-sweep": action_consensus_sweep(ai_root, args.timeout or 30)
    elif act == "list-nodes": action_list_nodes(ai_root)
    elif act == "register-node":
        action_register_node(
            ai_root, args.name or "", int(getattr(args, "tier", 4) or 4),
            getattr(args, "node_type", "agent") or "agent",
            args.invoke or "", args.invoke_args_str or "-p,{query}",
            args.memory or "short-term", int(args.timeout or 0),
        )
    elif act == "health-update":
        action_health_update(args.peer or "cc", args.status_val or "GREEN", args.jsonl_mb, args.failures)
    elif act == "health-check":
        action_health_check(args.peer)
    elif act == "peer-status":
        action_peer_status(args.peer or None)
    elif act == "context-fill":
        sections = [s.strip() for s in args.sections.split(",")] if args.sections else None
        action_context_fill(ai_root, sections)
    elif act == "checkpoint":
        note = args.msg or ""
        if not note:
            print("[HUB] checkpoint requires --msg", file=sys.stderr); sys.exit(1)
        action_checkpoint(ai_root, args.agent or "unknown", note)
    elif act == "peer-quarantine":
        action_peer_quarantine(ai_root, args.peer or args.target or "", args.reason or "")
    elif act == "peer-recover":
        action_peer_recover(ai_root, args.peer or args.target or "", args.reason or "")
    elif act == "new-topic":
        action_new_topic(ai_root, args.subject or args.mission or "")
    elif act == "clear-room":
        action_clear_room(ai_root, args.subject or args.mission or "")
    elif act == "preflight":
        if not args.cmd:
            print("[HUB] preflight requires --cmd", file=sys.stderr); sys.exit(1)
        action_preflight(ai_root, args.cmd, args.shell, args.peer or args.agent)
    elif act == "context-hash":
        action_context_hash(ai_root)
    elif act == "context-ack":
        action_context_ack(ai_root, args.peer or args.agent or "unknown", args.context_hash)
    elif act == "report-error":
        action_report_error(ai_root, args.peer or args.agent or "unknown", args.pattern or args.reason or "unknown", args.detail, args.severity)
    elif act == "feedback-add":
        peer = args.peer or args.from_ or "unknown"
        action_feedback_add(ai_root, peer, args.category, args.severity, args.subject or args.msg or "unknown gap", args.detail)
    elif act == "feedback-list":
        action_feedback_list(ai_root)
    elif act == "feedback-resolve":
        action_feedback_resolve(ai_root, args.feedback_id or args.round_id, args.status_val or "done", args.agent or args.peer)
    elif act == "artifact-claim":
        action_artifact_claim(ai_root, args.name, args.peer or args.agent or "unknown")
    elif act == "artifact-status":
        action_artifact_status(ai_root, args.name, args.peer or args.agent, args.draft_path)
    elif act == "artifact-finalize":
        action_artifact_finalize(ai_root, args.name, args.file_path)
    elif act == "leader-yield":
        action_leader_yield(ai_root, args.agent or "unknown", args.reason or args.detail)
    elif act == "leader-claim":
        action_leader_claim(ai_root, args.agent or "unknown", args.reason or args.detail or "", args.needs or "")
    elif act == "elect-leader":
        action_elect_leader(ai_root, args.needs or args.role or "general", args.effort, args.reason or args.detail or "")
    elif act == "discover":
        if not args.needs:
            print("[HUB] discover requires --needs", file=sys.stderr); sys.exit(1)
        action_discover(ai_root, args.needs, args.effort)
    elif act == "assign-role":
        action_assign_role(ai_root, args.role, args.peer)
    elif act == "release-role":
        action_role_release(ai_root, args.role, args.peer or args.agent or "")
    elif act == "role-status":
        action_role_status(ai_root)
    elif act == "health-precheck":
        action_health_precheck(ai_root, args.needs, args.peer)
    elif act == "health-sweep":
        action_health_sweep(ai_root)
    elif act == "append-handoff":
        action_append_handoff(ai_root, args.section, args.text)
    elif act == "task-checkpoint":
        action_task_checkpoint(ai_root, args.task_id or (str(args.id) if args.id else ""), args.peer or args.agent or "unknown", args.msg or args.detail or "")
    elif act == "task-status":
        action_task_status(ai_root, args.task_id or (str(args.id) if args.id else None))
    elif act == "task-failover":
        action_task_failover(ai_root, args.task_id or (str(args.id) if args.id else ""), args.peer or args.agent or "", args.reason or args.detail or "")
    elif act == "approval-request":
        action_approval_request(ai_root, args.from_ or args.peer or args.agent or "unknown", args.subject or args.msg or "", args.auth_needed or "", args.scope or args.file_path or "", args.severity or "workspace-write", args.fallback or "")
    elif act == "file-lock":
        action_file_lock(ai_root, args.name or args.file_path or "", args.peer or args.agent or "", args.scope or args.section or "")
    elif act == "file-unlock":
        action_file_unlock(ai_root, args.name or args.file_path or "", args.peer or args.agent or "")
    elif act == "lock-status":
        action_lock_status(ai_root)
    elif act == "profile-validate":
        action_validate_profiles(args.peer or None)
    elif act == "lease-status":
        action_lease_status(ai_root)
    elif act == "lease-sweep":
        _lease_sweep(ai_root)
        print("[HUB] lease-sweep complete.")
    elif act == "model-status":
        action_model_status()
    elif act == "transient-scan":
        action_transient_scan(ai_root)

if __name__ == "__main__":
    main()
