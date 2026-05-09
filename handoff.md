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

## 2026-05-08 SOC Fig. 2 Renderer

Changed:

- Added a runnable `examples/soc_proxy_fig2` package with four CSV inputs and a 2x2 `figure.yaml`.
- Added a matplotlib renderer for lollipop, AUC dotplot, precision lift, and decile curve panels.
- Added `ofl render` output for SVG/PDF/PNG.
- Added data QA for panel data files and required CSV fields.
- Added `qa_report.md` generation under figure project outputs.
- Added matplotlib as the first runtime dependency and updated CI to install the package before tests.

Verified:

- `PYTHONPATH=src python -m open_figure_lab.cli validate examples/soc_proxy_fig2`
- `PYTHONPATH=src python -m open_figure_lab.cli qa examples/soc_proxy_fig2`
- `PYTHONPATH=src python -m open_figure_lab.cli render examples/soc_proxy_fig2`
- `PYTHONPATH=src python -m unittest discover -s tests -v`
- Visual inspection of `examples/soc_proxy_fig2/outputs/soc_proxy_fig2.png`.

Open:

- Renderer styling is functional but still first-pass; next iteration should tighten typography, spacing, axis limits, and journal preflight checks.
- Data QA checks file and field integrity, but not yet annotation/statistic provenance.
- The demo data is illustrative, not a real SOC result export.

## 2026-05-08 OpenCode - Web UI Skeleton

Changed:

- Added lightweight Python HTTP API server (`app/api/server.py`)
- Added vanilla HTML/CSS/JavaScript frontend (`app/web-ui/`)
- Added three-panel workbench layout: Command, Preview, Inspector
- Added bottom Run Log for command execution history
- Added API endpoints wrapping existing CLI functionality
- Added startup script (`app/start.py`)
- Updated development documentation

Verified:

- Server starts with `python app/start.py`
- Browser opens to http://localhost:8080
- Can view figure.yaml, data manifest, QA report in Inspector
- Can click Validate/Render/QA buttons and see output in Run Log
- Can preview rendered figure (soc_proxy_fig2.png)
- Existing CLI tests still pass

Open:

- No real LLM integration yet (command input disabled)
- No WebSocket for real-time updates
- No project switching (hardcoded to soc_proxy_fig2)
- No file editing capabilities
- No theme switching
- Frontend could be enhanced with better error handling

## 2026-05-09 Codex - Stitch-Inspired Web UI Redesign

Changed:

- Replaced the dark skeleton workbench with a light scientific "digital paper" workspace inspired by the Stitch reference package.
- Reframed the UI around an artifact canvas, fixed workspace rail, right inspector, agent context panel, and run trace.
- Removed mojibake/icon glyph dependencies from the web UI and kept labels ASCII-safe.
- Updated frontend command handling to match the current API response contract (`success`, `stdout`, `stderr`, `returncode`).

Verified:

- `PYTHONPATH=src python -m unittest discover -s tests -v`
- `PYTHONPATH=src python -m open_figure_lab.cli render examples/soc_proxy_fig2 --format png`
- `PYTHONPATH=src python -m open_figure_lab.cli qa examples/soc_proxy_fig2`
- HTTP smoke test on `http://127.0.0.1:8090` for `/`, `/styles.css`, `/app.js`, `/api/project`, `/api/spec`, `/api/data-manifest`, `/api/qa-report`, `/outputs/soc_proxy_fig2.png`, and POST `/api/validate`, `/api/render`, `/api/qa`.

Open:

- Still no real LLM/agent editing loop; command draft remains disabled.
- Project selection is still hardcoded to `soc_proxy_fig2`.
- Browser-level visual QA was not automated in this pass because Playwright/browser automation was unavailable in the current environment.

## 2026-05-09 Codex - OpenDesign-Style Agent Entry

Changed:

