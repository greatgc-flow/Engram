"""TDD contract for Codex rate-limit reset credits.

Every app-server process/client is mocked. Never add a real-account consume
test here: redemption is irreversible and manual-only.
"""
import json
import sys
import time
import uuid
from pathlib import Path

import pytest


SYS_DIR = Path(__file__).resolve().parent.parent.parent  # _sys/
if str(SYS_DIR / "core") not in sys.path:
    sys.path.insert(0, str(SYS_DIR / "core"))
if str(SYS_DIR) not in sys.path:
    sys.path.insert(0, str(SYS_DIR))

import snapshot  # noqa: E402
import core.hub as hub  # noqa: E402


_UNSET = object()
_NOW = 2_000_000_000
_CREDIT_ID = "credit-available-1"
_IDEMPOTENCY_KEY = "12345678-1234-4234-8234-123456789abc"


def _credit(
    credit_id=_CREDIT_ID,
    *,
    status="available",
    expires_at=None,
    granted_at=1_999_000_000,
):
    return {
        "id": credit_id,
        "grantedAt": granted_at,
        "resetType": "codexRateLimits",
        "status": status,
        "expiresAt": expires_at,
        "title": "Reset Codex limit",
        "description": "mocked test credit",
    }


def _result(credit_state=_UNSET, *, used_percent=25):
    result = {
        "rateLimits": {
            "primary": {
                "usedPercent": used_percent,
                "resetsAt": _NOW + 3600,
                "windowDurationMins": 300,
            },
        },
        "rateLimitsByLimitId": None,
    }
    if credit_state is not _UNSET:
        result["rateLimitResetCredits"] = credit_state
    return result


def _summary(available_count=1, credits=None):
    return {
        "availableCount": available_count,
        "credits": credits,
    }


class _RecordingStdin:
    def __init__(self):
        self.writes = []

    def write(self, text):
        self.writes.append(text)

    def flush(self):
        return None


class _LineReader:
    def __init__(self, lines):
        self._lines = iter(lines)

    def readline(self):
        return next(self._lines, "")


class _FakeAppServer:
    def __init__(self, lines):
        self.stdin = _RecordingStdin()
        self.stdout = _LineReader(lines)
        self.pid = 424242

    def poll(self):
        return None


class _BlockingReader:
    def readline(self):
        time.sleep(0.20)
        return ""


class _BlockingAppServer:
    def __init__(self):
        self.stdin = _RecordingStdin()
        self.stdout = _BlockingReader()
        self.pid = 515151

    def poll(self):
        return None


class _FakeCreditClient:
    """Fully in-memory client used by all action tests."""

    def __init__(self, reads, outcome=None):
        self.reads = list(reads)
        self.outcome = outcome
        self.read_calls = 0
        self.consume_calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read_rate_limits(self):
        self.read_calls += 1
        if not self.reads:
            raise AssertionError("unexpected extra rate-limit read")
        item = self.reads.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    def consume_reset_credit(self, *, credit_id, idempotency_key):
        self.consume_calls.append(
            {"credit_id": credit_id, "idempotency_key": idempotency_key}
        )
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return {"outcome": self.outcome}


def _install_client(monkeypatch, client, audits=None):
    monkeypatch.setattr(
        hub,
        "CodexAccountClient",
        lambda *_args, **_kwargs: client,
        raising=False,
    )
    if audits is not None:
        monkeypatch.setattr(
            hub,
            "_audit_credit_step",
            lambda step, credit_id, key, *args, **kwargs: audits.append(
                {
                    "step": step,
                    "credit_id": credit_id,
                    "idempotency_key": key,
                    "args": args,
                    "kwargs": kwargs,
                }
            ),
            raising=False,
        )
    # staticmethod is required here: a plain function assigned into a class
    # dict binds as an instance method on attribute access, so hub.time.time()
    # would implicitly pass `self` to this zero-arg lambda and raise TypeError
    # (caught while making action_credit_consume's preflight expiry check --
    # which legitimately calls time.time() -- pass against this fixture).
    monkeypatch.setattr(
        hub, "time", type("_Time", (), {"time": staticmethod(lambda: _NOW)})(), raising=False
    )


