# Product Frame

## Positioning

Open Figure Lab is a scientific figure production system for reproducible, editable, publication-grade figures.

It is not:

- an Origin replacement
- a Figma replacement
- an AI illustration generator
- a generic matplotlib prompt wrapper

It is:

- a spec-driven figure workbench
- a multi-agent scientific visualization pipeline
- a QA-first production system for paper figures

## MVP Definition

Input trusted data plus figure intent. Output a reproducible multi-panel figure package containing:

- `figure.yaml`
- `theme.yaml`
- `data_manifest.yaml`
- rendering source code
- SVG/PDF/PNG exports
- QA report
- revision history

## First User

The first user is a researcher who can use Python or R but needs faster, more reproducible publication-grade figures.

Core pain:

- figures are technically correct but visually weak
- multi-panel styles drift
- manual vector editing breaks reproducibility
- journal export requirements are easy to miss
- AI tools may fabricate or silently alter scientific claims

## MVP Scope

Must have:

- local project management
- CSV/XLSX-oriented data registry
- natural-language figure intent translated to a figure plan
- structured `figure.yaml`
- matplotlib-first rendering
- multi-panel layout
- Nature-style preset
- SVG/PDF/PNG export
- QA report
- natural-language revision mapped to spec/code
- version history

Postpone:

- Figma plugin
- Illustrator plugin
- Origin control
- QGIS control
- WebGL interaction
- bitmap AI illustration generation
- automatic style extraction from PDFs

## Initial Skills

1. `journal-preset`
2. `figure-spec`
3. `nature-multipanel`
4. `stat-plot`
5. `map-placeholder-and-hybrid`
6. `conceptual-schematic`
7. `publication-qa`
8. `revision-diff`

## First Demo Candidate

Fig. 2 proxy validity:

- Panel A: Spearman rho lollipop
- Panel B: AUC dotplot with 0.5 baseline
- Panel C: top-k precision or lift
- Panel D: decile response