- Cloned `nexu-io/open-design` into `D:\Acodeproject\Temp\open-design` as a read-only reference.
- Added an OpenDesign-style `/api/agents` endpoint that detects local CLI agents from `PATH`.
- Added fallback model lists for OpenCode, Claude Code, Codex CLI, Cursor Agent, and Gemini CLI.
- Switched the Web UI to start on an Agent Runtime setup screen before entering the Lab.
- Added a short-lived agent detection cache and threaded HTTP server so CLI probes do not block unrelated UI/API requests.
- Documented the OpenDesign runtime boundary in `docs/architecture.md`.

Verified:

- `python -m py_compile app\api\server.py app\start.py`
- `node --check app\web-ui\app.js`
- `PYTHONPATH=src python -m unittest discover -s tests -v`
- HTTP smoke test on `http://127.0.0.1:8090` for `/api/agents` and POST `/api/validate`.

Open:

- Agent selection is persisted only in browser memory for this MVP pass.
- Agent streaming/chat execution is not wired yet; the Lab still uses validate/render/QA CLI API endpoints.
- `/api/agents` currently detects local binaries and models but does not verify auth/account health.

## 2026-05-09 Codex + OpenCode - Agent Runtime Plan

Changed:

- Assigned OpenCode a planning task for the next agent execution/streaming stage.
- Added `docs/opencode-agent-runtime-plan.md` from that OpenCode task.
- Reverted an incorrect attempt to rename/configure the OpenCode CLI adapter; OpenCode should remain `OpenCode` in the product picker unless the user explicitly asks for a product-level alias.

Verified:

- `docs/opencode-agent-runtime-plan.md` exists and was generated by OpenCode.

Open:

- `.sisyphus/` was created by OpenCode as local runtime state and is intentionally not part of the committed product surface unless we later decide to track it.

## 2026-05-09 OpenCode - Project Config and Mock Agent Runs

Changed:

- Added project discovery for `examples/*/spec/figure.yaml`.
- Added session config persistence for selected project, agent, model, and reasoning.
- Added mock agent run create/read/cancel endpoints backed by `.omx/runs/`.
- Enabled the Lab agent prompt box to create mock runs and show the run id in the UI.
- Added `.gitignore` entries for local session/run state and `.sisyphus/`.
- Added `tests/test_agent_runs.py` for agent run API behavior.

Verified:

- `python -m py_compile app\api\server.py app\start.py`
- `node --check app\web-ui\app.js`
- `PYTHONPATH=src python -m unittest discover -s tests -p 'test*.py' -v`
- HTTP smoke test on `/api/projects`, `/api/session-config`, `/api/agent-runs`, `/api/agent-runs/<id>`, `/api/agent-runs/<id>/cancel`, and POST `/api/validate`, `/api/render`, `/api/qa`.

Open:

- Agent run records are still mock records; no real CLI process is spawned yet.
- No SSE/event streaming yet.

## 2026-05-09 OpenCode - Synchronous OpenCode Runs

Changed:

- Upgraded `/api/agent-runs` from mock records to synchronous OpenCode execution for `agentId=opencode`.
- Added Open Figure Lab data-safety boundary text to every OpenCode prompt.
- Persisted command, timestamps, return code, stdout, stderr, and completed/failed status in run records.
- Limited prompt length, validated projects, rejected unsupported agents, and whitelisted OpenCode models from `/api/agents`.
- Updated the Agent Console to display completed/failed output summaries and refresh spec/data/QA/preview after a run.

Verified:

- `python -m py_compile app\api\server.py app\start.py`
- `node --check app\web-ui\app.js`
- `PYTHONPATH=src python -m unittest discover -s tests -p 'test*.py' -v`
- HTTP smoke test for `/api/projects`, `/api/session-config`, unsupported-agent rejection on `/api/agent-runs`, and POST `/api/validate`, `/api/render`, `/api/qa`.

Open:

- Real OpenCode execution is synchronous and blocks the request until completion or timeout.
- No SSE/event streaming, incremental tool output, or process cancellation yet.

## 2026-05-09 OpenCode - Async Agent Runs, SSE, and File Changes