def _consume(*, credit_id=_CREDIT_ID, confirm=True, key=_IDEMPOTENCY_KEY, origin="terminal"):
    return hub.action_credit_consume(
        "cx",
        credit_id,
        confirm=confirm,
        idempotency_key=key,
        as_json=True,
        origin=origin,
    )


def test_eligible_reset_credits_counts_only_available_unexpired_applicable():
    """Feeds diag's EFF EXH field (2026-07-22 follow-up): only status=
    'available', not-expired, resetType='codexRateLimits' credits count."""
    credits = [
        _credit("c-ok-1", status="available"),
        _credit("c-ok-2", status="available"),
        _credit("c-redeemed", status="redeemed"),
        _credit("c-expired", status="available", expires_at=1),  # epoch 1970: always in the past
        {**_credit("c-wrong-type", status="available"), "resetType": "unknown"},
    ]
    assert snapshot._eligible_reset_credits(_summary(5, credits)) == 2


def test_eligible_reset_credits_returns_none_not_zero_for_missing_data():
    """None (not 0) when the list itself is absent/null -- diag must render
    the literal 'absent', never a guessed/fabricated count."""
    assert snapshot._eligible_reset_credits(None) is None
    assert snapshot._eligible_reset_credits(_summary(1, None)) is None
    assert snapshot._eligible_reset_credits(_summary(0, [])) == 0


def test_eligible_reset_credits_returns_none_when_list_is_capped():
    """cx.effort's finding: a `credits` array shorter than `availableCount`
    is a partial/capped view (design doc §2.1) -- counting eligibility over
    it could silently undercount real eligible credits sitting outside the
    cap. Must return None (unknown), never the visible-subset count."""
    capped = _summary(99, [_credit()])  # 1 visible row, 99 claimed available
    assert snapshot._eligible_reset_credits(capped) is None

    # Not capped: visible list length matches availableCount exactly.
    exact = _summary(1, [_credit()])
    assert snapshot._eligible_reset_credits(exact) == 1


def test_codex_rate_limits_retains_complete_result_and_quota_consumer_gets_only_rate_limits(
    monkeypatch,
):
    complete = _result(_summary(1, [_credit()]))

    proc = _FakeAppServer(
        [
            json.dumps({"id": 0, "result": {"serverInfo": {"name": "codex"}}}) + "\n",
            json.dumps({"id": 1, "result": complete}) + "\n",
        ]
    )
    killed = []
    monkeypatch.setattr(snapshot, "_codex_binary", lambda: "mock-codex")
    monkeypatch.setattr(snapshot.subprocess, "Popen", lambda *_a, **_kw: proc)
    monkeypatch.setattr(snapshot, "_kill_process_tree_windows", killed.append)

    actual = snapshot._codex_rate_limits(deadline_sec=0.2)

    assert actual == complete
    assert actual["rateLimitResetCredits"]["availableCount"] == 1
    assert snapshot._codex_quota_buckets(actual["rateLimits"])
    assert killed == [424242]


@pytest.mark.parametrize(
    ("credit_state", "expected_kind"),
    [
        (_UNSET, "missing"),
        (None, "null"),
        (_summary(0, []), "object"),
    ],
)
def test_rate_limit_result_preserves_missing_null_and_object_credit_states(
    monkeypatch, credit_state, expected_kind
):
    complete = _result() if credit_state is _UNSET else _result(credit_state)
    monkeypatch.setattr(snapshot, "_codex_rate_limits", lambda: complete)
    snapshot._CODEX_RATE_LIMIT_CACHE.clear()

    actual = snapshot._cached_codex_rate_limits(clock=lambda: 100.0)

    if expected_kind == "missing":
        assert "rateLimitResetCredits" not in actual
    elif expected_kind == "null":
        assert actual["rateLimitResetCredits"] is None
    else:
        assert actual["rateLimitResetCredits"] == {"availableCount": 0, "credits": []}


