# Ops — Skill System

> Status: ACTIVE v1.0 | Created: 2026-06-18
> Purpose: Documents the hub skill subsystem — skill definitions, registration, catalog, and invocation.
> Skill files live at: `_sys/ai/common/skills/`

---

## 1. What Is a Skill?

A **skill** is a parameterized, reusable instruction block that peers can invoke via hub.py. Skills abstract common multi-step workflows (voting, context fill, health check, etc.) into named, versioned units. They replace ad-hoc natural-language instructions with deterministic, auditable procedures.

**Properties:**
- Self-contained markdown files (no external imports)
- Parameterized with `{placeholders}` substituted at invocation time
- Version-tracked in git alongside code
- Injected into peer asks as structured context blocks

---

## 2. Skill Catalog (current)

| Skill File | ID | Purpose | Invoked By |
|-----------|-----|---------|-----------|
| `consensus-vote.md` | `consensus-vote` | Cast a vote on an open consensus round | Any peer |
| `context-fill.md` | `context-fill` | Load session context from handoff.md into prompt | hub.py startup |
| `health-check.md` | `health-check` | Read and report local health.json status | Any peer |
| `lesson-add.md` | `lesson-add` | Propose a new lesson to active-lessons.jsonl | Any peer |
| `peer-propose.md` | `peer-propose` | Create a new governance proposal | Any peer |
| `reflect.md` | `reflect` | Post-task self-assessment (quality, cost, outcome) | Any peer after task |

---

## 3. Skill File Structure

```markdown
# Skill: {skill-name}
> Version: {N} | Updated: {date}
> Scope: {which peers may invoke this skill}

## Purpose
{One sentence: what this skill does}

## Parameters
| Name | Required | Description |
|------|----------|-------------|
| {param} | yes/no | {description} |

## Steps
1. {Action step with hub.py command if applicable}
2. ...

## Output Format
{Expected output / side effect}

## Error Handling
{What to do if the skill fails}
```

---

## 4. Invocation

Skills are invoked through hub.py's skill execution path:

```bash
# Direct invocation
python _sys/core/hub.py skill --name {skill-id} --peer {peer_id} --params '{"key":"value"}'

# Skills injected into peer asks (auto-resolved by hub.py)
# When ask contains [SKILL:{skill-id}:{params}], hub.py substitutes
# the skill content before forwarding to peer.
```

---

## 5. Registration

To register a new skill:
1. Create `_sys/ai/common/skills/{skill-name}.md` following the structure in §3.
2. Add an entry to this catalog (§2).
3. Reference in `00-MANIFEST.md` if it affects peer load order.
4. No hub.py code change required — skill resolution is file-based.

Skill changes require R:5 consensus (single `_sys/` file modification).

---

## 6. Feedback Loop

Skills participate in the virtuous feedback loop:
- `reflect.md` skill output → feeds into `cost-log.jsonl` quality signals
- `lesson-add.md` skill → promotes repeated patterns into `active-lessons.jsonl`
- `health-check.md` → feeds routing decisions in hub.py

5-Whys for skill failures: if a skill consistently fails → propose new skill version via `peer-propose.md` → consensus → update skill file + this catalog in same commit (Doc-as-Code, §6 of ops/governance.md).