Changed:

- Replaced synchronous agent execution with a background run controller using `subprocess.Popen`.
- Added short-connection SSE endpoint `GET /api/agent-runs/<id>/events?after=<event_id>`.
- Added process cancellation for pending/running runs.
- Added adapter argv builders for OpenCode, Claude Code, and Codex.
- Added prompt-via-stdin support for Claude Code and Codex.
- Added per-run stdout/stderr events and file change detection after run completion.
- Updated the Agent Console to poll run events, show stdout/stderr, expose Cancel, and display changed files.

Verified:

- `python -m py_compile app\api\server.py app\start.py`
- `node --check app\web-ui\app.js`
- `PYTHONPATH=src python -m unittest discover -s tests -p 'test*.py' -v`
- HTTP smoke test for `/api/agents`, `/api/agent-runs/nope/events` 404, empty prompt rejection, unsupported agent rejection, and POST `/api/validate`.

Open:

- SSE is still polling-style short connection, not a held streaming connection.
- Real long-running OpenCode/Claude/Codex edits were not manually exercised in-browser in this pass; subprocess behavior is covered by mocked tests.

## 2026-05-09 Codex - Skill Injection and Skill Registry MVP

Changed:

- Added a lightweight skill registry (`SKILL_REGISTRY`) in `app/api/server.py` with three builtin skills:
  - `open-figure-lab-core`: Core scientific figure production rules and data safety boundaries (enabled by default)
  - `scientific-figure-qa`: QA constraints for axes, legends, statistical annotations, journal compliance (enabled by default)
  - `nature-style-figure`: Nature journal formatting requirements (disabled by default, opt-in)
- Each skill contains: `id`, `title`, `description`, `promptText`, `source` (builtin/local/github), `enabled` (default state).
- Replaced the old `_OPENCODE_BOUNDARY` static string with `_build_injected_prompt()` that dynamically composes:
  - Project context (name, directory, key file paths)
  - Skill prompt text from selected skills
  - Data safety boundary rules (fabrication prohibition, reproducibility, file change listing)
  - User's task prompt
- Added `GET /api/skills` endpoint returning the full skill registry.
- Updated `POST /api/agent-runs` to accept optional `skillIds` list; defaults to enabled skills when omitted; rejects invalid skill IDs with 400.
- Run records now include `skillIds` (list of active skill IDs) and `injectedPromptPreview` (truncated to 2000 chars).
- Updated `app/web-ui/index.html` to add an "Active Skills" section with checkbox toggles in the Agent Console.
- Updated `app/web-ui/app.js` to:
  - Load skills from `GET /api/skills` on init
  - Render skill toggles with checkboxes
  - Include selected `skillIds` when creating agent runs
  - Display which skills were used after run completion
- Added CSS styles for skill toggles and skill-used badges.
- Added `SkillRegistryTests` class with 11 unit tests covering registry structure, default states, enabled skills resolution, and prompt injection content.
- Added 6 integration tests in `AsyncAgentRunTests` for `GET /api/skills`, invalid `skillIds` rejection, `skillIds` list validation, run record `skillIds` persistence, default skill injection, and `injectedPromptPreview` content.

Verified:

- `python -m py_compile app\api\server.py app\start.py`
- `node --check app\web-ui\app.js`
- `PYTHONPATH=src python -m unittest discover -s tests -p "test*.py" -v` (92 tests, all pass)

Open:

- The `source` field supports `builtin`, `local`, and `github` values, but only `builtin` skills are implemented. `local` and `github` sources are reserved for future extension.
- External skill downloading/vendor is intentionally not implemented; `github` source is documentation-only.
- The skill toggle UI is minimal; a future pass could add skill descriptions as tooltips or a dedicated Skills panel.
- The injected prompt preview is truncated to 2000 chars in the run record to avoid excessive storage; the actual prompt sent to the agent is uncapped.
- Reviewer correction: project context now points agents to the real QA artifact, `outputs/qa_report.md`.
