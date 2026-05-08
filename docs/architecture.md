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

