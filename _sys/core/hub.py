"""
hub.py — Portable Dev Environment AI 협업 허브 (3TCP v1)
액션: Write 7개 (filelock) + Read 3개 (Lock-Free) + ask 1개 (동기) + consensus 3개 + node 2개

3TCP v1: nodes.json 기반 N-node 확장, timeout=None(무제한), 메시지 봉투 확장
단일 통로: msg.bat → hub.py %*
"""
from __future__ import annotations

import argparse
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


def _default_nodes() -> dict:
    return {
        "version": "1",
        "nodes": {
            "cc": {"tier": 1, "type": "orchestrator", "invoke": "claude",
                   "invoke_args": ["-p", "{query}"], "timeout": 0, "memory": "persistent"},
            "ca": {"tier": 2, "type": "agent",        "invoke": "claude",
                   "invoke_args": ["-p", "{query}"], "timeout": 0, "memory": "short-term"},
            "gc": {"tier": 3, "type": "sensor",       "invoke": "gemini",
                   "invoke_args": ["-p", "{query}", "-o", "text", "-y"], "timeout": 0, "memory": "session"},
        }
    }


def ensure_ai_dir(ai_root: Path) -> Path:
    (ai_root / ".lock").mkdir(parents=True, exist_ok=True)
    (ai_root / "sessions").mkdir(parents=True, exist_ok=True)
    (ai_root / "consensus").mkdir(parents=True, exist_ok=True)
    if not (ai_root / "mailbox.json").exists():
        _write_json(ai_root / "mailbox.json", {"messages": [], "unread_count": 0})
    if not (ai_root / "state.json").exists():
        _write_json(ai_root / "state.json", {
            "pair": None, "claude_sid": None, "gemini_sid": None,
            "mission": None, "blocked": None, "phase": None,
            "updated_at": None
        })
    if not (ai_root / "nodes.json").exists():
        _write_json(ai_root / "nodes.json", _default_nodes())
    return ai_root


# ─────────────────────────────────────────────────────────────
# JSON / 유틸리티
# ─────────────────────────────────────────────────────────────

def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _short_id(prefix: str = "") -> str:
    return prefix + uuid.uuid4().hex[:4]


def _strip_ansi(text: str) -> str:
    return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)


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
    """nodes.json 로드. 없으면 하드코딩 기본값 (하위 호환)."""
    nodes_path = ai_root / "nodes.json"
    if nodes_path.exists():
        data = _read_json(nodes_path)
        return data.get("nodes", {})
    # 하위 호환 기본값 (nodes.json 없을 때)
    return {
        "gemini": {"invoke": "gemini", "invoke_args": ["-p", "{query}", "-o", "text", "-y"]},
        "gc":     {"invoke": "gemini", "invoke_args": ["-p", "{query}", "-o", "text", "-y"]},
        "claude": {"invoke": "claude", "invoke_args": ["-p", "{query}"]},
        "cc":     {"invoke": "claude", "invoke_args": ["-p", "{query}"]},
        "ca":     {"invoke": "claude", "invoke_args": ["-p", "{query}"]},
    }


def _resolve_node_cmd(to: str, query: str, ai_root: Path | None) -> list[str]:
    """노드 ID → subprocess 명령어 리스트. 없으면 None."""
    if ai_root:
        nodes = _load_nodes(ai_root)
    else:
        nodes = {
            "gemini": {"invoke": "gemini", "invoke_args": ["-p", "{query}", "-o", "text", "-y"]},
            "gc":     {"invoke": "gemini", "invoke_args": ["-p", "{query}", "-o", "text", "-y"]},
            "claude": {"invoke": "claude", "invoke_args": ["-p", "{query}"]},
            "cc":     {"invoke": "claude", "invoke_args": ["-p", "{query}"]},
            "ca":     {"invoke": "claude", "invoke_args": ["-p", "{query}"]},
        }

    node = nodes.get(to)
    if node:
        exe_name = node.get("invoke", to)
        raw_args = node.get("invoke_args", ["-p", "{query}"])
        args = [a.replace("{query}", query) for a in raw_args]
    else:
        # 마지막 fallback: to 자체를 실행 파일명으로 사용
        exe_name = to
        args = ["-p", query]

    exe = shutil.which(exe_name)
    if not exe:
        print(f"[ERROR] {exe_name} CLI not found in PATH", file=sys.stderr)
        sys.exit(1)
    return [exe] + args