def test_cached_codex_rate_limits_keeps_complete_shape_and_honors_ttl(monkeypatch):
    calls = []
    first_result = _result(_summary(2, [_credit(), _credit("credit-2")]))
    second_result = _result(_summary(1, [_credit("credit-2")]))

    def fetch():
        calls.append("fetch")
        return first_result if len(calls) == 1 else second_result

    monkeypatch.setattr(snapshot, "_codex_rate_limits", fetch)
    snapshot._CODEX_RATE_LIMIT_CACHE.clear()

    first = snapshot._cached_codex_rate_limits(ttl_sec=60, clock=lambda: 100.0)
    cached = snapshot._cached_codex_rate_limits(ttl_sec=60, clock=lambda: 159.0)
    refreshed = snapshot._cached_codex_rate_limits(ttl_sec=60, clock=lambda: 160.0)

    assert first is cached
    assert refreshed is second_result
    assert refreshed["rateLimitResetCredits"]["availableCount"] == 1
    assert calls == ["fetch", "fetch"]


def test_rate_limit_rpc_uses_exact_initialize_initialized_and_read_framing(monkeypatch):
    complete = _result(_summary(1, [_credit()]))
    proc = _FakeAppServer(
        [
            json.dumps({"id": 0, "result": {"serverInfo": {"name": "codex"}}}) + "\n",
            json.dumps({"id": 1, "result": complete}) + "\n",
        ]
    )
    monkeypatch.setattr(snapshot, "_codex_binary", lambda: "mock-codex")
    monkeypatch.setattr(snapshot.subprocess, "Popen", lambda *_a, **_kw: proc)
    monkeypatch.setattr(snapshot, "_kill_process_tree_windows", lambda _pid: None)

    assert snapshot._codex_rate_limits(deadline_sec=0.2) == complete

    assert len(proc.stdin.writes) == 3
    initialize, initialized, read = map(json.loads, proc.stdin.writes)

    assert initialize == {
        "id": 0,
        "method": "initialize",
        "params": {
            "clientInfo": {"name": "hub-credit", "version": "1.0"},
            "capabilities": {"experimentalApi": True},
        },
    }
    assert initialized == {"method": "initialized"}
    assert read == {
        "id": 1,
        "method": "account/rateLimits/read",
        "params": None,
    }


def test_rate_limit_rpc_deadline_cleans_up_process_tree(monkeypatch):
    proc = _BlockingAppServer()
    killed = []
    monkeypatch.setattr(snapshot, "_codex_binary", lambda: "mock-codex")
    monkeypatch.setattr(snapshot.subprocess, "Popen", lambda *_a, **_kw: proc)
    monkeypatch.setattr(snapshot, "_kill_process_tree_windows", killed.append)

    started = time.monotonic()
    assert snapshot._codex_rate_limits(deadline_sec=0.03) is None

    assert time.monotonic() - started < 0.15
    assert killed == [515151]


@pytest.mark.parametrize(
    ("label", "preflight", "allowed"),
    [
        ("missing-summary", _result(), False),
        ("null-summary", _result(None), False),
        ("detail-list-null", _result(_summary(1, None)), False),
        ("empty-detail-list", _result(_summary(0, [])), False),
        (
            "capped-detail-list-still-permits-selected-credit",
            _result(_summary(99, [_credit()])),
            True,
        ),
        (
            "expired-credit",
            _result(_summary(1, [_credit(expires_at=_NOW - 1)])),
            False,
        ),
        (
            "unknown-credit-status",
            _result(_summary(1, [_credit(status="unknown")])),
            False,
        ),
        (
            "redeemed-credit-status",
            _result(_summary(0, [_credit(status="redeemed")])),
            False,
        ),
        (
            "available-credit",
            _result(_summary(1, [_credit(status="available")])),
            True,
        ),
    ],
)
def test_credit_preflight_handles_every_credit_list_state(
    monkeypatch, label, preflight, allowed
):
    post = _result(_summary(0, []))
    client = _FakeCreditClient([preflight, post], outcome="reset")
    _install_client(monkeypatch, client)

    if allowed:
        assert _consume() is None, label
        assert client.consume_calls == [
            {"credit_id": _CREDIT_ID, "idempotency_key": _IDEMPOTENCY_KEY}
        ]
    else:
        with pytest.raises(SystemExit) as exc:
            _consume()
        assert exc.value.code == 3, label
        assert client.consume_calls == []


