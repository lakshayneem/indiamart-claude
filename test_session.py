"""
Phase 3 test — SkillSession multi-turn with PTY streaming.

Turn 1: ask claude to write a secret number to a file
Turn 2: ask claude to recall the number (tests --continue + filesystem persistence)

Run: .venv/Scripts/python test_session.py
"""
import os, sys, json
from dotenv import load_dotenv

load_dotenv()

required = ["DAYTONA_API_KEY", "DAYTONA_API_URL", "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN"]
missing = [k for k in required if not os.environ.get(k)]
if missing:
    print(f"ERROR: missing env vars: {missing}")
    sys.exit(1)

from backend.session import SessionStore


def collect_text(raw: str) -> str:
    """Extract assistant text from stream-json chunks."""
    text = []
    for line in raw.strip().splitlines():
        try:
            ev = json.loads(line)
            if ev.get("type") == "assistant":
                for block in ev.get("message", {}).get("content", []):
                    if block.get("type") == "text" and block["text"].strip():
                        text.append(block["text"].strip())
            elif ev.get("type") == "result" and ev.get("is_error"):
                text.append(f"[ERROR] {ev}")
        except json.JSONDecodeError:
            pass
    return "\n".join(text)


def print_tool_calls(raw: str) -> None:
    """Print each tool call Claude made, plus final cost/usage."""
    for line in raw.strip().splitlines():
        try:
            ev = json.loads(line)
            if ev.get("type") == "assistant":
                for block in ev.get("message", {}).get("content", []):
                    if block.get("type") == "tool_use":
                        inp = block.get("input", {})
                        detail = inp.get("command") or inp.get("path") or inp.get("file_path") or ""
                        print(f"    [tool] {block['name']}  {detail}")
            elif ev.get("type") == "result":
                cost = ev.get("total_cost_usd")
                usage = ev.get("usage", {})
                print(f"    [cost] ${cost:.6f}" if cost else "    [cost] n/a")
                if usage:
                    print(f"    [tokens] input={usage.get('input_tokens',0)}  output={usage.get('output_tokens',0)}")
        except json.JSONDecodeError:
            pass


def main():
    store = SessionStore()
    chat_id = "test-session-001"

    print("=== Phase 3: Session Manager Test ===\n")

    # --- Turn 1 ---
    print("Creating session with skill: hello-world")
    session = store.create(chat_id, "hello-world")
    print(f"  sandbox id: {session.sandbox_id}\n")

    print("Turn 1: Write a secret number to a file")
    chunks = []
    session.send(
        "Write the number 42 to /home/daytona/output/secret.txt, then tell me you've done it.",
        on_chunk=lambda c: chunks.append(c)
    )
    turn1_raw = "".join(chunks)
    turn1_output = collect_text(turn1_raw)
    print(f"  Claude: {turn1_output[:300]}")
    print_tool_calls(turn1_raw)

    # --- Turn 2 ---
    print("\nTurn 2: Ask claude to recall the number (tests --continue)")
    chunks2 = []
    session.send(
        "What number did you write to the file in your previous turn?",
        on_chunk=lambda c: chunks2.append(c)
    )
    turn2_raw = "".join(chunks2)
    turn2_output = collect_text(turn2_raw)
    print(f"  Claude: {turn2_output[:300]}")
    print_tool_calls(turn2_raw)

    assert "42" in turn2_output, f"Expected '42' in turn 2 response, got: {turn2_output}"
    print("\nTurn 2 memory check PASSED — claude remembered across turns.")

    # --- Cleanup ---
    print("\nDestroying session...")
    store.destroy(chat_id)
    print("Phase 3 PASSED.")


if __name__ == "__main__":
    main()
