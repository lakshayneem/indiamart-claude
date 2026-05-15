"""
Phase 1 test — create sandbox from company-claude-v1 snapshot,
verify claude CLI is present, run a simple prompt, parse stream-json output.

Run: python test_snapshot.py
Requires: snapshot registered as 'company-claude-v1' in Daytona
"""
import os, sys, json
from dotenv import load_dotenv

load_dotenv()

required = ["DAYTONA_API_KEY", "DAYTONA_API_URL", "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN"]
missing = [k for k in required if not os.environ.get(k)]
if missing:
    print(f"ERROR: missing env vars: {missing}")
    sys.exit(1)

from daytona import Daytona, DaytonaConfig, CreateSandboxFromSnapshotParams

SNAPSHOT = os.environ.get("SNAPSHOT_NAME", "company-claude-v1")

def parse_stream(raw: str):
    events = []
    for line in raw.strip().splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return events

def main():
    config = DaytonaConfig(
        api_key=os.environ["DAYTONA_API_KEY"],
        api_url=os.environ["DAYTONA_API_URL"],
    )
    daytona = Daytona(config)

    print(f"Creating sandbox from snapshot '{SNAPSHOT}'...")
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
    print(f"  sandbox id: {sandbox.id}")

    print("Checking claude --version...")
    result = sandbox.process.exec("claude --version")
    print(f"  {result.result.strip()}")
    assert "claude" in result.result.lower(), "claude CLI not found in snapshot"

    print("Running: claude -p 'Reply with just the word HELLO' --output-format stream-json --dangerously-skip-permissions")
    cmd = (
        "claude -p 'Reply with just the word HELLO' "
        "--output-format stream-json "
        "--dangerously-skip-permissions "
        "--verbose"
    )
    result = sandbox.process.exec(cmd, timeout=60)
    raw = result.result
    print("  Raw output (first 500 chars):")
    print("  " + raw[:500].replace("\n", "\n  "))

    events = parse_stream(raw)
    types = [e.get("type") for e in events]
    print(f"  Event types seen: {types}")

    has_result = any(e.get("type") == "result" for e in events)
    assert has_result, "No 'result' event in stream-json output"
    print("Phase 1 PASSED — claude runs inside the snapshot sandbox.")

    print("Deleting sandbox...")
    sandbox.delete()

if __name__ == "__main__":
    main()
