# Company Skill Platform — Project Context

## What we are building

A centralized internal platform where:
- Admins upload company-specific **skills** (markdown instruction files)
- Employees access a **chat interface** to run tasks using those skills
- Each session runs inside an isolated **Daytona sandbox** with **Claude Code CLI** as the autonomous agent
- The sandbox is the safety boundary — no prod infra access, no data exfiltration risk

---

## Architecture decision: Pattern C — Thin router + agent in sandbox

This was chosen over two alternatives:

**Pattern A (sandbox as tool)** — rejected. Your orchestrator calls `run_code()` as a one-shot function. Too stateless; loses Claude Code's autonomous multi-step capability.

**Pattern B (manager AI + agent AI)** — rejected for most skills. Double API cost, added latency, overkill when skills are already predefined. Only worth adding later for complex multi-skill orchestration.

**Pattern C (chosen)** — thin rule-based router picks the skill, Claude Code runs autonomously inside the sandbox. The skill's `CLAUDE.md` shapes all agent behavior. No AI cost on the routing layer.

```
Chat UI
  └─ Backend orchestrator (rule-based skill router)
       └─ Daytona SDK → localhost:3000
            └─ Sandbox (per session, lives across all turns)
                 ├─ CLAUDE.md injected at session start (skill content)
                 ├─ Claude Code CLI (pre-installed in snapshot)
                 └─ Runs: claude -p "task" --continue --output-format stream-json
```

---

## Daytona setup

- **Self-hosted OSS Daytona running at `http://localhost:3000`**
- API key generated from the local dashboard
- SDK configured via env vars:

```env
DAYTONA_API_URL=http://localhost:3000
DAYTONA_API_KEY=<from local dashboard>
ANTHROPIC_API_KEY=<per user or department>
```

SDK smoke test:

```python
from daytona import Daytona, DaytonaConfig

daytona = Daytona(DaytonaConfig(
    api_key=os.environ["DAYTONA_API_KEY"],
    api_url="http://localhost:3000",
))
sandbox = daytona.create()
print(sandbox.process.exec("echo hello").result)
sandbox.delete()
```

---

## Snapshot design

### What is baked into the snapshot (Dockerfile, built once)

| Layer | What | Why |
|---|---|---|
| Node.js 20 | Runtime for Claude Code | Required |
| Claude Code CLI (pinned version) | `npm install -g @anthropic-ai/claude-code@X.Y.Z` | Zero install latency at session start |
| `/etc/claude-code/managed-settings.json` | Org-wide policy, highest precedence | Engineers can't override tool permissions |
| `~/.claude/settings.json` | Default model, auto-compact | Consistent behaviour |
| Company tools / runtimes | Python, internal CLIs, pip packages | Available to agent immediately |
| Directory structure | `/home/daytona/skills/`, `/output/`, `/workspace/` | Skills expect these paths |
| `DISABLE_AUTOUPDATER=1` | Env var | Version stability across all sandboxes |

### What is injected at runtime (never baked in)

| What | When | How |
|---|---|---|
| `ANTHROPIC_API_KEY` | Sandbox creation | `env_vars={"ANTHROPIC_API_KEY": ...}` |
| `CLAUDE.md` (skill content) | Session start | `sandbox.filesystem.upload_file(...)` |
| User input files / data | Per task | `sandbox.filesystem.upload_file(...)` |

**Never bake in API keys or skill content.** Keys are a security risk; skills change often and belong in the skill registry.

### Dockerfile

```dockerfile
FROM ubuntu:22.04
ARG CLAUDE_VERSION=2.1.94

ENV DEBIAN_FRONTEND=noninteractive
ENV DISABLE_AUTOUPDATER=1
ENV NODE_VERSION=20

RUN apt-get update && apt-get install -y \
    curl git python3 python3-pip jq unzip \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - \
    && apt-get install -y nodejs

RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_VERSION}

RUN mkdir -p /etc/claude-code
COPY managed-settings.json /etc/claude-code/managed-settings.json

RUN mkdir -p /home/daytona/.claude
COPY claude-settings.json /home/daytona/.claude/settings.json

RUN mkdir -p /home/daytona/skills \
             /home/daytona/output \
             /home/daytona/workspace \
             /home/daytona/.claude/projects

RUN pip3 install pandas matplotlib requests openpyxl --break-system-packages

RUN touch /home/daytona/CLAUDE.md

WORKDIR /home/daytona
```

### managed-settings.json

```json
{
  "permissions": {
    "allow": ["Bash", "Read", "Write", "Edit", "Glob", "Grep"],
    "deny": []
  },
  "autoUpdaterStatus": "disabled",
  "env": {
    "DISABLE_AUTOUPDATER": "1"
  }
}
```

