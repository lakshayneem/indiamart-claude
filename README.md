# Company Skill Platform

An internal platform where employees run AI-powered tasks through a chat interface. Each session runs inside an isolated [Daytona](https://daytona.io) sandbox with [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) as the autonomous agent.

---

## How It Works

```
Employee (Chat UI)
  └─ FastAPI Backend  ←─ skill router picks the right CLAUDE.md
       └─ Daytona SDK → localhost:3000
            └─ Sandbox (one per chat session)
                 ├─ CLAUDE.md injected at session start
                 ├─ Claude Code CLI (pre-installed in snapshot)
                 └─ claude -p "..." --resume <id> --output-format stream-json
```

Skills are plain markdown files. Admins write or update them without touching any backend code. Claude Code reads the skill's `CLAUDE.md` and executes the task autonomously inside the sandbox.

---

## Project Structure

```
├── snapshot/                  # Daytona sandbox image (built once)
│   ├── Dockerfile
│   ├── managed-settings.json  # Org-wide Claude tool permissions
│   └── claude-settings.json   # Model config, autoCompact
├── skills/                    # Skill registry
│   ├── hello-world/
│   │   ├── CLAUDE.md
│   │   └── metadata.yaml
│   └── code-review/
│       ├── CLAUDE.md
│       └── metadata.yaml
├── backend/
│   ├── session.py             # SkillSession + SessionStore
│   ├── skill_registry.py      # load / list skills
│   ├── api.py                 # FastAPI endpoints (Phase 4)
│   └── router.py              # Rule-based skill matcher (Phase 4)
├── smoke_test.py              # Phase 0 — SDK connectivity test
├── test_snapshot.py           # Phase 1 — Claude Code inside sandbox
├── test_session.py            # Phase 3 — multi-turn session test
├── CHECKLIST.md               # Build progress
└── WORKFLOW.md                # Architecture, objectives, decisions
```

---

## Setup

### Prerequisites

- Python 3.11
- Daytona self-hosted OSS running at `http://localhost:3000`
- Docker (for building the snapshot image)

### Install

```bash
python3.11 -m venv .venv
.venv/Scripts/activate       # Windows
# source .venv/bin/activate  # Linux/Mac

pip install -e daytona/libs/sdk-python --no-deps
pip install -e daytona/libs/api-client-python --no-deps
pip install -e daytona/libs/api-client-python-async --no-deps
pip install -e daytona/libs/toolbox-api-client-python --no-deps
pip install -e daytona/libs/toolbox-api-client-python-async --no-deps
pip install python-dotenv fastapi uvicorn
```

### Configure

Copy `.env.example` to `.env` and fill in your values:

```env
DAYTONA_API_URL=http://localhost:3000/api
DAYTONA_API_KEY=<from Daytona dashboard>
ANTHROPIC_BASE_URL=<your LLM gateway URL>
ANTHROPIC_AUTH_TOKEN=<your auth token>
```

### Build the Snapshot

```bash
cd snapshot
docker buildx build --platform linux/amd64 -t company-claude:1.0.0 --load .

# Register with Daytona (adjust registry URL as needed)
curl -X POST http://localhost:3000/api/snapshots \
  -H "Authorization: Bearer $DAYTONA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"company-claude-v1","imageName":"registry:6000/company-claude:1.0.0"}'
```

---

## Testing

```bash
# Phase 0 — SDK smoke test
python smoke_test.py

# Phase 1 — Claude Code in sandbox
python test_snapshot.py

# Phase 3 — Multi-turn session (turn 1 writes file, turn 2 recalls it)
python test_session.py
```

---

## Adding a Skill

1. Create `skills/<skill-name>/CLAUDE.md` — write the agent's instructions
2. Create `skills/<skill-name>/metadata.yaml`:

```yaml
name: my-skill
display_name: "My Skill"
description: "What this skill does"
tags: [tag1, tag2]
version: "1.0"
owner: your-team
```

No backend changes needed — the skill is available immediately.

---

## Key Design Decisions

| Decision | Reason |
|---|---|
| Pattern C (thin router + agent in sandbox) | No AI cost on routing layer; skill's CLAUDE.md shapes all behavior |
| `--resume <session_id>` over `--continue` | `--continue` relies on cwd hash which can mismatch across PTY sessions |
| Model in `claude-settings.json`, not `--model` flag | Gateway rejects model name passed via flag |
| Non-root `daytona` user in snapshot | Claude Code blocks `--dangerously-skip-permissions` as root |
| AMD64 image build | Daytona requires linux/amd64 |
| API key injected at runtime | Never baked into image — security requirement |

---

## Build Status

| Phase | Description | Status |
|---|---|---|
| 0 | SDK smoke test | ✅ Done |
| 1 | Snapshot build + Claude Code verification | ✅ Done |
| 2 | Skill registry | ✅ Done |
| 3 | Session manager + PTY streaming + multi-turn | ✅ Done |
| 4 | FastAPI backend + SSE streaming | 🔲 Next |
| 5 | Chat UI | 🔲 Planned |
| 6 | Hardening + audit log | 🔲 Planned |
