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
