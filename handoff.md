# Handoff Log

This file is the durable cross-thread handoff surface for Open Figure Lab.

## 2026-05-08 Foundation Setup

Current product frame:

- Local-first scientific figure workbench.
- MVP loop: data -> figure spec -> skill renderer -> QA report -> revision diff -> export.
- First target: dependency-light CLI foundation before web UI.
- First demo candidate: SOC Fig. 2 proxy validity.

Current leader stance:

- Codex leads repository coordination.
- OpenCode and other agents can be assigned bounded implementation lanes later.
- Durable memory lives in `AGENTS.md`, `.omx/project-memory.json`, `.omx/notepad.md`, `docs/*.md`, and this file.

Next recommended implementation lane:

- Implement `figure.yaml` schema and validation.
- Add journal preset tokens for Nature/Nature Communications.
- Add one demo renderer for a 2x2 proxy-validity figure using real CSV fixtures.

