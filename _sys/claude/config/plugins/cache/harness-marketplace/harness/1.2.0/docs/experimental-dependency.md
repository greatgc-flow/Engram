# Experimental Flag Dependency

> **Status:** Active · **Owner:** revfactory · **Last updated:** 2026-04-18 · **SLA:** See [Monitoring Commitment](#monitoring-commitment)

This document explains why `harness` requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, the three plausible futures of that flag, and what this repository will do in each case — with time-boxed commitments so enterprise adopters can plan against it.

---

## Current State

### Why the flag is required

`harness` is a meta-skill factory built on top of Claude Code's **Agent Teams API**. Three Claude Code primitives are invoked internally whenever a user runs `claude "build a harness for <domain>"`:

| Primitive | Purpose | Flag gated? |
|-----------|---------|-------------|
| `TeamCreate` | Instantiates a multi-agent team with shared context | **Yes** |
| `SendMessage` | Routes messages between team members (supervisor ↔ worker) | **Yes** |
| `TaskCreate` | Spawns long-running subtasks inside a team | **Yes** |
| `Agent` tool (invoke) | Single-agent dispatch | No (GA) |

All three flag-gated primitives require:

```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

Without this variable set in the shell that launches `claude`, harness's generated teams fall back to single-agent execution, which silently breaks the Pipeline / Fan-out-in / Supervisor / Hierarchical Delegation patterns.

### Anthropic references (required reading before filing issues)

The design rationale and roadmap for this flag live in three Anthropic Engineering posts. Adopters evaluating harness should read at least the first:

1. [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — defines the "harness" category Anthropic endorses and the long-running agent contract.
2. [Harness design for long-running apps](https://www.anthropic.com/engineering/harness-design-long-running-apps) — the patterns `harness` codifies (Pipeline, Producer-Reviewer, Supervisor, etc.).
3. [Scaling Managed Agents](https://www.anthropic.com/engineering/managed-agents) — the forward path that may supersede the Experimental flag (see Scenario B).

---

## Dependency Graph

```
harness (v1.2.0)
  └── Agent Teams API (Claude Code)
        ├── TeamCreate            ← EXPERIMENTAL_AGENT_TEAMS=1
        ├── SendMessage           ← EXPERIMENTAL_AGENT_TEAMS=1
        ├── TaskCreate            ← EXPERIMENTAL_AGENT_TEAMS=1
        └── Agent (invoke)        ← GA (flag-independent)
              └── Anthropic Roadmap
                    ├── Scenario A: Flag removed (GA promotion)
                    ├── Scenario B: Managed Agents GA (parallel path)
                    └── Scenario C: Breaking signature change
```

**Read this graph top-down:** harness depends on Agent Teams API, which depends on a single Experimental flag, which depends on Anthropic's own roadmap. If any upstream node changes, this repository is on the hook to adapt within the SLA below.

---

## 3 Scenarios

Each scenario lists the **detection trigger** (how we will know it happened), the **T+24h / T+48h / T+72h actions** this repository commits to, and the **user-visible artifact** at each checkpoint.

### Scenario A — Flag removed (Agent Teams promoted to GA)

**Trigger detection:** Anthropic Claude Code Changelog publishes "Agent Teams is now GA" **or** `claude-code` binary no longer requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` (detected by nightly CI in [P-13](#).

**Probability (subjective):** High — this is the path the three blog posts above telegraph.

| Checkpoint | Action | Artifact |
|------------|--------|----------|
| **T+24h** | Open branch `feat/drop-experimental-flag`. Remove `export` line from every README / docs / Quickstart. Add `claude-code >= X.Y.Z` lower bound in `plugin.json`. | Branch + PR (draft) |
| **T+48h** | Publish `docs/migrating-from-experimental.md`. Update `docs/experimental-dependency.md` (this file) headline to "no flag required as of vX.Y". Pin GitHub issue: "Action required: drop the export line". | Migration guide + pinned issue |
| **T+72h** | Ship **v1.3.0** release with: (a) CHANGELOG entry, (b) `gh release create` with migration note, (c) HN follow-up: "We dropped the experimental flag". | `v1.3.0` git tag + GH Release |

**Adopter impact:** Positive. Enterprise approval friction drops — one checkbox ("no experimental flags") becomes satisfiable. No breaking change to harness user code.

---

### Scenario B — Managed Agents reaches GA (parallel path)

**Trigger detection:** Anthropic publishes "[Managed Agents](https://www.anthropic.com/engineering/managed-agents) is generally available" with a stable `claude-agents` CLI or SDK surface.

**Probability (subjective):** Medium-high within 90 days. Managed Agents is a server-side execution model; harness's client-side team orchestration does **not** automatically translate.

| Checkpoint | Action | Artifact |
|------------|--------|----------|
| **T+24h** | Open `feat/managed-agents-compat` PR. Add `adapters/managed-agents/` scaffold that maps harness's 6 team patterns to Managed Agents invocation. Identify incompatible patterns (likely: Hierarchical Delegation). | Compat PR (draft) |
| **T+48h** | Publish blog post: **"Harness + Managed Agents: one layer up, not replaced"** on Dev.to and in the repo. Re-frame harness as the **design-time** layer that outputs Managed Agents configs, not a runtime competitor. | Coexistence framing blog |
| **T+72h** | Publish `docs/managed-agents-migration.md` with a per-pattern matrix (which of the 6 patterns map 1:1, which need rewrite). Update README sibling-repo section. | Migration guide |

**Strategic note:** harness re-positions as the **upper layer on top of Managed Agents** — "Managed Agents runs the team, harness designs it." This is the coexistence frame in §4.2 of the GTM plan.

**Adopter impact:** Neutral to positive. Existing harness users keep working on the Experimental flag path; new users can opt into Managed Agents output.

---

### Scenario C — Breaking change (API signature mutation)

**Trigger detection:** Nightly CI (`.github/workflows/nightly-compat.yml`, tracked as roadmap P-13) fails against Claude Code's latest nightly build **or** the Changelog announces a renamed env var / changed `TeamCreate` signature.

**Probability (subjective):** Medium. Experimental APIs are renamed without deprecation windows.

| Checkpoint | Action | Artifact |
|------------|--------|----------|
| **T+0 to T+24h** | Nightly CI alert fires in Slack/Discord. Author opens `hotfix/compat-<date>` branch, patches affected call sites. Unit tests green on both old + new signature (best effort). | Hotfix branch |
| **T+24h** | Merge hotfix. Push `v1.2.x` patch tag. Update `docs/compatibility-matrix.md` row for affected Claude Code version. | `v1.2.x` patch release |
| **T+72h** | If the change is non-trivial (affects harness's public contract), publish a short notice on the repo Discussions tab + X. Otherwise, CHANGELOG entry is sufficient. | Discussions post (conditional) |

**Adopter impact:** Existing pinned users on the prior Claude Code version are unaffected. Users on latest get a same-week patch.

---

## Monitoring Commitment

We commit to the following **observable SLA**. Missing it is grounds for filing an issue with the `sla-breach` label.

| Event | SLA | Measurement |
|-------|-----|-------------|
| Anthropic publishes Agent Teams / Managed Agents change in official Changelog | This document updated within **72 hours** | Compare Changelog post timestamp to this file's `Last updated` line |
| Nightly CI detects compat break | Hotfix branch open within **24 hours** | GitHub Actions run timestamp vs. branch creation timestamp |
| New Claude Code stable release (minor or major) | `docs/compatibility-matrix.md` row added within **7 days** | Compatibility matrix diff |

**Sources we actively monitor:**

- Claude Code release notes — watched via the [Anthropic Engineering blog](https://www.anthropic.com/engineering) RSS
- `anthropics/claude-code` GitHub Releases (nightly tag)
- Anthropic Discord `#claude-code` channel (community signal)

---

## FAQ for Enterprise Adopters

### Q1. We're in a regulated industry (finance, healthcare, public sector) and can't enable `EXPERIMENTAL` flags in production. How do we adopt harness?

**Cause:** Many compliance frameworks (SOC 2 Type II, ISO 27001, K-ISMS) disallow unstable / preview features in production.
**Action:** Use harness **design-time only**: run it in a sandbox workstation to scaffold `.claude/agents/` and `.claude/skills/` files, then commit the generated artifacts into your production repo. Production Claude Code never needs the flag — only the flag-gated `TeamCreate` runtime does. The generated single-agent skills are GA-path compatible.

### Q2. If Agent Teams goes GA (Scenario A), will my existing harness-generated code break?

**Cause:** GA promotion in Anthropic's Claude Code has historically been non-breaking for generated artifacts; the flag simply stops being required.
**Action:** No action required for end users. Your `.claude/agents/*.md` and `.claude/skills/*` files are plain Markdown and remain valid. You will be able to `unset CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` on the day of GA. We will publish a migration note within 48 hours (see Scenario A).

### Q3. Do you guarantee an SLA in writing? What happens if you miss it?

**Cause:** Enterprises need a contractual or at-minimum observable commitment before approval.
**Action:** The SLA table above is the **public commitment** and is enforced by: (a) a GitHub Action that comments on this file if its `Last updated` line is older than 72 hours after a detected Changelog event, (b) an `sla-breach` issue label adopters may apply, (c) a post-mortem obligation in `CONTRIBUTING.md` for any breach. This is not a paid SLA — it is a community commitment. For a paid SLA, contact the maintainer (see repository README).

---

**Related documents:**
- [`docs/quickstart.md`](./quickstart.md) — 5-minute install walkthrough
- [`docs/show-hn-launch-kit.md`](./show-hn-launch-kit.md) — Public launch package
- `docs/compatibility-matrix.md` *(pending P-13)* — Claude Code × harness version table