# ─────────────────────────────────────────────────────────────
# handoff.md FIFO 관리 (CONSENSUS_HISTORY + ACTIVE_THREADS 포함)
# ─────────────────────────────────────────────────────────────

HANDOFF_MAX_CHARS = 12000
HANDOFF_MAX_COMPLETED = 5
HANDOFF_MAX_ISSUES = 3
HANDOFF_MAX_DECISIONS = 3
HANDOFF_MAX_CONSENSUS = 10
HANDOFF_MAX_THREADS = 5

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
                sections[current].append(stripped[2:])
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
    sections["RECENT_COMPLETED"] = sections["RECENT_COMPLETED"][-HANDOFF_MAX_COMPLETED:]
    sections["PENDING_ISSUES"]   = sections["PENDING_ISSUES"][-HANDOFF_MAX_ISSUES:]
    sections["KEY_DECISIONS"]    = sections["KEY_DECISIONS"][-HANDOFF_MAX_DECISIONS:]
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

def action_init_session(ai_root: Path, agent: str) -> None:
    prefix = "c" if agent == "claude" else "g"
    sid = _short_id(prefix)
    with _get_lock(ai_root, "state"):
        state = _read_json(ai_root / "state.json")
        if agent == "claude":
            state["claude_sid"] = sid
        else:
            state["gemini_sid"] = sid
        c = state.get("claude_sid") or "c---"
        g = state.get("gemini_sid") or "g---"
        state["pair"] = f"{c}-{g}"
        state["updated_at"] = _now()
        _write_json(ai_root / "state.json", state)
    session_dir = ai_root / "sessions" / state["pair"]
    session_dir.mkdir(parents=True, exist_ok=True)
    print(sid)


def action_end_session(ai_root: Path, agent: str) -> None:
    with _get_lock(ai_root, "state"):
        state = _read_json(ai_root / "state.json")
        pair = state.get("pair")
        ts = _now()
        completed_entry = f"{ts[:10]} {agent}: 세션 종료"
        if agent == "claude":
            state["claude_sid"] = None
        else:
            state["gemini_sid"] = None
        state["updated_at"] = ts
        _write_json(ai_root / "state.json", state)
    if pair:
        session_dir = ai_root / "sessions" / pair
        session_dir.mkdir(parents=True, exist_ok=True)
        handoff = _read_handoff(session_dir)
        handoff["RECENT_COMPLETED"].append(completed_entry)
        _write_handoff(session_dir, handoff)
    with _get_lock(ai_root, "mailbox"):
        mb = _read_json(ai_root / "mailbox.json")
        msgs = [m for m in mb.get("messages", []) if m.get("status") != "read"]
        mb["messages"] = msgs
        mb["unread_count"] = sum(1 for m in msgs if m.get("status") == "unread")
        _write_json(ai_root / "mailbox.json", mb)
    print(f"[END] {agent} 세션 종료 완료")


def action_send(
    ai_root: Path, from_: str, to: str, msg: str,
    thread_id: str | None = None,
    msg_type: str = "MSG",
    cc_list: list[str] | None = None,
    ref_id: int | None = None,
) -> None:
    """비동기 메시지 발송 (3TCP 봉투 지원, 하위 호환)."""
    if cc_list is None:
        cc_list = []
    auto_thread = thread_id or _short_id("t-")
    with _get_lock(ai_root, "mailbox"):
        mb = _read_json(ai_root / "mailbox.json")
        msgs = mb.get("messages", [])
        new_id = len(msgs) + 1
        msgs.append({
            "id": new_id,
            "thread_id": auto_thread,
            "type": msg_type,
            "from": from_,
            "to": to,
            "cc": cc_list,
            "content": msg,
            "status": "unread",
            "timestamp": _now(),
            "ref": ref_id,
        })
        mb["messages"] = msgs
        mb["unread_count"] = sum(1 for m in msgs if m.get("status") == "unread")
        _write_json(ai_root / "mailbox.json", mb)
    cc_str = f" cc={','.join(cc_list)}" if cc_list else ""
    ref_str = f" ref={ref_id}" if ref_id else ""
    print(f"[HUB] SENT  {from_}→{to} | thread={auto_thread} | id={new_id} type={msg_type}{cc_str}{ref_str}")


