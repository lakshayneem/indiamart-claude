"""Runs a skill via the sandbox client and returns a structured result."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from components.sandbox_client import run_skill

def run_skill_analysis(skill_id: str, inputs: dict) -> dict:
    if not skill_id:
        return {"status": "error", "error": "skill_id is required"}
    if not inputs:
        return {"status": "error", "error": "inputs cannot be empty"}

    missing = [k for k, v in inputs.items() if not v and v != 0]
    if missing:
        return {"status": "error", "error": f"Missing required inputs: {', '.join(missing)}"}

    result = run_skill(skill_id, inputs)
    return result

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python analyze.py <skill_id> '<inputs_json>'")
        sys.exit(1)
    skill_id = sys.argv[1]
    inputs = json.loads(sys.argv[2])
    result = run_skill_analysis(skill_id, inputs)
    print(json.dumps({"status": result.get("status"), "preview": result.get("output", "")[:200]}, indent=2))
