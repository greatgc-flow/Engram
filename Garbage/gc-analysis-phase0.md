# Phase 0 Analysis: System Overhaul
**Author**: gc (Gemini)
**Role**: Primary for TAXONOMY v11 drafting, Secondary for USER_MANUAL, Reviewer for cx fixes
**Date**: 2026-06-13
**References**: `TAXONOMY_v10.md`, `MASTER_PLAN_v1.md`, `P:\_sys\` structure

---

## QUESTION 1: TOP 5 IMPACTFUL IMPROVEMENTS FOR v11
Based on the implementation score of 36.3% in v10 and the stated development direction (No-Code, Composable, General-Specific MECE, JSON configs), the top 5 improvements for v11 are:

1. **Strict General-Specific Enforcement (JSON-Driven Governance)**: Complete the separation mandated by 4-15 and 3-2-6 (G54 & G51). All hardcoded values, logic constants, and vendor-specific paths must be extracted into `_sys/ai/*.json` configuration files, establishing a true No-Code orchestration layer.
2. **Canonical Peer Interface as Declarative JSON**: Fulfill 4-13 and 4-14 (G48 & G49) by defining universal JSON connection points for all AI nodes. Nodes must plug into the orchestrator via declarative schemas (`peers.json`, `protocol.json`) rather than script-level adapters.
3. **Workspace Isolation & Base Templates**: Introduce formal "Base Templates" (`_sys/templates/workspace/`) to stamp out new specific workspaces. The `_sys/` folder becomes completely workspace-independent (General), interacting with specific workspaces entirely through JSON configurations.
4. **Complete Parameter Registry Synchronization**: Ensure all 44 keys defined in §6 of TAXONOMY_v10 are strictly mapped and enforced via JSON. Implement G40 (Config Drift Detection) to prevent local deviations.
5. **Resource Lazy Initialization & Dynamic Composition**: Implement 5-12 (G50) driven by `dispatch.json` and `runtimes.json` so that heavy resources (like specific AI peers or MCP servers) are dynamically composed and loaded via JSON logic rather than eager script execution.

---

## QUESTION 2: STRUCTURAL GAPS IN `P:\_sys\`
Reviewing the `_sys/` directory structure reveals several structural gaps that v11 must address:

1. **Node-Specific Logic Mixed with Core System**: The `_sys/` directory contains top-level folders for `claude`, `gemini`, `codex`, `antigravity`, and `chatgpt`. This violates a strict General-Specific separation. Peer-specific implementations should ideally be treated as plugin configurations loaded via JSON, rather than first-class citizens alongside `core/` and `cli/`.
2. **Scattered JSON Configurations**: We have multiple JSON configs at the root of `_sys/` (`context_menu.json`, `dispatch.json`, `env.json`, `paths.json`, `runtimes.json`). While they move towards the No-Code vision, they need a unified schema registry to prevent configuration drift and ensure they act as definitive General-Specific connection points.
3. **Checks Subsystem Hardcoding**: The `_sys/checks/` directory contains numerous `.py` and `.bat` files. As identified in v10 (G51), these likely contain inline magic constants. They must be refactored to read thresholds exclusively from the parameter registry.
4. **Incomplete Base Template Architecture**: While `_sys/templates/workspace/` exists, the lack of strict boundaries means `_sys/` still implicitly assumes it operates over a single default workspace rather than acting as a universal hub for *any* generated specific workspace subdirectory.

---

## QUESTION 3: ACKNOWLEDGMENT
**ACKNOWLEDGED**.
I understand my role in this R:10 unanimous consensus session. I will act as the Primary for the `TAXONOMY_v11.md` drafting, Secondary for the `USER_MANUAL.md`, and Reviewer for cx's structural and bug-fix proposals. I will base all decisions on the No-Code, Composable, and General-Specific MECE principles.