def action_mark_read(ai_root: Path, target: str, all_: bool, msg_id: int | None) -> None:
    with _get_lock(ai_root, "mailbox"):
        mb = _read_json(ai_root / "mailbox.json")
        msgs = mb.get("messages", [])
        count = 0
        for m in msgs:
            if m.get("to") == target and m.get("status") == "unread":
                if all_ or m.get("id") == msg_id:
                    m["status"] = "read"
                    count += 1
        mb["unread_count"] = sum(1 for m in msgs if m.get("status") == "unread")
        _write_json(ai_root / "mailbox.json", mb)
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
    if not src.exists():
        print(f"[ERROR] 파일 없음: {file_path}", file=sys.stderr)
        sys.exit(1)
    archive_dir = ai_root.parent / "_archive"
    archive_dir.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    shutil.copy2(src, archive_dir / f"{name}-{date_str}.json")
    shutil.copy2(src, archive_dir / f"{name}-latest.json")
    print(f"[ARCHIVE] {name} → {name}-{date_str}.json + {name}-latest.json")


def action_update_status(ai_root: Path, mission: str, blocked: str | None, phase: str | None) -> None:
    with _get_lock(ai_root, "state"):
        state = _read_json(ai_root / "state.json")
        state["mission"] = mission
        if blocked is not None:
            state["blocked"] = blocked if blocked else None
        if phase is not None:
            state["phase"] = phase
        state["updated_at"] = _now()
        _write_json(ai_root / "state.json", state)
    print(f"[STATUS] mission={mission}")


# ─────────────────────────────────────────────────────────────
# Read 액션 (Lock-Free)
# ─────────────────────────────────────────────────────────────

def action_check(ai_root: Path, target: str) -> None:
    """받은 메시지 전문 출력 (cc 필드 포함 — 타 노드 참조 지원)."""
    mb = _read_json(ai_root / "mailbox.json")
    msgs = mb.get("messages", [])
    # to==target 또는 cc에 target 포함
    unread = [
        m for m in msgs
        if (m.get("to") == target or target in m.get("cc", []))
        and m.get("status") == "unread"
    ]
    if not unread:
        print(f"[HUB] READ  0 messages for {target} (inbox empty)")
        return
    type_counts: dict[str, int] = {}
    for m in unread:
        t = m.get("type", "MSG")
        type_counts[t] = type_counts.get(t, 0) + 1
    type_summary = " ".join(f"{t}×{n}" for t, n in type_counts.items())
    print(f"[HUB] READ  {len(unread)} messages for {target} ({type_summary})\n")
    for m in unread:
        ts = m.get("timestamp", "")[:16]
        thread = m.get("thread_id", "?")
        msg_type = m.get("type", "MSG")
        ref = m.get("ref")
        ref_str = f" ref={ref}" if ref else ""
        print(f"**[{m['id']}]** From: **{m['from']}** | {ts} | thread={thread} type={msg_type}{ref_str}")
        print()
        print(m["content"])
        print("\n---")