### claude-settings.json

```json
{
  "model": "claude-sonnet-4-20250514",
  "autoCompact": true
}
```

### Build and register

```bash
# Build for AMD64 (Daytona requires this)
docker buildx build --platform linux/amd64 -t company-claude:1.0.0 --load .

# Register as a named snapshot
daytona snapshot push company-claude:1.0.0 \
  --name company-claude-v1 \
  --cpu 2 --memory 4 --disk 8

# Or let Daytona build directly from Dockerfile
daytona snapshot create \
  --name company-claude-v1 \
  --dockerfile ./Dockerfile \
  --context .
```

---

## Skill format

Each skill is a directory in the skill registry:

```
skills/
  data-report/
    CLAUDE.md          ← injected into sandbox as /home/daytona/CLAUDE.md
    metadata.yaml      ← name, tags, version, description
  code-review/
    CLAUDE.md
    metadata.yaml
```

### CLAUDE.md structure for a skill

```markdown
# Skill: <name>
<!-- version: 1.0 | owner: <team> -->

## Context
You are running inside a Daytona sandbox for <Company>.
Working directory: /home/daytona/workspace
Output directory: /home/daytona/output
Available tools: <list company CLIs, Python libs>

## Your task
<What the agent should accomplish. Be specific.>

## Constraints
- Never access external URLs except <allowed domains>
- Write all outputs to /home/daytona/output/
- Log steps to /home/daytona/output/run.log
- <any skill-specific rules>
```

### metadata.yaml

```yaml
name: data-report
display_name: "Data Report Generator"
description: "Generates formatted reports from raw data files"
tags: [analytics, reporting, data]
version: "1.2"
owner: analytics-team
```

---

## Multi-turn session management

### Core concept

The **sandbox lives for the entire chat session**. Only the `claude` process dies and restarts per turn.

Three layers of state persist across turns:

1. **Backend** (Redis/DB): `chat_id → sandbox_id`, `turn_count`
2. **Sandbox filesystem**: files Claude wrote in turn 1 are there in turn 2
3. **Claude Code conversation history**: `~/.claude/projects/<path>/session.jsonl` inside the sandbox

### How turns work

```
Turn 1:  claude -p "build a report"    --output-format stream-json --dangerously-skip-permissions
Turn 2:  claude -p "add charts"        --continue --output-format stream-json ...
Turn N:  claude -p "export as PDF"     --continue --output-format stream-json ...
```

`--continue` picks up the most recent session from `~/.claude/` in the sandbox. Since each sandbox has exactly one session, no session ID tracking is needed.

**Do not use `--resume <session-id>` unless you specifically need to track multiple sessions per sandbox.** `--continue` is simpler and more reliable.

Claude Code auto-compacts the conversation at ~95% context usage — this is transparent, no handling needed.

---

## Session manager implementation (Python)

```python
# session.py
import os, asyncio
from daytona import AsyncDaytona, DaytonaConfig

config = DaytonaConfig(
    api_key=os.environ["DAYTONA_API_KEY"],
    api_url="http://localhost:3000",
)

class SkillSession:
    def __init__(self, chat_id: str, sandbox_id: str):
        self.chat_id = chat_id
        self.sandbox_id = sandbox_id
        self.turn = 0

    async def send(self, message: str, on_chunk):
        async with AsyncDaytona(config) as daytona:
            sandbox = await daytona.get(self.sandbox_id)
            continue_flag = "--continue" if self.turn > 0 else ""
            cmd = (
                f"claude -p '{message}' "
                f"{continue_flag} "
                f"--output-format stream-json "
                f"--dangerously-skip-permissions "
                f"--verbose"
            )
            pty = await sandbox.process.create_pty_session(
                id=f"turn-{self.turn}",
                on_data=lambda data: on_chunk(data.decode(errors="replace"))
            )
            await pty.wait_for_connection()
            await pty.send_input(cmd + "\n")
            await pty.wait()
        self.turn += 1


class SessionStore:
    _sessions: dict[str, SkillSession] = {}

    async def create(self, chat_id: str, skill_name: str) -> SkillSession:
        async with AsyncDaytona(config) as daytona:
            sandbox = await daytona.create(
                snapshot="company-claude-v1",
                env_vars={"ANTHROPIC_API_KEY": os.environ["ANTHROPIC_API_KEY"]},
                auto_stop_interval=30,
            )
            skill_md = await load_skill(skill_name)
            await sandbox.filesystem.upload_file(
                "/home/daytona/CLAUDE.md", skill_md.encode()
            )
        session = SkillSession(chat_id, sandbox.id)
        self._sessions[chat_id] = session
        return session

    def get(self, chat_id: str) -> SkillSession | None:
        return self._sessions.get(chat_id)

    async def destroy(self, chat_id: str):
        session = self._sessions.pop(chat_id, None)
        if session:
            async with AsyncDaytona(config) as daytona:
                sandbox = await daytona.get(session.sandbox_id)
                await sandbox.delete()
```

