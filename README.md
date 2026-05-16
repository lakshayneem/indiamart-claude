# IM Agentic OS — Company Skill Platform

An internal platform where IndiaMART employees run AI-powered tasks through a Streamlit dashboard. Each skill run executes inside an isolated [Daytona](https://daytona.io) sandbox with [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) as the autonomous agent.

---

## How It Works

```
Employee (Streamlit UI)
  └─ FastAPI Backend  ←─ receives skill_id + inputs
       └─ Daytona SDK → localhost:3000
            └─ Sandbox (spun up per run, deleted after)
                 ├─ CLAUDE.md injected (skill instructions)
                 ├─ Claude Code CLI (pre-installed in snapshot)
                 └─ claude -p "<inputs>" --model <model> --output-format stream-json
```

Skills are plain markdown files. Admins write or update them without touching any backend code. Claude Code reads the skill's `CLAUDE.md` and executes the task autonomously inside the sandbox — then the sandbox is deleted.

---

## Project Structure

```
├── snapshot/                   # Daytona sandbox image (built once)
│   ├── Dockerfile
│   ├── managed-settings.json   # Org-wide Claude tool permissions
│   └── claude-settings.json    # autoCompact config
├── skills/                     # Skill registry
│   ├── hello-world/
│   │   ├── CLAUDE.md           # Agent instructions for this skill
│   │   └── metadata.yaml
│   ├── data-report/
│   └── code-review/
├── backend/
│   ├── api.py                  # FastAPI — GET /health, POST /run-skill
│   ├── skill_runner.py         # Stateless runner: sandbox → CLAUDE.md → claude -p → delete
│   └── skill_registry.py       # Load / list skills from skills/ directory
├── test_snapshot.py            # Phase 1 — verify Claude Code runs in sandbox
├── test_skill_runner.py        # Phase 4 — end-to-end skill run test
├── requirements.txt
└── .env.example
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
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # Linux/Mac

pip install -e daytona/libs/sdk-python --no-deps
pip install -e daytona/libs/api-client-python --no-deps
pip install -e daytona/libs/api-client-python-async --no-deps
pip install -e daytona/libs/toolbox-api-client-python --no-deps
pip install -e daytona/libs/toolbox-api-client-python-async --no-deps
pip install -r requirements.txt
```

### Configure

Copy `.env.example` to `.env` and fill in your values:

```env
DAYTONA_API_URL=http://localhost:3000/api
DAYTONA_API_KEY=<from Daytona dashboard>
ANTHROPIC_BASE_URL=<your LLM gateway URL>
ANTHROPIC_AUTH_TOKEN=<your auth token>
CLAUDE_MODEL=anthropic/claude-sonnet-4
SNAPSHOT_NAME=company-claude-v1
```

### Build the Snapshot

```bash
cd snapshot
docker buildx build --platform linux/amd64 -t company-claude:1.0.0 --load .

# Register with Daytona
curl -X POST http://localhost:3000/api/snapshots \
  -H "Authorization: Bearer $DAYTONA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"company-claude-v1","imageName":"registry:6000/company-claude:1.0.0"}'
```

---

## Running

### Backend (FastAPI)

```bash
.venv/Scripts/python -m uvicorn backend.api:app --host 0.0.0.0 --port 8000
```

Endpoints:
- `GET /health` → `{"status": "ok"}`
- `POST /run-skill` → `{"skill_id": "...", "inputs": {...}}`

### Frontend (Streamlit)

The Streamlit app (`im-agentic-os/`) connects to the backend at `http://localhost:8000`.

```bash
cd im-agentic-os
.venv/Scripts/activate
streamlit run app.py
```

---

## Testing

```bash
# Phase 1 — verify Claude Code runs inside the snapshot
.venv/Scripts/python test_snapshot.py

# Phase 4 — end-to-end skill run (creates sandbox, runs skill, deletes sandbox)
.venv/Scripts/python test_skill_runner.py
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

No backend changes needed — the skill is picked up automatically.

---

## Key Design Decisions

| Decision | Reason |
|---|---|
| Stateless per-run sandbox | No idle resource cost; each run is fully isolated |
| Pattern C (thin router + agent in sandbox) | No AI cost on routing; skill's `CLAUDE.md` shapes all behavior |
| `CLAUDE_MODEL` in `.env`, passed via `--model` flag | Model can be changed without rebuilding the snapshot |
| Non-root `daytona` user in snapshot | Claude Code blocks `--dangerously-skip-permissions` as root |
| AMD64 image build | Daytona requires `linux/amd64` |
| API key injected at runtime | Never baked into image — security requirement |

---

## Build Status

| Phase | Description | Status |
|---|---|---|
| 0 | SDK smoke test | ✅ Done |
| 1 | Snapshot build + Claude Code verification | ✅ Done |
| 2 | Skill registry | ✅ Done |
| 3 | Session manager (replaced by stateless runner) | ✅ Done |
| 4 | FastAPI backend + stateless skill runner | ✅ Done |
| 5 | Streamlit frontend (`im-agentic-os`) | ✅ Done |
