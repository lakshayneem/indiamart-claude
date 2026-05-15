"""
Phase 4 test — stateless skill runner.

Runs the hello-world skill with a name input, checks that the output contains a greeting.

Run: .venv/Scripts/python test_skill_runner.py
"""
import os, sys
from dotenv import load_dotenv

load_dotenv()

required = ["DAYTONA_API_KEY", "DAYTONA_API_URL", "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN"]
missing = [k for k in required if not os.environ.get(k)]
if missing:
    print(f"ERROR: missing env vars: {missing}")
    sys.exit(1)

from backend.skill_runner import run_skill

def main():
    print("=== Phase 4: Skill Runner Test ===\n")

    print("Running skill: hello-world")
    print("  inputs: {name: 'Lakshay'}\n")

    result = run_skill("hello-world", {"name": "Lakshay"})

    safe = result["output"][:500].encode("ascii", errors="replace").decode()
    print(f"  output ({len(result['output'])} chars):")
    print("  " + safe.replace("\n", "\n  "))
    print(f"\n  execution_time: {result['execution_time']:.1f}s")
    print(f"  cost_usd: ${result['cost_usd']:.6f}")

    files = result.get("output_files", {})
    if files:
        print(f"\n  output_files ({len(files)}):")
        for name, content in files.items():
            print(f"    [{name}] {len(content)} chars — {content[:80].strip()!r}")
    else:
        print("\n  output_files: (none)")

    assert result["output"], "Expected non-empty output"
    print("\nPhase 4 PASSED — skill runner works.")

if __name__ == "__main__":
    main()