---

## API endpoints (FastAPI)

```python
# api.py
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio

app = FastAPI()
store = SessionStore()

@app.post("/chat/start")
async def start_chat(payload: dict):
    skill = match_skill(payload["first_message"])
    session = await store.create(payload["chat_id"], skill)
    return {"sandbox_ready": True, "skill": skill}

@app.post("/chat/message")
async def chat_message(payload: dict):
    session = store.get(payload["chat_id"])
    if not session:
        skill = match_skill(payload["message"])
        session = await store.create(payload["chat_id"], skill)

    queue = asyncio.Queue()

    async def run():
        await session.send(payload["message"], lambda c: asyncio.create_task(queue.put(c)))
        await queue.put(None)

    asyncio.create_task(run())

    async def stream():
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk

    return StreamingResponse(stream(), media_type="text/event-stream")

@app.post("/chat/end")
async def end_chat(payload: dict):
    await store.destroy(payload["chat_id"])
    return {"deleted": True}
```

---

## Project structure (recommended)

```
company-skill-platform/
├── snapshot/
│   ├── Dockerfile
│   ├── managed-settings.json
│   └── claude-settings.json
├── skills/                        ← skill registry (could also be S3/DB)
│   ├── data-report/
│   │   ├── CLAUDE.md
│   │   └── metadata.yaml
│   └── code-review/
│       ├── CLAUDE.md
│       └── metadata.yaml
├── backend/
│   ├── api.py                     ← FastAPI endpoints
│   ├── session.py                 ← SkillSession + SessionStore
│   ├── skill_registry.py          ← load/match skills
│   └── router.py                  ← rule-based skill matcher
├── frontend/                      ← chat UI (Next.js / SvelteKit)
└── .env
```

---

## Implementation phases

| Phase | Task | Status |
|---|---|---|
| 0 | Connect SDK to `localhost:3000`, smoke test | Todo |
| 1 | Build Dockerfile, register snapshot, verify Claude Code runs | Todo |
| 2 | Skill registry — file-based loader + metadata schema | Todo |
| 3 | Session manager — create / send / destroy | Todo |
| 4 | FastAPI backend — 3 endpoints + SSE streaming | Todo |
| 5 | Chat UI — connect to backend, render stream-json output | Todo |
| 6 | Hardening — per-user API keys, audit log, kill switch | Todo |

---

## Key constraints to remember

- **AMD64 only**: All snapshot images must be built with `--platform linux/amd64`
- **`--continue` not `--resume`**: Use `--continue` for multi-turn; `--resume <id>` had a bug in older versions and is unnecessary when one sandbox = one session
- **`--dangerously-skip-permissions`**: Safe inside Daytona because the sandbox is already isolated — this just prevents interactive permission prompts that would block the PTY
- **API key never in image**: Always injected as `env_vars` at `daytona.create()` time
- **CLAUDE.md is the control plane**: All agent behavior is shaped here, not in the orchestrator
- **`AsyncDaytona` preferred**: Has automatic `on_data` callbacks; the sync client needs manual threading for streaming
- **Auto-stop**: Always set `auto_stop_interval=30` to kill idle sandboxes and avoid resource waste
- **stream-json output format**: Each line is a JSON object. Parse `type` field — `assistant` for content, `result` for final output with `session_id` and `total_cost_usd`

---

## stream-json output parsing reference

```python
import json

def parse_stream_chunk(raw: str):
    for line in raw.strip().splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        match event.get("type"):
            case "assistant":
                # content blocks — text the agent is writing
                for block in event.get("message", {}).get("content", []):
                    if block.get("type") == "text":
                        yield {"type": "text", "text": block["text"]}
                    elif block.get("type") == "tool_use":
                        yield {"type": "tool", "name": block["name"]}
            case "result":
                # final event — has session_id, cost, is_error
                yield {
                    "type": "done",
                    "session_id": event.get("session_id"),
                    "cost_usd": event.get("total_cost_usd"),
                    "is_error": event.get("is_error", False),
                }
            case "system":
                # init event at the start of each turn
                pass
```

---

## Snapshot versioning convention

```
company-claude-v1    ← production
company-claude-v2    ← staged / canary (route 5% of sessions here)
```

To upgrade: bump `CLAUDE_VERSION` in Dockerfile, rebuild, push as `company-claude-v2`, update orchestrator after validation.
