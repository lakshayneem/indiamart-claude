# Company Skill Platform — Build Checklist

## Current Focus: Daytona Snapshot + Claude Code Verification

---

## Phase 0 — SDK Smoke Test
- [x] Install Daytona Python SDK (local `daytona/libs/sdk-python`) — Python 3.11 venv at `.venv/`
- [x] Create `.env` with `DAYTONA_API_KEY`, `DAYTONA_API_URL`, `ANTHROPIC_API_KEY`
- [x] Run `smoke_test.py` — create sandbox, exec `echo hello`, delete sandbox

## Phase 1 — Build Snapshot & Verify Claude Code
- [x] Create `snapshot/Dockerfile`
- [x] Create `snapshot/managed-settings.json`
- [x] Create `snapshot/claude-settings.json`
- [x] Build Docker image (`--platform linux/amd64`) — `company-claude:1.0.1` with non-root `daytona` user
- [x] Register snapshot with Daytona — `company-claude-v1` via API (registry:6000)
- [x] Create sandbox from snapshot via SDK
- [x] Verify `claude --version` runs inside sandbox — `2.1.94 (Claude Code)`
- [x] Verify stream-json output — `system → assistant → result` events confirmed

## Phase 2 — Skill Registry
- [x] Create `skills/` directory structure
- [x] Write `skills/hello-world/CLAUDE.md` + `metadata.yaml`
- [x] Write `skills/code-review/CLAUDE.md` + `metadata.yaml`
- [x] Write `backend/skill_registry.py` — list_skills, load_skill_md, skill_exists

## Phase 3 — Session Manager
- [x] Write `backend/session.py` — `SkillSession` + `SessionStore`
- [x] Test turn 1 (no `--continue`)
- [x] Test turn 2+ (`--resume <session_id>`, picks up prior conversation)
- [x] Test sandbox filesystem persistence across turns

## Phase 4 — FastAPI Backend
- [ ] Write `backend/api.py` — `/chat/start`, `/chat/message`, `/chat/end`
- [ ] Write `backend/router.py` — rule-based skill matcher
- [ ] Test SSE streaming with `curl`

## Phase 5 — Chat UI
- [ ] Scaffold frontend (Next.js or SvelteKit)
- [ ] Connect to backend SSE stream
- [ ] Render `assistant` text blocks in real time
- [ ] Show tool-use events as status indicators


## Phase 6 — Hardening
- [ ] Per-user `ANTHROPIC_AUTH_TOKEN` injection
- [ ] Audit log per turn — `session_id`, `cost_usd`, `input_tokens`, `output_tokens`, `user_id` written to DB
- [ ] Aggregate cost/token report per user (uses `SkillSession.total_cost_usd` + token fields)
- [ ] Kill switch endpoint to force-delete a sandbox
- [ ] `auto_stop_interval=30` confirmed on all sandbox creates

---

## Notes
- Daytona running at `http://localhost:3000`
- SDK source: `daytona/libs/sdk-python/`
- AMD64 mandatory for all snapshot images
- Never bake API keys into images
