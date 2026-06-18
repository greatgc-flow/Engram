# General — The Master Plan (Unified Architecture)
> Status: FINAL_UNANIMOUS (Ready for Implementation Phase)
> Date: 2026-06-16 | Version: 1.0
> Summary: The definitive blueprint for environment stabilization, peer equality, session optimization, and autonomous evolution.

## 1. Reliability & Resilience (Operation Journal)
To ensure consistency across USB/SUBST/Serverless filesystems without heavy ACID transactions.
- **Mechanism:** Replace 'Transaction Journal' with **"Recovery Journal"** (`operations.jsonl`).
- **Flow:** Write Intent → Atomic File Replace (`os.replace`) → Write Commit.
- **Recovery:** Hub startup/sweep reconciles incomplete intents. Idempotency is mandatory for all hub actions.
- **Dual-Write Guard:** `handoff.md` and `handoff.json` stay synchronized via this journaled dual-write process.

## 2. Peer Equality & Governance (Deterministic Gating)
To prevent race conditions and ensure fair leadership without background daemons.
- **Atomic Leader Claim:** Use a **"Challenge Window"** ledger. A claim is not finalized until the `challenge_until` timestamp passes and a finalization command is invoked.
- **Counter-Claim Logic:** Any peer can challenge a claim within the window, forcing a score-based `elect-leader` event.
- **AP-20 Enforcement:** `state.json` tracks a rolling history of coordinators; the hub automatically rejects a 4th consecutive claim by the same peer.

## 3. Autonomous Evolution & Docs (Decision Capsules)
To prevent LLM hallucination in SSOT (docs-v2) and ensure safe self-healing.
- **Decision Capsule:** Finalized consensus emits a machine-readable capsule containing the approved scope, change summary, and doc-targets.
- **DocsSyncer Guard:** Documentation updates must cite either the Decision Capsule or a validated source. New normative claims without citation trigger `DOCS_SYNC_NEEDS_HUMAN`.
- **Self-Healing Tiers (INV-19):**
    - **Tier-0 (Exempt):** Only `_sys/data/` or `_archive/`. Reversible, no state mutation (.ai/ hub.py untouched).
    - **Tier-1/2:** Requires fast-consensus or full R:10.
- **Saturation Centralization:** Centralized `commit_count` in `state.json` triggers `saturation-scan` exactly once every 10 commits.

## 4. Session Persistence (Continuity Score)
To eliminate context drop and fragmentation.
- **Stable Fingerprint:** Hash only normative compatibility fields (peer ID, approval-mode, skip-trust). Exclude environment-specific paths or incidental flags.
- **Resume Failure Classification:** Classify errors as *Transient* (timeout/network) vs. *Permanent* (expired/invalid). Transient errors keep the session ID; Permanent errors issue a new one.
- **Continuity Score:** Replace hard 4h/24h cut-offs with a weighted score (time, pending issues, active threads) to decide between RESUME, RESUME+FILL, or NEW.

## 5. Communication Framework (The Usage Contract)
- **Send:** Directed, transient mailbox transport (Wake-up, Assignment pointers).
- **Thread:** Shared reasoning, debate history, and decision records (SSOT).
- **Alert:** Implementation of `alert-raise` for P0/P1 events, blocking all governed actions until ACKed.
- **INV-17 Clarification:** 1:1 `ask` is permitted for inquiry, but any resulting decision must be promoted to a thread (`thread-promote`) before action.

---

## 6. Implementation Roadmap
1. **[Core]** Recovery Journal & Atomic File Replace helpers in `hub.py`.
2. **[Gov]** Challenge Window & AP-20 enforcement logic.
3. **[Session]** Stable Fingerprint & Resume Classifier.
4. **[Auto]** Decision Capsules & DocsSyncer Semantic Guard.
5. **[Comm]** `alert-raise`, `thread-promote`, and `handoff.json` dual-write.