def test_worker_origin_is_rejected_before_client_construction(monkeypatch):
    constructed = []
    monkeypatch.setattr(
        hub,
        "CodexAccountClient",
        lambda *_a, **_kw: constructed.append("constructed"),
        raising=False,
    )

    with pytest.raises(SystemExit) as exc:
        _consume(origin="worker")

    assert exc.value.code == 3
    assert constructed == []


@pytest.mark.parametrize(
    ("peer", "credit_id", "confirm"),
    [
        (None, _CREDIT_ID, True),
        ("", _CREDIT_ID, True),
        ("cx", None, True),
        ("cx", "", True),
        ("cx", _CREDIT_ID, False),
    ],
)
def test_credit_consume_rejects_missing_peer_credit_id_or_confirm(
    monkeypatch, peer, credit_id, confirm
):
    client = _FakeCreditClient([], outcome="reset")
    _install_client(monkeypatch, client)

    with pytest.raises(SystemExit) as exc:
        hub.action_credit_consume(
            peer,
            credit_id,
            confirm=confirm,
            idempotency_key=_IDEMPOTENCY_KEY,
            as_json=True,
            origin="terminal",
        )

    assert exc.value.code == 3
    assert client.consume_calls == []


def test_credit_consume_rejects_noncanonical_idempotency_key(monkeypatch):
    client = _FakeCreditClient([_result(_summary(1, [_credit()]))], outcome="reset")
    _install_client(monkeypatch, client)

    with pytest.raises(SystemExit) as exc:
        _consume(key="not-a-uuid")

    assert exc.value.code == 3
    assert client.consume_calls == []


def test_credit_consume_generates_one_uuid_audits_intent_and_reuses_it_after_timeout(
    monkeypatch,
):
    generated = uuid.UUID(_IDEMPOTENCY_KEY)
    audits = []
    first = _FakeCreditClient(
        [_result(_summary(1, [_credit()]))],
        outcome=TimeoutError("ambiguous transport timeout"),
    )
    _install_client(monkeypatch, first, audits=audits)
    # staticmethod: see the matching note in _install_client -- a plain
    # function in a class dict binds as an instance method, so hub.uuid.uuid4()
    # would implicitly pass `self` to this zero-arg lambda.
    monkeypatch.setattr(
        hub,
        "uuid",
        type("_Uuid", (), {"uuid4": staticmethod(lambda: generated)})(),
        raising=False,
    )

    with pytest.raises(SystemExit) as exc:
        _consume(key=None)
    assert exc.value.code == 1

    assert first.consume_calls == [
        {"credit_id": _CREDIT_ID, "idempotency_key": _IDEMPOTENCY_KEY}
    ]
    assert audits[0]["step"] == "intent"
    assert audits[0]["credit_id"] == _CREDIT_ID
    assert audits[0]["idempotency_key"] == _IDEMPOTENCY_KEY

    second = _FakeCreditClient(
        [
            _result(_summary(1, [_credit()])),
            _result(_summary(0, [])),
        ],
        outcome="reset",
    )
    _install_client(monkeypatch, second, audits=[])

    assert _consume(key=_IDEMPOTENCY_KEY) is None
    assert second.consume_calls == [
        {"credit_id": _CREDIT_ID, "idempotency_key": _IDEMPOTENCY_KEY}
    ]


