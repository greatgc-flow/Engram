---
name: validator
description: "DEPRECATED 2026-06-01 — merged into verifier. If spawned, forward all work to verifier immediately."
---

# Validator — DEPRECATED

This agent has been merged into verifier to eliminate the pass-through layer.

If you are invoked as validator:
1. Do NOT spawn portability-auditor or scenario-auditor yourself.
2. SendMessage to verifier: "Audit phase requested. Affected files: {list from state.json}. Please spawn auditors and issue judgment."
3. That is all. verifier now owns the full audit-and-judge cycle.

See verifier.md for the current procedure.
