import json
import os
import time

from daytona import Daytona, DaytonaConfig, CreateSandboxFromSnapshotParams

from .skill_registry import load_skill_md

SNAPSHOT = os.environ.get("SNAPSHOT_NAME", "company-claude-v1")

_config = DaytonaConfig(
    api_key=os.environ["DAYTONA_API_KEY"],
    api_url=os.environ.get("DAYTONA_API_URL", "http://localhost:3000"),
)


def _format_task(inputs: dict) -> str:
    return "\n".join(f"{k}: {v}" for k, v in inputs.items())


def _parse_output(raw: str) -> str:
    parts = []
    for line in raw.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "assistant":
            for block in ev.get("message", {}).get("content", []):
                if block.get("type") == "text":
                    parts.append(block["text"])
    return "".join(parts)


def _parse_cost(raw: str) -> float:
    for line in raw.splitlines():
        try:
            ev = json.loads(line)
            if ev.get("type") == "result":
                return ev.get("total_cost_usd") or 0.0
        except json.JSONDecodeError:
            continue
    return 0.0


def run_skill(skill_id: str, inputs: dict) -> dict:
    """
    Stateless skill runner: create sandbox → inject CLAUDE.md → run claude -p → delete sandbox.
    Returns {output, execution_time, cost_usd}.
    """
    skill_md = load_skill_md(skill_id)
    task = _format_task(inputs)
    safe_task = task.replace("'", "'\\''")

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

    try:
        sandbox.fs.upload_file(skill_md, "/home/daytona/CLAUDE.md")

        model = os.environ.get("CLAUDE_MODEL", "")
        model_flag = f"--model {model}" if model else ""
        cmd = (
            f"claude -p '{safe_task}' "
            f"{model_flag} "
            f"--output-format stream-json "
            f"--dangerously-skip-permissions "
            f"--verbose"
        )

        chunks: list[str] = []
        start = time.time()

        pty = sandbox.process.create_pty_session(id="skill-run")
        pty.wait_for_connection()
        pty.send_input(cmd + "\nexit\n")
        pty.wait(on_data=lambda data: chunks.append(data.decode(errors="replace")))

        elapsed = time.time() - start
        raw = "".join(chunks)

        return {
            "output": _parse_output(raw),
            "execution_time": elapsed,
            "cost_usd": _parse_cost(raw),
        }
    finally:
        try:
            sandbox.delete()
        except Exception:
            pass
