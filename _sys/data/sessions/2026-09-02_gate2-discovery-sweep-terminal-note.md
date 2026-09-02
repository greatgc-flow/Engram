# Gate 2 discovery-sweep design — brief terminal note (2026-09-03)

Light-weight terminal check (not a full critique round — `cx` remains
unavailable until 2026-09-07, and a full round is deferred until it
recovers or the user asks for terminal-substituted depth here explicitly,
matching the diet plan's precedent for when that substitution is
warranted).

The design's most safety-critical claim — that a rejected
`register_adapter_factory()` call (Lane 2's collision path) leaves the
registry completely unmodified, safe to catch and continue the sweep
without partial pollution — was **already independently verified earlier
this same session** against the real docstring
(`peerhub/adapters/registry.py:84-127`: "Registration is validated
completely before anything is written: a rejected call leaves both the
factory table and the alias table exactly as they were"). This directly
supports the design's `AliasCollisionError`-and-continue behavior being
safe as specified.

Combined with this dispatch's own two verified citations
(`_resolve_executable_path()` at `registry.py:128`, no `adapter`
subcommand collision in `cli.py`), the design rests on 3 independently
confirmed real facts and no detected fabrication. Reasonable to treat as
a solid first-pass design ready for a full critique round once `cx`
recovers, or for the terminal to critique in full depth if the user wants
to proceed with implementation planning before then.
