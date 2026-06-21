# {PROJECT_NAME} — Claude Instructions

> Replace `{PROJECT_NAME}` with your actual project name.

## Quick Start

Read `_sys/docs-v2/user/manual.md` for onboarding.
Protocol rules: `_sys/docs-v2/general/protocol.md`

## Workspace Structure

```
{PROJECT_NAME}/
├── specific/       ← workspace-specific agents, skills, config
├── config/         ← project settings (settings.json)
└── src/            ← your source code (create as needed)
```

## Session Start

1. Check peer health before any task
2. Read handoff.md if continuing from previous session
3. Follow COLLAB_RATE from config/settings.json (null = use global)
