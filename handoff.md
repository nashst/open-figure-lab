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

GitHub status:

- Remote repository: `https://github.com/nashst/open-figure-lab`
- Visibility: public
- Branches: `main`, `develop`
- Branch protection was initially rejected while private; repository was made public so protection can be enabled.

License:

- MIT

## 2026-05-08 Figure Schema + Nature Preset

Changed:

- Added dependency-free `figure.yaml` subset loader and schema validator.
- Added built-in `nature` and `nature_comm` journal presets.
- Added CLI commands: `ofl validate` and `ofl presets`.
- Updated `ofl qa` to fail on invalid figure specs.
- Documented the first spec contract in `docs/figure-spec.md`.

Verified:

- `PYTHONPATH=src python -m open_figure_lab.cli doctor`
- `PYTHONPATH=src python -m unittest discover -s tests -v`
- `ofl init -> ofl validate -> ofl qa` smoke flow through `python -m open_figure_lab.cli`.

Open:

- Replace the bootstrap YAML subset parser with PyYAML or another structured parser only after an explicit dependency decision.
- Implement semantic data integrity QA.
- Add the first real renderer for SOC Fig. 2 proxy validity.
