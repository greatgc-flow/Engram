# Engram

Move this repo to another Windows machine, run `INSTALL.bat`, and keep the same AI workspace without rebuilding paths by hand.

[![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078d4.svg)](https://www.microsoft.com/windows)
[![Python: 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](_sys/runtimes.json)
[![Validation: local tests](https://img.shields.io/badge/validation-local%20tests-brightgreen.svg)](_sys/tests/unit)
[![Protocol: 4.2](https://img.shields.io/badge/protocol-4.2-purple.svg)](_sys/ai/protocol.json)
[![Architecture: Zero-Code](https://img.shields.io/badge/architecture-Zero--Code-ff69b4.svg)](_sys/ai/orchestration.json)

Engram is a portable Windows AI workspace built around Zero-Code orchestration.

Zero-Code means you change the workspace by editing JSON and docs, not by rewriting adapter code.

## What You Get

- Portable setup: copy the folder, run `register.bat`, and mount the workspace on `P:\`.
- Multi-peer routing: send work across peers and profiles through one documented hub.
- Operating rules: startup, health, context, and consensus behavior live in source-controlled docs.
- Local validation: checks and tests live in the repo, so changes can be reviewed instead of guessed.

## Trust Signals

- Runtime SSOT: [`_sys/ai/protocol.json`](_sys/ai/protocol.json) and [`_sys/ai/orchestration.json`](_sys/ai/orchestration.json).
- Human docs: [`_sys/docs-v2/user/manual.md`](_sys/docs-v2/user/manual.md) and [`_sys/docs-v2/MOC.md`](_sys/docs-v2/MOC.md).
- Bootstrap entry points: [`INSTALL.bat`](INSTALL.bat) and [`register.bat`](register.bat).
- Validation surfaces: [`_sys/tests/unit`](_sys/tests/unit) and [`_sys/checks`](_sys/checks).
- Windows-first layout: the workspace is built around a relocatable `P:\` drive.

## Get Started

1. Copy or clone the repo to a Windows drive.
2. Run `INSTALL.bat`.
3. Run `register.bat` to mount `P:\`.
4. Read the [user manual](_sys/docs-v2/user/manual.md) and [MOC](_sys/docs-v2/MOC.md).

If this repo saves you setup time, please star it so other people can find a portable Windows AI workspace that does not need hand-wired setup.

> **For AI peers**: start with [`_sys/docs-v2/MOC.md`](_sys/docs-v2/MOC.md) and [`_sys/docs-v2/10-invariants.md`](_sys/docs-v2/10-invariants.md). This README is the human entry point, not the policy source.
