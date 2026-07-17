# _retire_session() on-disk directory deletion was reverted 2026-07-17: scope_key at
# every real call site is f"{room_id}:{profile_id}" (colon-suffixed), which never
# matches the actual on-disk `.ai/sessions/{room_id}/` directory name, and even a
# corrected match would delete room-shared state (handoff.md/json, threads/) still
# needed by other profiles/peers on routine per-profile session churn (fingerprint
# drift, resume failure) -- not just on genuine room closure. No safe fix identified
# within hygiene-batch scope; left for a future room-lifecycle-aware design.