def action_status(ai_root: Path) -> None:
    state = _read_json(ai_root / "state.json")
    mb = _read_json(ai_root / "mailbox.json")
    msgs = mb.get("messages", [])
    unread_c = sum(1 for m in msgs if m.get("to") == "claude" and m.get("status") == "unread")
    unread_g = sum(1 for m in msgs if m.get("to") == "gemini" and m.get("status") == "unread")

    print("### [SESSION STATUS]")
    print(f"**Pair**: {state.get('pair') or '없음'}")
    print(f"**Mission**: {state.get('mission') or '없음'}")
    print(f"**Phase**: {state.get('phase') or '없음'}")
    print(f"**Blocked**: {state.get('blocked') or '없음'}")
    print(f"**Updated**: {state.get('updated_at') or '없음'}")
    print()
    print("### [MAILBOX]")
    print(f"claude: {unread_c} unread / gemini: {unread_g} unread")

    # 활성 consensus 라운드
    consensus_dir = ai_root / "consensus"
    if consensus_dir.exists():
        active = []
        for f in consensus_dir.glob("*.json"):
            r = _read_json(f)
            if r.get("status") == "voting":
                votes_in = sum(1 for v in r.get("votes", {}).values() if v is not None)
                total = len(r.get("voters", []))
                active.append(f"  - {r['round_id']}: {r.get('subject','?')} [{votes_in}/{total}]")
        if active:
            print()
            print("### [CONSENSUS — ACTIVE]")
            print("\n".join(active))

    pair = state.get("pair")
    if pair:
        handoff_path = ai_root / "sessions" / pair / "handoff.md"
        if handoff_path.exists():
            print()
            print("### [HANDOFF]")
            print(handoff_path.read_text(encoding="utf-8"))


def action_check_gate(ai_root: Path, agent: str) -> None:
    if agent == "gemini":
        status_path = Path(__file__).parent.parent / "gemini" / "status.json"
        if status_path.exists():
            data = _read_json(status_path)
            if data.get("mode") == "ON":
                print("[GATE] gemini=ON")
                sys.exit(0)
        print("[GATE] gemini=OFF")
        sys.exit(1)
    else:
        print(f"[GATE] {agent}=ON")
        sys.exit(0)


# ─────────────────────────────────────────────────────────────
# ask 액션 — 동기 subprocess (timeout=None 무제한)
# ─────────────────────────────────────────────────────────────

