"""
hub.py — Portable Dev Environment AI 협업 허브 (Facade 패턴)
11개 액션: Write 7개 (filelock) + Read 3개 (Lock-Free) + ask 1개 (동기 subprocess)

Raw Data 철학: --format llm 없음. 모든 출력은 손실 없는 Pretty-print Markdown.
단일 통로: msg.bat → hub.py %* (동기 ask + 비동기 send/check)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Windows 콘솔 UTF-8 강제 (CP949 차단)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ─────────────────────────────────────────────────────────────
# .ai/ 프로젝트 루트 탐색 (CWD → .git 상향, 없으면 CWD에 생성)
# ─────────────────────────────────────────────────────────────

def find_ai_root() -> Path:
    """CWD에서 시작해 .git/.ai를 찾아 상향 탐색. 없으면 CWD."""
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


def ensure_ai_dir(ai_root: Path) -> Path:
    """필요한 하위 폴더 및 초기 파일 생성."""
    (ai_root / ".lock").mkdir(parents=True, exist_ok=True)
    (ai_root / "sessions").mkdir(parents=True, exist_ok=True)
    if not (ai_root / "mailbox.json").exists():
        _write_json(ai_root / "mailbox.json", {"messages": [], "unread_count": 0})
    if not (ai_root / "state.json").exists():
        _write_json(ai_root / "state.json", {
            "pair": None, "claude_sid": None, "gemini_sid": None,
            "mission": None, "blocked": None, "phase": None,
            "updated_at": None
        })
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
# handoff.md FIFO 관리
# ─────────────────────────────────────────────────────────────

HANDOFF_MAX_CHARS = 12000
HANDOFF_MAX_COMPLETED = 5
HANDOFF_MAX_ISSUES = 3
HANDOFF_MAX_DECISIONS = 3


def _parse_handoff(text: str) -> dict:
    sections: dict[str, list[str]] = {
        "GOAL": [], "RECENT_COMPLETED": [], "PENDING_ISSUES": [], "KEY_DECISIONS": []
    }
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in ("## [GOAL]", "## [RECENT_COMPLETED]", "## [PENDING_ISSUES]", "## [KEY_DECISIONS]"):
            current = stripped[4:-1]
        elif current and stripped.startswith("- "):
            sections[current].append(stripped[2:])
    return sections


def _render_handoff(sections: dict) -> str:
    lines = ["## [GOAL]"]
    lines += [f"- {x}" for x in sections["GOAL"]] or ["- (목표 미설정)"]
    lines += ["\n## [RECENT_COMPLETED]"]
    lines += [f"- {x}" for x in sections["RECENT_COMPLETED"]] or ["- (없음)"]
    lines += ["\n## [PENDING_ISSUES]"]
    lines += [f"- {x}" for x in sections["PENDING_ISSUES"]] or ["- (없음)"]
    lines += ["\n## [KEY_DECISIONS]"]
    lines += [f"- {x}" for x in sections["KEY_DECISIONS"]] or ["- (없음)"]
    return "\n".join(lines) + "\n"


def _read_handoff(session_dir: Path) -> dict:
    path = session_dir / "handoff.md"
    if not path.exists():
        return {"GOAL": [], "RECENT_COMPLETED": [], "PENDING_ISSUES": [], "KEY_DECISIONS": []}
    return _parse_handoff(path.read_text(encoding="utf-8"))


def _write_handoff(session_dir: Path, sections: dict) -> None:
    sections["RECENT_COMPLETED"] = sections["RECENT_COMPLETED"][-HANDOFF_MAX_COMPLETED:]
    sections["PENDING_ISSUES"] = sections["PENDING_ISSUES"][-HANDOFF_MAX_ISSUES:]
    sections["KEY_DECISIONS"] = sections["KEY_DECISIONS"][-HANDOFF_MAX_DECISIONS:]
    text = _render_handoff(sections)
    while len(text) > HANDOFF_MAX_CHARS and sections["RECENT_COMPLETED"]:
        sections["RECENT_COMPLETED"].pop(0)
        text = _render_handoff(sections)
    (session_dir / "handoff.md").write_text(text, encoding="utf-8")


# ─────────────────────────────────────────────────────────────
# Write 액션 (filelock)
# ─────────────────────────────────────────────────────────────

def action_init_session(ai_root: Path, agent: str) -> None:
    """세션 초기화: SID 발급, pair 생성/합류. SID만 stdout 출력 (bat 캡처용)."""
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
    # SID만 출력 (gem.bat의 FOR /F 캡처 호환)
    print(sid)


def action_end_session(ai_root: Path, agent: str) -> None:
    """세션 종료: handoff.md 갱신, mailbox read 메시지 정리."""
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


def action_send(ai_root: Path, from_: str, to: str, msg: str) -> None:
    """비동기 메시지 발송."""
    with _get_lock(ai_root, "mailbox"):
        mb = _read_json(ai_root / "mailbox.json")
        msgs = mb.get("messages", [])
        new_id = len(msgs) + 1
        msgs.append({
            "id": new_id, "from": from_, "to": to,
            "content": msg, "status": "unread", "timestamp": _now()
        })
        mb["messages"] = msgs
        mb["unread_count"] = sum(1 for m in msgs if m.get("status") == "unread")
        _write_json(ai_root / "mailbox.json", mb)
    print(f"[SENT] {from_}→{to} | id={new_id}")


def action_mark_read(ai_root: Path, target: str, all_: bool, msg_id: int | None) -> None:
    """메시지 읽음 처리."""
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
    """Axis 실행 로그 기록 (.ai/log.jsonl)."""
    log_path = ai_root / "log.jsonl"
    entry = {"ts": _now(), "axis": axis, "script": script, "status": status, "detail": detail}
    with _get_lock(ai_root, "log"):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"[LOG] {axis} {script} → {status}")


def action_archive_file(ai_root: Path, name: str, file_path: str) -> None:
    """파일을 _archive/{name}-YYYYMMDD.json + {name}-latest.json으로 복사."""
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
    """미션·블로커·페이즈 상태 업데이트."""
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
# Read 액션 (Lock-Free) — Raw Pretty-print Markdown
# ─────────────────────────────────────────────────────────────

def action_check(ai_root: Path, target: str) -> None:
    """받은 메시지 전문을 Pretty-print Markdown으로 출력."""
    mb = _read_json(ai_root / "mailbox.json")
    msgs = mb.get("messages", [])
    unread = [m for m in msgs if m.get("to") == target and m.get("status") == "unread"]

    if not unread:
        print(f"### [INBOX] {target} — 새 메시지 없음")
        return

    print(f"### [INBOX] {target} — {len(unread)}개 미읽음\n")
    for m in unread:
        ts = m.get("timestamp", "")[:16]
        print(f"**[{m['id']}]** From: **{m['from']}** | {ts}")
        print()
        print(m["content"])
        print("\n---")


def action_status(ai_root: Path) -> None:
    """세션 상태 전체를 Pretty-print Markdown으로 출력."""
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

    pair = state.get("pair")
    if pair:
        handoff_path = ai_root / "sessions" / pair / "handoff.md"
        if handoff_path.exists():
            print()
            print("### [HANDOFF]")
            print(handoff_path.read_text(encoding="utf-8"))


def action_check_gate(ai_root: Path, agent: str) -> None:
    """게이트 확인: Gemini/Claude 가용 여부."""
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
# ask 액션 — 동기 subprocess (단일 통로의 동기 분기)
# ─────────────────────────────────────────────────────────────

def action_ask(to: str, query: str, query_file: str | None = None) -> None:
    """동기식 AI 질의: subprocess로 Gemini/Claude CLI 호출, Raw 응답 출력.
    --query-file 지정 시 파일을 읽어 쿼리로 사용하고 파일 자동 삭제 (구 consult-ai.bat 호환).
    """
    if query_file:
        qf = Path(query_file)
        if not qf.exists():
            print(f"[ERROR] query file not found: {query_file}", file=sys.stderr)
            sys.exit(1)
        query = qf.read_text(encoding="utf-8")
        qf.unlink()  # 응답 전 삭제 (consult-ai.bat 동작 유지)

    if to == "gemini":
        exe = shutil.which("gemini")
        if not exe:
            print("[ERROR] gemini CLI not found in PATH", file=sys.stderr)
            sys.exit(1)
        cmd = [exe, "-p", query, "-o", "text", "-y"]
    elif to == "claude":
        exe = shutil.which("claude")
        if not exe:
            print("[ERROR] claude CLI not found in PATH", file=sys.stderr)
            sys.exit(1)
        cmd = [exe, "-p", query]
    else:
        print(f"[ERROR] --to는 gemini 또는 claude만 허용", file=sys.stderr)
        sys.exit(1)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        output = _strip_ansi(result.stdout)
        if result.returncode != 0:
            err = _strip_ansi(result.stderr)
            print(f"[WARN] {to} exited {result.returncode}: {err[:200]}", file=sys.stderr)
        print(output.strip())
    except subprocess.TimeoutExpired:
        print("[ERROR] ask timeout (120s) — CLI가 응답하지 않음", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] ask 실패: {e}", file=sys.stderr)
        sys.exit(1)


# ─────────────────────────────────────────────────────────────
# CLI 진입점
# ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(prog="hub", description="AI 협업 허브 — 단일 통로")
    parser.add_argument("action", choices=[
        "init-session", "end-session", "send", "mark-read",
        "append-log", "archive-file", "update-status",
        "check", "status", "check-gate", "ask"
    ])
    parser.add_argument("--agent", choices=["claude", "gemini"])
    parser.add_argument("--from", dest="from_", metavar="AGENT")
    parser.add_argument("--to", dest="to_")
    parser.add_argument("--msg", dest="msg")
    parser.add_argument("--query", dest="query", default="")
    parser.add_argument("--query-file", dest="query_file", default=None)
    parser.add_argument("--target", dest="target")
    parser.add_argument("--all", dest="all_", action="store_true")
    parser.add_argument("--id", dest="msg_id", type=int)
    parser.add_argument("--axis", dest="axis")
    parser.add_argument("--script", dest="script")
    parser.add_argument("--status", dest="status_val")
    parser.add_argument("--detail", dest="detail", default="")
    parser.add_argument("--name", dest="name")
    parser.add_argument("--file", dest="file_path")
    parser.add_argument("--mission", dest="mission")
    parser.add_argument("--blocked", dest="blocked", default=None)
    parser.add_argument("--phase", dest="phase", default=None)
    args = parser.parse_args()

    # ask는 .ai/ 불필요
    if args.action == "ask":
        if not args.to_:
            print("[ERROR] --to 필수", file=sys.stderr); sys.exit(1)
        if not args.query and not args.query_file:
            print("[ERROR] --query 또는 --query-file 필수", file=sys.stderr); sys.exit(1)
        action_ask(args.to_, args.query, args.query_file)
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
            action_send(ai_root, args.from_, args.to_, args.msg)
        elif act == "mark-read":
            if not args.target:
                print("[ERROR] --target 필수", file=sys.stderr); sys.exit(1)
            action_mark_read(ai_root, args.target, args.all_, args.msg_id)
        elif act == "append-log":
            action_append_log(ai_root, args.axis or "", args.script or "", args.status_val or "", args.detail)
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
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
