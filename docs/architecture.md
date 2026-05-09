# Architecture

## System Shape

```text
Open Figure Lab
|-- Agent Adapter
|-- Skill Engine
|-- Figure Spec Engine
|-- Render Engine
|-- QA Engine
|-- Export Engine
`-- UI
```

## OpenDesign Reference Boundary

Open Figure Lab should follow OpenDesign's runtime boundary where practical:

```text
local web UI -> local daemon/API -> existing coding-agent CLI -> project workspace
```

The app does not replace OpenCode, Claude Code, Codex, Cursor Agent, or similar CLIs. It detects installed local agents, lets the user choose an agent and model, then starts the figure lab with that runtime context.

The first implementation is intentionally small:

- `GET /api/agents` detects known local CLIs from `PATH`.
- The Web UI starts on an agent setup screen before entering the Lab.
- Model choices come from the CLI when cheap and reliable; otherwise the app uses curated fallback options.
- The figure workspace still uses the existing CLI-backed validate/render/QA API until the streaming agent loop is implemented.

This keeps the product aligned with OpenDesign without importing its full daemon, SQLite, React, or packaging stack before the scientific figure loop is stable.

## Core Rule

Data layer and visual layer are separate.

Data layer responsibilities:

- read user data
- record provenance
- calculate statistics
- create intermediate tables

Visual layer responsibilities:

- arrange panels
- style marks, labels, legends, annotations
- export assets
- record visual revisions

Visual revisions must not recompute or rewrite scientific values unless the user explicitly asks for a data-layer change.

## Figure Project Layout

```text
figure_project/
|-- data/
|-- spec/
|   |-- figure.yaml
|   |-- theme.yaml
|   `-- data_manifest.yaml
|-- src/
|   `-- render.py
|-- outputs/
|   |-- figure.svg
|   |-- figure.pdf
|   |-- figure.png
|   `-- qa_report.md
`-- history/
```

## Package Boundaries

- `open_figure_lab.cli` - command routing and project bootstrapping.
- `figure_spec` - schema, validation, and diff model.
- `renderers` - matplotlib-first rendering implementations.
- `qa` - data integrity, journal compliance, accessibility, and visual hierarchy checks.
- `exporters` - output formats and preflight checks.
- `agent_adapter` - future integration boundary for Codex, OpenCode, Claude Code, Cursor.

The current codebase starts with only `open_figure_lab.cli` to avoid premature dependency decisions.