@pytest.mark.parametrize(
    ("outcome", "post", "expected_exit"),
    [
        ("reset", _result(_summary(0, [])), None),
        (
            "alreadyRedeemed",
            _result(_summary(0, [_credit(status="redeemed")])),
            None,
        ),
        ("nothingToReset", _result(_summary(1, [_credit()])), 2),
        ("noCredit", _result(_summary(1, [_credit()])), 2),
    ],
)
def test_credit_consume_sends_exact_params_and_handles_all_backend_outcomes(
    monkeypatch, outcome, post, expected_exit
):
    client = _FakeCreditClient(
        [_result(_summary(1, [_credit()])), post],
        outcome=outcome,
    )
    _install_client(monkeypatch, client)

    if expected_exit is None:
        assert _consume() is None
    else:
        with pytest.raises(SystemExit) as exc:
            _consume()
        assert exc.value.code == expected_exit

    assert client.consume_calls == [
        {"credit_id": _CREDIT_ID, "idempotency_key": _IDEMPOTENCY_KEY}
    ]


def test_reset_requires_post_verification_count_decrement_and_credit_transition(monkeypatch):
    client = _FakeCreditClient(
        [
            _result(_summary(1, [_credit()])),
            _result(_summary(1, [_credit(status="available")])),
        ],
        outcome="reset",
    )
    _install_client(monkeypatch, client)

    with pytest.raises(SystemExit) as exc:
        _consume()

    assert exc.value.code == 1
    assert client.consume_calls


def test_successful_consume_with_unreadable_post_state_is_verification_pending(
    monkeypatch, capsys
):
    client = _FakeCreditClient(
        [
            _result(_summary(1, [_credit()])),
            TimeoutError("post-verification transport failure"),
        ],
        outcome="reset",
    )
    _install_client(monkeypatch, client)

    with pytest.raises(SystemExit) as exc:
        _consume()

    assert exc.value.code == 1
    assert "consume_succeeded_verification_pending" in capsys.readouterr().out
    assert client.consume_calls == [
        {"credit_id": _CREDIT_ID, "idempotency_key": _IDEMPOTENCY_KEY}
    ]


@pytest.mark.parametrize(
    "credit_state",
    [
        _UNSET,
        None,
        _summary(0, []),
        _summary(1, [_credit()]),
    ],
)
def test_credit_status_reads_only_and_preserves_credit_state(
    monkeypatch, capsys, credit_state
):
    result = _result() if credit_state is _UNSET else _result(credit_state)
    client = _FakeCreditClient([result], outcome=AssertionError("status must not consume"))
    _install_client(monkeypatch, client)

    assert hub.action_credit_status("cx", as_json=True) is None

    rendered = json.loads(capsys.readouterr().out)
    if credit_state is _UNSET:
        assert "rateLimitResetCredits" not in rendered
    else:
        assert rendered["rateLimitResetCredits"] == credit_state
    assert client.consume_calls == []


def test_quota_refresh_rpc_never_contains_consume_method(monkeypatch):
    complete = _result(_summary(1, [_credit()]))
    proc = _FakeAppServer(
        [
            json.dumps({"id": 0, "result": {}}) + "\n",
            json.dumps({"id": 1, "result": complete}) + "\n",
        ]
    )
    monkeypatch.setattr(snapshot, "_codex_binary", lambda: "mock-codex")
    monkeypatch.setattr(snapshot.subprocess, "Popen", lambda *_a, **_kw: proc)
    monkeypatch.setattr(snapshot, "_kill_process_tree_windows", lambda _pid: None)

    snapshot._codex_rate_limits(deadline_sec=0.2)

    outbound = "\n".join(proc.stdin.writes)
    assert "account/rateLimitResetCredit/consume" not in outbound


def test_diag_sweeps_and_snapshot_refresh_have_no_automatic_redemption_path():
    """Read-only telemetry must never gain an implicit irreversible action."""
    snapshot_source = Path(snapshot.__file__).read_text(encoding="utf-8")
    diag_source = (SYS_DIR / "cli" / "diag.py").read_text(encoding="utf-8")

    assert "rateLimitResetCredit/consume" not in snapshot_source
    assert "rateLimitResetCredit/consume" not in diag_source


@pytest.mark.skip(
    reason=(
        "MANUAL ONLY: real account status/credit redemption is irreversible and "
        "must never execute in CI or a normal pytest run."
    )
)
def test_manual_real_account_reset_credit_flow_is_never_a_ci_test():
    pytest.fail("manual-only placeholder")
