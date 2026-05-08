# AGENTS.md - Open Figure Lab

This repository is the shared operating surface for Codex, OpenCode, and future coding agents working on Open Figure Lab.

## Role and Intent

Open Figure Lab is a local-first, agent-driven scientific figure production system. Keep the MVP focused on reproducible multi-panel research figures, not a general design tool.

The canonical loop is:

```text
data -> figure spec -> skill renderer -> QA report -> revision diff -> export
```

## Operating Principles

- Execute clear, reversible tasks without waiting for confirmation.
- Prefer evidence over assumption; verify before claiming completion.
- Keep diffs small, reviewable, and reversible.
- No new runtime dependencies without explicit user approval or a written decision in `docs/decisions/`.
- Preserve data integrity: visual revisions must not silently alter source data or computed statistics.
- Prefer deletion, reuse, and simpler boundaries before adding abstractions.

## Product Constraints

- Do not turn this into a generic design/Figma/Origin replacement.
- Figure data must come from user-provided files, source code, or recorded intermediate tables.
- Agents must not invent scientific values, demo metrics, p-values, AUC values, correlations, or map annotations.
- `figure.yaml` is the product-facing intermediate representation. JSON may be used only for dependency-free bootstrap tooling.
- Export targets must remain reproducible: source code, figure spec, data manifest, QA report, and final assets belong together.

## Agent Collaboration

- Codex acts as leader unless the user assigns another lead.
- Future agents should read `README.md`, `docs/product-frame.md`, `docs/architecture.md`, `docs/agent-collaboration.md`, `.omx/project-memory.json`, and `.omx/notepad.md` before implementing.
- Agent handoffs should be appended to `handoff.md`.
- Cross-thread durable notes belong in `.omx/notepad.md` or `.omx/project-memory.json`; do not rely on chat history alone.
- Independent implementation lanes may be delegated, but each lane must have a bounded file scope and verification expectation.

## Version Control

Follow `docs/version-control.md`.

Commit messages should use the Lore protocol when possible:

```text
<intent line: why the change was made>

<body: context and rationale>

Constraint: <external constraint>
Rejected: <alternative> | <reason>
Confidence: <low|medium|high>
Scope-risk: <narrow|moderate|broad>
Tested: <what was verified>
Not-tested: <known gaps>
```

## Verification

Before reporting completion, run the narrowest useful verification:

- Docs-only change: check links/paths and `git status`.
- Python CLI change: run `python -m open_figure_lab.cli doctor` with `PYTHONPATH=src`.
- Future tests: run the project test command documented in `docs/development.md`.

