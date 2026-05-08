# Agent Collaboration

## Leadership

Codex is the repository leader until the user assigns another lead.

Leader responsibilities:

- preserve product scope
- maintain durable memory
- split work into bounded lanes
- integrate agent outputs
- own final verification

## Durable Context Files

Every agent should read these first:

- `README.md`
- `AGENTS.md`
- `docs/product-frame.md`
- `docs/architecture.md`
- `.omx/project-memory.json`
- `.omx/notepad.md`
- `handoff.md`

## Agent Work Lanes

Good lanes for future OpenCode or other agents:

- `figure-spec`: schema and validation
- `journal-preset`: preset tokens and compliance checks
- `renderer`: matplotlib rendering for one panel family
- `qa`: data integrity and export preflight checks
- `docs`: developer guide and examples
- `web-ui`: preview and inspector after CLI stabilizes

Each lane must declare:

- owned files
- expected command or test
- assumptions
- open blockers

## Handoff Format

Append to `handoff.md`:

```markdown
## YYYY-MM-DD Agent Name - Task

Changed:
- ...

Verified:
- ...

Open:
- ...
```

