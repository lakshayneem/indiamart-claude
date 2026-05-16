"""
Phase 4 test — stateless skill runner.

Runs the srs-creator skill against a real GitLab repo + OpenProject ticket;
checks that the output contains srs.md and srs.docx and that the run did not
trip the empty-content gateway 400.

Requires GITLAB_TOKEN, OPENPROJECT_TOKEN in .env (host-side fetch).

Run: .venv/Scripts/python test_skill_runner.py
"""
import os, sys
from dotenv import load_dotenv

load_dotenv()

required = [
    "DAYTONA_API_KEY", "DAYTONA_API_URL",
    "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN",
    "GITLAB_TOKEN", "OPENPROJECT_TOKEN",
]
missing = [k for k in required if not os.environ.get(k)]
if missing:
    print(f"ERROR: missing env vars: {missing}")
    sys.exit(1)

from backend.skill_runner import run_skill

def main():
    print("=== Phase 4: Skill Runner Test (srs-creator) ===\n")

    repo_url = os.environ.get("GITLAB_URL") or "https://scm.intermesh.net/indiamart/soa/service-api-go"
    inputs = {
        "repo_url": repo_url,
        "api_name": "/banned_city_mcat",
        "business_requirement": "Smoke test of the SRS pipeline.",
        "ticket_id": "650234",
    }

    print(f"Running skill: srs-creator")
    print(f"  repo_url    : {inputs['repo_url']}")
    print(f"  api_name    : {inputs['api_name']}")
    print(f"  ticket_id   : {inputs['ticket_id']}\n")

    result = run_skill("srs-creator", inputs)

    safe = result["output"][:500].encode("ascii", errors="replace").decode()
    print(f"  output ({len(result['output'])} chars):")
    print("  " + safe.replace("\n", "\n  "))
    print(f"\n  execution_time: {result['execution_time']:.1f}s")
    print(f"  cost_usd: ${result['cost_usd']:.6f}")

    files = result.get("output_files", {})
    if files:
        print(f"\n  output_files ({len(files)}):")
        for name, content in files.items():
            preview = content[:80].strip().encode("ascii", errors="replace").decode()
            print(f"    [{name}] {len(content)} chars - {preview!r}")
    else:
        print("\n  output_files: (none)")

    binary_files = result.get("output_files_binary", {})
    if binary_files:
        print(f"\n  output_files_binary ({len(binary_files)}):")
        for name, b64 in binary_files.items():
            print(f"    [{name}] {len(b64)} base64 chars")
    else:
        print("\n  output_files_binary: (none)")

    # SRS-specific checks
    assert result["output"], "Expected non-empty output"
    assert "srs.md" in files, "Expected srs.md in output_files"
    assert "srs.docx" in binary_files, "Expected srs.docx in output_files_binary"
    print("\nPhase 4 PASSED — srs-creator produced srs.md + srs.docx.")

if __name__ == "__main__":
    main()
