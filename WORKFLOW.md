# Company Skill Platform — Workflow & Objectives

## What We Are Building

An internal platform that lets employees run AI-powered tasks through a chat interface, where each task is governed by a company-defined **skill** (a markdown instruction file). Every chat session runs inside an isolated **Daytona sandbox** with **Claude Code CLI** as the autonomous agent. The sandbox is the security boundary — no production infrastructure access, no data exfiltration risk.

---

## Core Architecture

```
Employee (Chat UI)
  └─ FastAPI Backend  ←─ skill router picks the right CLAUDE.md
       └─ Daytona SDK  →  localhost:3000
            └─ Sandbox (one per chat session, lives across all turns)
                 ├─ CLAUDE.md injected at session start  ← skill instructions
                 ├─ Claude Code CLI 2.1.94 (pre-installed in snapshot)
                 └─ claude -p "..." --resume <id> --output-format stream-json
```

**Why this design:**
- Skills are just markdown — any admin can write or update them without touching code
- Claude Code runs autonomously inside the sandbox — it can read files, run Bash, write outputs
- The sandbox is ephemeral — destroyed after the session ends, taking all intermediate data with it
- SSE streaming means the employee sees Claude's response in real time, token by token

---

## Infrastructure

| Component | Detail |
|---|---|
| Daytona | Self-hosted OSS at `http://localhost:3000` |
| Snapshot | `company-claude-v1` — Docker image with Node 20, Claude Code 2.1.94, Python libs |
| LLM Gateway | IMLLM at `https://imllm.intermesh.net` — internal Anthropic proxy |
| Model | `anthropic/claude-sonnet-4-6` set in `claude-settings.json` inside snapshot |
| Auth token | `ANTHROPIC_AUTH_TOKEN` injected at sandbox creation, never baked into image |
| OTel tracing | SDK traces exported to local collector → Jaeger at `localhost:16686` |

---

## What We Have Built

### Phase 0 — SDK Smoke Test ✅
- Python 3.11 venv with Daytona SDK (local monorepo) installed
- `smoke_test.py` — creates a sandbox, runs `echo hello`, deletes it
- Confirmed SDK talks to Daytona at `localhost:3000/api`

### Phase 1 — Snapshot ✅
- `snapshot/Dockerfile` — node:20-bookworm-slim, non-root `daytona` user, Claude Code 2.1.94
- `snapshot/managed-settings.json` — org-wide tool permissions (Bash/Read/Write/Edit/Glob/Grep allowed)
- `snapshot/claude-settings.json` — model pinned to `anthropic/claude-sonnet-4-6`, autoCompact on
- Image built for linux/amd64, pushed to internal registry at `registry:6000`
- Snapshot registered as `company-claude-v1` via Daytona API
- Verified: `claude --version` runs inside sandbox, stream-json output confirmed

### Phase 2 — Skill Registry ✅
- `skills/hello-world/` and `skills/code-review/` — each with `CLAUDE.md` + `metadata.yaml`
- `backend/skill_registry.py` — `load_skill_md()`, `list_skills()`, `skill_exists()`
- Skills are plain files; future migration to S3/DB is a drop-in swap

### Phase 3 — Session Manager ✅
- `backend/session.py` — `SkillSession` + `SessionStore`
- PTY streaming: `create_pty_session` → `send_input` → `wait(on_data=...)` — chunks stream in real time
- Multi-turn memory: `session_id` captured from `result` event, passed as `--resume <id>` on turn 2+
- Cost/token tracking: `total_cost_usd`, `total_input_tokens`, `total_output_tokens` accumulated per session
- `test_session.py` — two-turn test confirmed: Turn 1 writes file, Turn 2 recalls it correctly

**Key fixes discovered:**
- PTY hangs if shell doesn't exit → send `exit\n` after `claude` command
- `--continue` is unreliable (working-directory hash mismatch) → use `--resume <session_id>` explicitly
- Model must be set in `claude-settings.json`, not via `--model` flag (gateway bug with flag)

---

## What We Plan to Build

### Phase 4 — FastAPI Backend
- `backend/api.py` — three endpoints:
  - `POST /chat/start` — match skill, create sandbox, return `sandbox_ready`
  - `POST /chat/message` — run one turn, stream response as SSE
  - `POST /chat/end` — destroy sandbox, return cost summary
- `backend/router.py` — rule-based skill matcher (keyword/tag matching against `metadata.yaml`)
- SSE format: each chunk forwarded as `data: <raw stream-json line>\n\n`
- Goal: testable end-to-end with `curl`

### Phase 5 — Chat UI
- Frontend scaffold (Next.js or SvelteKit)
- Connects to `/chat/message` SSE stream
- Renders assistant text blocks in real time
- Shows tool-use events as status indicators (e.g. "Running Bash...", "Writing file...")
- Session lifecycle: start on first message, end on tab close / explicit button

### Phase 6 — Hardening & Audit
- **Per-user token injection** — each user gets their own `ANTHROPIC_AUTH_TOKEN` passed at sandbox creation
- **Audit log** — per-turn record of `user_id`, `session_id`, `turn`, `cost_usd`, `input_tokens`, `output_tokens`, `tool_calls[]` written to DB
- **Audit page** — admin view showing cost and usage per user, per skill, per day
- **Kill switch** — admin endpoint to force-delete any live sandbox immediately
- **Sandbox auto-stop** — `auto_stop_interval=30` enforced on all creates (already in place)

---

## Data We Collect Per Turn (for Audit)

From the `result` event in stream-json output:

| Field | Source | Use |
|---|---|---|
| `session_id` | `result.session_id` | Link turns to a session |
| `cost_usd` | `result.total_cost_usd` | Per-turn and per-user billing visibility |
| `input_tokens` | `result.usage.input_tokens` | Usage tracking |
| `output_tokens` | `result.usage.output_tokens` | Usage tracking |
| `tool_calls` | `assistant` events, `tool_use` blocks | What Claude actually did (Bash cmds, files written) |

`SkillSession` accumulates these across turns. On `SessionStore.destroy()`, the totals get flushed to the audit DB tied to the `user_id`.

---

## Skill Format (for Admins)

```
skills/
  <skill-name>/
    CLAUDE.md       ← injected into sandbox as /home/daytona/CLAUDE.md at session start
    metadata.yaml   ← name, description, tags, version, owner
```

`CLAUDE.md` is the only control plane for agent behavior. The backend orchestrator does not shape what Claude does — the skill file does. Admins can update a skill without any backend deploy.

---

## Key Constraints

- **AMD64 only** — all snapshot images built with `--platform linux/amd64`
- **Non-root user** — sandbox runs as `daytona` user; Claude Code blocks `--dangerously-skip-permissions` as root
- **API key never in image** — always injected as `env_vars` at `daytona.create()` time
- **`--resume` not `--continue`** — `--continue` uses cwd hash which can mismatch across PTY sessions; `--resume <session_id>` is explicit and reliable
- **Model in settings, not flag** — `anthropic/claude-sonnet-4-6` set in `claude-settings.json`; passing via `--model` flag causes a gateway error
- **OTel traces** — SDK operations visible in Jaeger at `localhost:16686`; Claude's internal tool calls are in stream-json only
