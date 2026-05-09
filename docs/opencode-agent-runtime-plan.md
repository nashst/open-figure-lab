# OpenCode Agent Runtime Plan for Open Figure Lab

## 1. OpenDesign Files/Concepts to Borrow

| OpenDesign File | Concept to Borrow | Adaptation for OFL |
|---|---|---|
| `specs/current/runtime-adapter.md` | Runtime adapter architecture | Reference for agent spawning/streaming |
| `specs/current/run.md` | Run model + recovery flow | Persist runId, status, event replay |
| `apps/daemon/src/agents.ts` | `AGENT_DEFS` registry | Extend existing `AGENT_DEFS` in server.py |
| `apps/daemon/src/server.ts` | `/api/chat` + SSE | New `/api/agent-runs` endpoint |
| `apps/daemon/src/json-event-stream.ts` | JSON event parsing | Parse OpenCode/Claude/Codex JSON output |
| `apps/daemon/src/claude-stream.ts` | Claude Code JSONL parsing | Parse `claude -p --output-format stream-json` |

## 2. Minimal API Contract: `/api/agent-runs`

```http
POST /api/agent-runs        # Start agent run
GET  /api/agent-runs/:id    # Get run status
GET  /api/agent-runs/:id/events?after=<lastEventId>  # SSE stream
POST /api/agent-runs/:id/cancel  # Stop running agent
```

Request (`POST /api/agent-runs`):
```json
{
  "agentId": "opencode",
  "model": "default",
  "prompt": "Render figure spec from figure.yaml",
  "projectPath": "D:/projects/fig2_proxy_validity"
}
```

Response (202):
```json
{ "runId": "run_abc123", "status": "running" }
```

SSE Events:
- `status` -> `{"type": "status", "status": "running|completed|failed"}`
- `text_delta` -> `{"type": "text_delta", "content": "..."}`
- `tool_use` -> `{"type": "tool_use", "tool": "Read", "input": {...}}`
- `tool_result` -> `{"type": "tool_result", "tool": "Read", "output": "..."}`
- `usage` -> `{"type": "usage", "tokens": 1234}`
- `error` -> `{"type": "error", "message": "..."}`

## 3. Agent Spawning on Windows

| Agent | Spawn Command | Stream Format |
|---|---|---|
| OpenCode | `opencode run --format json --dangerously-skip-permissions <prompt>` | JSON event stream |
| Claude Code | `claude -p <prompt> --output-format stream-json --verbose --include-partial-messages` | JSONL (claude-stream) |
| Codex | `codex exec --json --skip-git-repo-check --sandbox workspace-write -C <cwd> -p <prompt>` | JSON event stream |

Windows-specific:
- Use `subprocess.Popen` with `creationflags=subprocess.CREATE_NEW_PROCESS_GROUP` for process isolation
- Pass `cwd` as explicit `-C` argument (OpenCode/Codex) or `--cwd` flag
- Use `SIGTERM` via `proc.terminate()`; on Windows sends `CTRL_BREAK_EVENT`

## 4. Event Stream Shape for UI

```typescript
// Frontend consumes SSE /api/agent-runs/:id/events
interface AgentEvent {
  id: string;        // Monotonically increasing event ID
  type: 'status' | 'text_delta' | 'tool_use' | 'tool_result' | 'usage' | 'error';
  timestamp: number;
  payload: any;
}

// UI Run Log displays:
// - Status badges (queued/running/completed/failed)
// - Text chunks as assistant message
// - Tool call cards (tool name + input summary)
// - Tool result expandable panels
// - Token usage footer
```

## 5. Skill Injection Strategy

Figure-specific skills in `skills/` directory:

1. **Prompt composition** (like OpenDesign): Include skill content in prompt
2. **Directory exposure** (Claude Code pattern): Pass `--add-dir skills/` for skills that agents can read
3. **Initial skills for OFL**:
   - `scientific-visualization` - Publication-ready matplotlib figures
   - `nature-figure` - Nature journal formatting
   - `scanpy` / `pydeseq2` - Single-cell / RNA-seq pipelines

```python
# In prompt builder:
system_prompt = f"""
You are working on a scientific figure for publication.
Available skills are in: {skills_dir}
Current figure spec: {spec_path}

{user_message}
"""
```

## 6. Security Boundaries and CWD Constraints

| Boundary | Implementation |
|---|---|
| Working directory | Constrain to project workspace (`spec/` + `data/` dirs only) |
| File access | Validate all paths are within project root |
| Process isolation | `CREATE_NEW_PROCESS_GROUP`, no shell injection |
| Model validation | Sanitize against `/api/agents` model list |
| Output filtering | Parse JSON before forwarding; drop malformed lines |
| SSE disconnect | On HTTP close, `proc.terminate()` + `proc.wait()` |

Windows-specific:
- Use `os.path.realpath()` to resolve symlinks before path validation
- Reject paths containing `..` or starting outside project root

## 7. Implementation Sequence

### Phase 1: Basic Run API (Week 1)
- [ ] Add `POST /api/agent-runs` endpoint in server.py
- [ ] Implement agent spawning with `subprocess.Popen`
- [ ] Add basic SSE streaming of stdout
- [ ] Test: Run OpenCode with simple prompt, verify stdout flows to UI

### Phase 2: Structured Events (Week 2)
- [ ] Implement JSON event parser for OpenCode output
- [ ] Add event types: `status`, `text_delta`, `tool_use`, `tool_result`
- [ ] Update UI to render tool call cards
- [ ] Test: Verify tool calls appear in run log

### Phase 3: Multi-Agent Support (Week 3)
- [ ] Add Claude Code (`claude-stream.ts` equivalent)
- [ ] Add Codex (`json-event-stream.ts`)
- [ ] Unify event format across agents
- [ ] Test: Run same prompt on all three agents

### Phase 4: Skill Integration (Week 4)
- [ ] Create `skills/` directory structure
- [ ] Add prompt composition with skill content
- [ ] Add `--add-dir` for Claude Code
- [ ] Test: Agent can read skill files

### Phase 5: Security & Polish (Week 5)
- [ ] Path validation for all file operations
- [ ] Run cancellation (`SIGTERM` on Windows)
- [ ] Error handling and recovery
- [ ] Test: Malicious paths rejected, cancel stops agent

## Verification Steps

1. **Unit**: `test_agent_spawn()` - verify Popen creates process
2. **Integration**: `test_opencode_stream()` - verify JSON events parse
3. **E2E**: Open UI, select OpenCode, enter prompt, see tool calls in run log
4. **Security**: Attempt path traversal, verify rejection
5. **Cancel**: Start long-running agent, click Stop, verify process terminates