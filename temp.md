# Multi-Turn Session & Chat — Future Implementation Reference

> Removed in Phase 4 in favor of stateless single-shot skill runs.
> Restore this when you need persistent chat sessions across turns.

---

## Architecture

```
Chat UI
  └─ POST /chat/start     → creates sandbox, injects CLAUDE.md
  └─ POST /chat/message   → sends message, streams response (--resume <session_id>)
  └─ POST /chat/end       → deletes sandbox
```

Three layers of state persist across turns:
1. **Backend in-memory** (`SessionStore._sessions`): `chat_id → SkillSession`
2. **Sandbox filesystem**: files Claude wrote in turn 1 are there in turn 2
3. **Claude Code history**: `~/.claude/projects/<path>/session.jsonl` inside sandbox

---

## `backend/session.py` — Full Implementation

```python
"""
Session manager — SkillSession + SessionStore.

Each chat session maps to one persistent Daytona sandbox.
The sandbox lives for the entire chat; only the `claude` process
restarts per turn. session_id is captured from the result event and
used with --resume on subsequent turns for reliable history continuity.
"""
import json
import os
from typing import Callable

from daytona import Daytona, DaytonaConfig, CreateSandboxFromSnapshotParams

from .skill_registry import load_skill_md, SkillNotFoundError

SNAPSHOT = os.environ.get("SNAPSHOT_NAME", "company-claude-v1")

_config = DaytonaConfig(
    api_key=os.environ["DAYTONA_API_KEY"],
    api_url=os.environ["DAYTONA_API_URL"],
)


class SkillSession:
    def __init__(self, chat_id: str, sandbox_id: str):
        self.chat_id = chat_id
        self.sandbox_id = sandbox_id
        self.turn = 0
        self.session_id: str | None = None
        self.total_cost_usd: float = 0.0
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0

    def send(self, message: str, on_chunk: Callable[[str], None]) -> None:
        """Run one claude turn, streaming raw stream-json chunks via on_chunk."""
        daytona = Daytona(_config)
        sandbox = daytona.get(self.sandbox_id)

        if self.turn == 0:
            resume_flag = ""
        elif self.session_id:
            resume_flag = f"--resume {self.session_id}"
        else:
            resume_flag = "--continue"

        # Escape single quotes in user message
        safe_msg = message.replace("'", "'\\''")

        cmd = (
            f"claude -p '{safe_msg}' "
            f"{resume_flag} "
            f"--output-format stream-json "
            f"--dangerously-skip-permissions "
            f"--verbose"
        )

        raw_chunks: list[str] = []

        def collect(data: bytes) -> None:
            decoded = data.decode(errors="replace")
            raw_chunks.append(decoded)
            on_chunk(decoded)

        pty = sandbox.process.create_pty_session(
            id=f"{self.chat_id}-turn-{self.turn}",
        )
        pty.wait_for_connection()
        pty.send_input(cmd + "\nexit\n")
        pty.wait(on_data=collect)

        # Extract session_id and accumulate cost/token usage from result event
        for line in "".join(raw_chunks).splitlines():
            try:
                ev = json.loads(line)
                if ev.get("type") == "result":
                    if ev.get("session_id"):
                        self.session_id = ev["session_id"]
                    self.total_cost_usd += ev.get("total_cost_usd") or 0.0
                    usage = ev.get("usage") or {}
                    self.total_input_tokens += usage.get("input_tokens", 0)
                    self.total_output_tokens += usage.get("output_tokens", 0)
                    break
            except json.JSONDecodeError:
                pass

        self.turn += 1

    def delete(self) -> None:
        daytona = Daytona(_config)
        sandbox = daytona.get(self.sandbox_id)
        sandbox.delete()


class SessionStore:
    _sessions: dict[str, SkillSession] = {}

    def create(self, chat_id: str, skill_name: str) -> SkillSession:
        """Create a sandbox, inject the skill CLAUDE.md, return a session."""
        skill_md = load_skill_md(skill_name)

        daytona = Daytona(_config)
        sandbox = daytona.create(
            CreateSandboxFromSnapshotParams(
                snapshot=SNAPSHOT,
                env_vars={
                    "ANTHROPIC_BASE_URL": os.environ["ANTHROPIC_BASE_URL"],
                    "ANTHROPIC_AUTH_TOKEN": os.environ["ANTHROPIC_AUTH_TOKEN"],
                },
                auto_stop_interval=30,
            )
        )

        # Inject skill instructions as CLAUDE.md
        sandbox.fs.upload_file(skill_md, "/home/daytona/CLAUDE.md")

        session = SkillSession(chat_id, sandbox.id)
        self._sessions[chat_id] = session
        return session

    def get(self, chat_id: str) -> SkillSession | None:
        return self._sessions.get(chat_id)

    def destroy(self, chat_id: str) -> None:
        session = self._sessions.pop(chat_id, None)
        if session:
            session.delete()
```

---

## API endpoints for chat (`backend/api.py` additions)

```python
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

## Key design decisions

- **`--resume <session_id>`** over `--continue`: captures session_id from the `result` event on turn 0, uses it from turn 1+. More reliable than `--continue` when sandbox has multiple projects.
- **Sandbox lives across all turns**: only the `claude` process restarts. Filesystem state persists (files, outputs from prior turns).
- **`auto_stop_interval=30`**: sandbox auto-kills after 30 min idle — prevents resource leaks if `/chat/end` is never called.
- **In-memory `SessionStore`**: fine for single-process. For multi-process/worker deployment, replace with Redis: `chat_id → {sandbox_id, turn, session_id}`.
- **Out-of-scope detection**: add a pre-check in `/chat/message` that compares message embedding to skill description (cosine similarity < 0.35 → reject before creating sandbox). See CLAUDE.md section "Handling irrelevant messages".
