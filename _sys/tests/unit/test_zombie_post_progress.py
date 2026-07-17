"""Post-progress zombie tightening (2026-07-17 closure review round 2).

4/5 peer voices (ag.effort, ag.deepthink, cx.effort, cx.deepthink -- cc.fable
did not complete) independently converged on tightening the silence-kill
window to ~300s once genuine PTY output has been seen, based on measured
routing_metrics.jsonl evidence: a stalled ag run can go fully silent mid-
stream after real progress and never resume, but the full 600/900s cold-start
window was still applied from the LAST chunk, wasting hundreds of seconds of
dead time before the kill. See _sys/docs-v2/ops/closure-review-2026-07-17.md
Part B for the full evidence and peer papers.
"""
import sys
from pathlib import Path

SYS_CORE = Path(__file__).resolve().parents[2] / "core"
if str(SYS_CORE) not in sys.path:
    sys.path.insert(0, str(SYS_CORE))

import hub


def test_cold_start_uses_full_window_before_any_progress():
    # No bytes seen yet (progress_bytes_seen=0) -> full cold-start window,
    # preserving the retired-regression lesson (2026-07-11: a shorter
    # profile-scoped startup window killed 3 real cx calls at 180s).
    assert hub._effective_zombie_timeout_sec(600, 0) == 600
    assert hub._effective_zombie_timeout_sec(900, 0) == 900


def test_pty_init_noise_alone_does_not_arm_tightening():
    # Measured 2026-07-17: PTY-init noise across all 88 historical records was
    # 23 bytes (usually a 4+19 split). The noise floor (100) must sit above
    # that with margin, so noise-only progress never tightens the window.
    assert hub._effective_zombie_timeout_sec(600, 23) == 600
    assert hub._effective_zombie_timeout_sec(600, 100) == 600  # exactly at floor: not yet armed


def test_genuine_progress_tightens_to_300s():
    assert hub._effective_zombie_timeout_sec(600, 101) == 300
    assert hub._effective_zombie_timeout_sec(900, 3817) == 300  # matches the real 2026-07-17T15:56 zombie case


def test_tightened_window_never_exceeds_cold_start_window():
    # A profile with a shorter-than-300s cold-start window (hypothetical/future
    # config) must not be LENGTHENED by the post-progress rule.
    assert hub._effective_zombie_timeout_sec(200, 500) == 200


def test_matches_real_2026_07_17_zombie_case_timing():
    """Direct replay of the measured fail case (routing_metrics.jsonl):
    ag.effort, 600s cold-start window, last real chunk at elapsed=383.403s
    with bytes_total=3817 at that point, killed at 983s (599.6s of pure
    trailing silence). With the fix, the kill would fire at 383.403 + 300 =
    683.403s -- saving ~299.6s -- instead of 383.403 + 600 = 983.403s."""
    zombie_timeout_sec = 600
    bytes_at_last_chunk = 3817
    last_chunk_elapsed = 383.403
    effective = hub._effective_zombie_timeout_sec(zombie_timeout_sec, bytes_at_last_chunk)
    assert effective == 300
    old_kill_at = last_chunk_elapsed + zombie_timeout_sec
    new_kill_at = last_chunk_elapsed + effective
    assert round(old_kill_at, 1) == 983.4
    assert round(new_kill_at, 1) == 683.4
    assert round(old_kill_at - new_kill_at, 1) == 300.0