def action_ask(
    to: str,
    query: str,
    query_file: str | None = None,
    timeout_sec: int = 0,
    ai_root: Path | None = None,
) -> None:
    """동기식 AI 질의. timeout_sec=0 → 무제한(None)."""
    if query_file:
        qf = Path(query_file)
        if not qf.exists():
            print(f"[ERROR] query file not found: {query_file}", file=sys.stderr)
            sys.exit(1)
        query = qf.read_text(encoding="utf-8")
        qf.unlink()

    timeout = timeout_sec if timeout_sec > 0 else None
    timeout_label = "none" if timeout is None else f"{timeout}s"
    print(f"[HUB] ASK   cc→{to} | chars={len(query)} | timeout={timeout_label}")

    cmd = _resolve_node_cmd(to, query, ai_root)

    try:
        t0 = time.monotonic()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        elapsed = int(time.monotonic() - t0)
        output = _strip_ansi(result.stdout)
        if result.returncode != 0:
            err = _strip_ansi(result.stderr)
            print(f"[HUB:WARN] {to} exited {result.returncode}: {err[:200]}", file=sys.stderr)
        print(f"[HUB] REPLY {to}→cc | chars={len(output)} | elapsed={elapsed}s")
        print(output.strip())
    except subprocess.TimeoutExpired:
        print(f"[HUB:ERROR] ask timeout ({timeout}s) — CLI가 응답하지 않음", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[HUB:ERROR] ask 실패: {e}", file=sys.stderr)
        sys.exit(1)


# ─────────────────────────────────────────────────────────────
# Consensus 프로토콜 (§P-3)
# ─────────────────────────────────────────────────────────────

def action_consensus_propose(
    ai_root: Path,
    subject: str,
    voters: list[str],
    proposed_by: str = "cc",
) -> None:
    """만장일치 협의 라운드 생성."""
    round_id = _short_id("r-")
    data = {
        "round_id": round_id,
        "subject": subject,
        "proposed_by": proposed_by,
        "proposed_at": _now(),
        "status": "voting",
        "voters": voters,
        "votes": {v: None for v in voters},
        "outcome": None,
        "outcome_at": None,
    }
    rpath = ai_root / "consensus" / f"{round_id}.json"
    _write_json(rpath, data)
    print(f"[HUB] PROPOSE {round_id} | subject={subject} | voters={','.join(voters)}")


def action_consensus_vote(
    ai_root: Path,
    round_id: str,
    voter: str,
    vote_val: str,
    reason: str = "",
) -> None:
    """투표 기록. 전원 agree → FINALIZED, disagree → ESCALATED."""
    rpath = ai_root / "consensus" / f"{round_id}.json"
    if not rpath.exists():
        print(f"[HUB:ERROR] consensus round not found: {round_id}", file=sys.stderr)
        sys.exit(1)
    with _get_lock(ai_root, f"consensus_{round_id}"):
        data = _read_json(rpath)
        if data.get("status") != "voting":
            print(f"[HUB:ERROR] round {round_id} is already {data.get('status')}", file=sys.stderr)
            sys.exit(1)
        if voter not in data.get("voters", []):
            print(f"[HUB:ERROR] voter {voter} not in voters list", file=sys.stderr)
            sys.exit(1)
        votes = data.get("votes", {})
        votes[voter] = {"vote": vote_val, "reason": reason, "ts": _now()}
        data["votes"] = votes

        # 집계
        total = len(data["voters"])
        cast = sum(1 for v in votes.values() if v is not None)
        print(f"[HUB] VOTE   {round_id}  | voter={voter} {vote_val} | {cast}/{total}")

        if cast == total:
            # 전원 투표 완료 — 결과 판정
            if all(v["vote"] == "agree" for v in votes.values()):
                data["status"] = "finalized"
                data["outcome"] = "unanimous"
                data["outcome_at"] = _now()
                _write_json(rpath, data)
                print(f"[HUB] DECISION {round_id} FINALIZED | unanimous")
                # handoff.md CONSENSUS_HISTORY 기록
                _append_consensus_history(ai_root, round_id, data["subject"], "FINALIZED")
            elif any(v["vote"] == "disagree" for v in votes.values() if v):
                data["status"] = "escalated"
                data["outcome"] = "human_gate"
                data["outcome_at"] = _now()
                _write_json(rpath, data)
                print(f"[HUB] DECISION {round_id} ESCALATED | human gate required")
            else:
                # abstain만 있는 경우 finalized(abstain)
                data["status"] = "finalized"
                data["outcome"] = "abstain"
                data["outcome_at"] = _now()
                _write_json(rpath, data)
                print(f"[HUB] DECISION {round_id} FINALIZED | abstain")
        else:
            _write_json(rpath, data)


def _append_consensus_history(ai_root: Path, round_id: str, subject: str, outcome: str) -> None:
    state = _read_json(ai_root / "state.json")
    pair = state.get("pair")
    if not pair:
        return
    session_dir = ai_root / "sessions" / pair
    session_dir.mkdir(parents=True, exist_ok=True)
    handoff = _read_handoff(session_dir)
    entry = f"{round_id}: {subject} — {outcome} {_now()[:10]}"
    handoff.setdefault("CONSENSUS_HISTORY", []).append(entry)
    _write_handoff(session_dir, handoff)


def action_consensus_check(ai_root: Path, round_id: str | None = None) -> None:
    """특정 라운드 또는 모든 라운드 상태 출력."""
    consensus_dir = ai_root / "consensus"
    if not consensus_dir.exists():
        print("### [CONSENSUS] — 기록 없음")
        return

    if round_id:
        rpath = consensus_dir / f"{round_id}.json"
        if not rpath.exists():
            print(f"[HUB:ERROR] round not found: {round_id}", file=sys.stderr)
            sys.exit(1)
        rounds = [_read_json(rpath)]
    else:
        rounds = [_read_json(f) for f in sorted(consensus_dir.glob("*.json"))]

    if not rounds:
        print("### [CONSENSUS] — 기록 없음")
        return

    for r in rounds:
        rid = r.get("round_id", "?")
        status = r.get("status", "?")
        subject = r.get("subject", "?")
        voters = r.get("voters", [])
        votes = r.get("votes", {})
        cast = sum(1 for v in votes.values() if v is not None)
        print(f"\n### [{rid}] {status.upper()}")
        print(f"Subject: {subject}")
        print(f"Voters: {', '.join(voters)} | Votes: {cast}/{len(voters)}")
        for voter, v in votes.items():
            if v:
                print(f"  - {voter}: {v['vote']} — {v.get('reason','')}")
            else:
                print(f"  - {voter}: (미투표)")
        if r.get("outcome"):
            print(f"Outcome: {r['outcome']} @ {r.get('outcome_at','')}")


# ─────────────────────────────────────────────────────────────
# Node 관리 액션 (§P-7)
# ─────────────────────────────────────────────────────────────

def action_register_node(
    ai_root: Path,
    node_id: str,
    tier: int,
    node_type: str,
    invoke: str,
    invoke_args_str: str,
    memory: str,
    timeout_sec: int = 0,
) -> None:
    """노드를 nodes.json에 등록/갱신."""
    with _get_lock(ai_root, "nodes"):
        data = _read_json(ai_root / "nodes.json")
        if "nodes" not in data:
            data = _default_nodes()
        invoke_args = invoke_args_str.split(",") if invoke_args_str else ["-p", "{query}"]
        data["nodes"][node_id] = {
            "tier": tier,
            "type": node_type,
            "invoke": invoke,
            "invoke_args": invoke_args,
            "timeout": timeout_sec,
            "memory": memory,
        }
        _write_json(ai_root / "nodes.json", data)
    print(f"[HUB] REGISTER node={node_id} tier={tier} type={node_type} invoke={invoke}")


def action_list_nodes(ai_root: Path) -> None:
    """등록된 노드 목록 출력."""
    data = _read_json(ai_root / "nodes.json")
    nodes = data.get("nodes", {})
    print(f"### [NODES] v{data.get('version','?')} — {len(nodes)}개 등록\n")
    for nid, n in nodes.items():
        t_val = n.get('timeout', 0)
        t_str = 'none' if t_val == 0 else f"{t_val}s"
        print(f"**{nid}** (Tier {n.get('tier','?')} {n.get('type','?')}) "
              f"invoke={n.get('invoke','?')} memory={n.get('memory','?')} "
              f"timeout={t_str}")


# ─────────────────────────────────────────────────────────────
# CLI 진입점
# ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(prog="hub", description="AI 협업 허브 — 3TCP v1")
    parser.add_argument("action", choices=[
        # 기존 11개
        "init-session", "end-session", "send", "mark-read",
        "append-log", "archive-file", "update-status",
        "check", "status", "check-gate", "ask",
        # 신규: consensus 3개
        "consensus-propose", "consensus-vote", "consensus-check",
        # 신규: node 2개
        "register-node", "list-nodes",
    ])
    # 기존 옵션
    parser.add_argument("--agent",   choices=["claude", "gemini"])
    parser.add_argument("--from",    dest="from_", metavar="AGENT")
    parser.add_argument("--to",      dest="to_")
    parser.add_argument("--msg",     dest="msg")
    parser.add_argument("--query",   dest="query", default="")
    parser.add_argument("--query-file", dest="query_file", default=None)
    parser.add_argument("--target",  dest="target")
    parser.add_argument("--all",     dest="all_", action="store_true")
    parser.add_argument("--id",      dest="msg_id", type=int)
    parser.add_argument("--axis",    dest="axis")
    parser.add_argument("--script",  dest="script")
    parser.add_argument("--status",  dest="status_val")
    parser.add_argument("--detail",  dest="detail", default="")
    parser.add_argument("--name",    dest="name")
    parser.add_argument("--file",    dest="file_path")
    parser.add_argument("--mission", dest="mission")
    parser.add_argument("--blocked", dest="blocked", default=None)
    parser.add_argument("--phase",   dest="phase", default=None)
    # 신규: 메시지 봉투 (§P-2)
    parser.add_argument("--thread-id", dest="thread_id", default=None)
    parser.add_argument("--type",      dest="msg_type", default="MSG")
    parser.add_argument("--cc",        dest="cc_str", default="")
    parser.add_argument("--ref",       dest="ref_id", type=int, default=None)
    # 신규: ask 타임아웃 (§P-A)
    parser.add_argument("--timeout",   dest="timeout_sec", type=int, default=0)
    # 신규: consensus (§P-3)
    parser.add_argument("--round-id",  dest="round_id", default=None)
    parser.add_argument("--subject",   dest="subject", default=None)
    parser.add_argument("--voters",    dest="voters", default=None)
    parser.add_argument("--voter",     dest="voter", default=None)
    parser.add_argument("--vote",      dest="vote_val", choices=["agree", "disagree", "abstain"], default=None)
    parser.add_argument("--reason",    dest="reason", default="")
    # 신규: register-node (§P-7)
    parser.add_argument("--tier",         dest="tier", type=int, default=2)
    parser.add_argument("--node-type",    dest="node_type", default="agent")
    parser.add_argument("--invoke",       dest="invoke", default=None)
    parser.add_argument("--invoke-args",  dest="invoke_args_str", default="-p,{query}")
    parser.add_argument("--memory",       dest="memory", default="short-term")

    args = parser.parse_args()

    # ask는 .ai/ 불필요 (단, nodes.json 참조를 위해 ai_root 탐색 시도)
    if args.action == "ask":
        if not args.to_:
            print("[ERROR] --to 필수", file=sys.stderr); sys.exit(1)
        if not args.query and not args.query_file:
            print("[ERROR] --query 또는 --query-file 필수", file=sys.stderr); sys.exit(1)
        try:
            ai_root_opt: Path | None = find_ai_root()
        except Exception:
            ai_root_opt = None
        action_ask(args.to_, args.query, args.query_file, args.timeout_sec, ai_root_opt)
        return

    ai_root = find_ai_root()
    ensure_ai_dir(ai_root)

    act = args.action
    try:
        if act == "init-session":
            action_init_session(ai_root, args.agent or "claude")
        elif act == "end-session":
            action_end_session(ai_root, args.agent or "claude")
        elif act == "send":
            if not args.from_ or not args.to_ or not args.msg:
                print("[ERROR] --from, --to, --msg 필수", file=sys.stderr); sys.exit(1)
            cc_list = [x.strip() for x in args.cc_str.split(",") if x.strip()] if args.cc_str else []
            action_send(ai_root, args.from_, args.to_, args.msg,
                        args.thread_id, args.msg_type, cc_list, args.ref_id)
        elif act == "mark-read":
            if not args.target:
                print("[ERROR] --target 필수", file=sys.stderr); sys.exit(1)
            action_mark_read(ai_root, args.target, args.all_, args.msg_id)
        elif act == "append-log":
            action_append_log(ai_root, args.axis or "", args.script or "",
                              args.status_val or "", args.detail)
        elif act == "archive-file":
            if not args.name or not args.file_path:
                print("[ERROR] --name, --file 필수", file=sys.stderr); sys.exit(1)
            action_archive_file(ai_root, args.name, args.file_path)
        elif act == "update-status":
            if not args.mission:
                print("[ERROR] --mission 필수", file=sys.stderr); sys.exit(1)
            action_update_status(ai_root, args.mission, args.blocked, args.phase)
        elif act == "check":
            if not args.target:
                print("[ERROR] --target 필수", file=sys.stderr); sys.exit(1)
            action_check(ai_root, args.target)
        elif act == "status":
            action_status(ai_root)
        elif act == "check-gate":
            action_check_gate(ai_root, args.agent or "gemini")
        # ── Consensus (§P-3) ──
        elif act == "consensus-propose":
            if not args.subject:
                print("[ERROR] --subject 필수", file=sys.stderr); sys.exit(1)
            voters = [v.strip() for v in (args.voters or "cc,ca,gc").split(",") if v.strip()]
            action_consensus_propose(ai_root, args.subject, voters)
        elif act == "consensus-vote":
            if not args.round_id or not args.voter or not args.vote_val:
                print("[ERROR] --round-id, --voter, --vote 필수", file=sys.stderr); sys.exit(1)
            action_consensus_vote(ai_root, args.round_id, args.voter, args.vote_val, args.reason)
        elif act == "consensus-check":
            action_consensus_check(ai_root, args.round_id)
        # ── Node 관리 (§P-7) ──
        elif act == "register-node":
            if not args.to_ or not args.invoke:
                print("[ERROR] --to (node_id), --invoke 필수", file=sys.stderr); sys.exit(1)
            action_register_node(ai_root, args.to_, args.tier, args.node_type,
                                 args.invoke, args.invoke_args_str, args.memory, args.timeout_sec)
        elif act == "list-nodes":
            action_list_nodes(ai_root)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
