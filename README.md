# Open Figure Lab

Open Figure Lab is a local-first, agent-driven workbench for publication-grade scientific figures.

The first product frame is intentionally narrow: turn trusted research data and figure intent into reproducible, editable, journal-ready multi-panel figures through a spec-driven workflow.

## Product Promise

From data to publication figure, with agentic precision.

Open Figure Lab is not an Origin replacement, a Figma replacement, an AI image generator, or a loose prompt-to-matplotlib tool. It is a scientific figure production system built around:

- trusted data inputs
- structured figure specs
- skill-driven rendering
- publication QA
- natural-language revision
- reproducible exports

## MVP Loop

```text
data -> figure spec -> skill renderer -> QA report -> revision diff -> export
```

The first implementation target is a CLI workflow:

```powershell
ofl init fig2_proxy_validity
ofl doctor
ofl render fig2_proxy_validity
ofl qa fig2_proxy_validity
```

The first UI target, after the CLI loop works, is a local web workbench with a command pane, figure preview, spec inspector, and run log.

## Repository Map

- `docs/product-frame.md` - product boundaries, MVP scope, roadmap.
- `docs/architecture.md` - system architecture and module responsibilities.
- `docs/version-control.md` - branch, commit, and release conventions.
- `docs/agent-collaboration.md` - leader/agent workflow and handoff rules.
- `src/open_figure_lab/` - minimal Python CLI skeleton.
- `skills/` - product skills that future agents will implement.
- `examples/` - reproducible figure project examples.
- `.omx/` - cross-thread notes, plans, and project memory for agent continuity.

## Current Status

This repository is in foundation phase. The priority is to keep the product frame stable before adding heavy dependencies or a UI stack.

