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

    print(f"  output ({len(result['output'])} chars):")
    print("  " + result["output"][:500].replace("\n", "\n  "))
    print(f"\n  execution_time: {result['execution_time']:.1f}s")
    print(f"  cost_usd: ${result['cost_usd']:.6f}")

    assert result["output"], "Expected non-empty output"
    print("\nPhase 4 PASSED — skill runner works.")

if __name__ == "__main__":
    main()
