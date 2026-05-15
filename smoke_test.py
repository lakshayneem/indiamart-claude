"""
Phase 0 smoke test — connect to local Daytona, create sandbox, exec a command, delete.
Run: .venv/Scripts/python smoke_test.py
"""
import os, sys
from dotenv import load_dotenv

load_dotenv()

required = ["DAYTONA_API_KEY", "DAYTONA_API_URL"]
missing = [k for k in required if not os.environ.get(k)]
if missing:
    print(f"ERROR: missing env vars: {missing}")
    print("Copy .env.example to .env and fill in the values.")
    sys.exit(1)

from daytona import Daytona, DaytonaConfig

def main():
    config = DaytonaConfig(
        api_key=os.environ["DAYTONA_API_KEY"],
        api_url=os.environ["DAYTONA_API_URL"],
    )
    daytona = Daytona(config)

    print("Creating sandbox...")
    sandbox = daytona.create()
    print(f"  sandbox id: {sandbox.id}")

    print("Running: echo hello")
    result = sandbox.process.exec("echo hello")
    print(f"  result: {result.result!r}")
    assert "hello" in result.result, f"unexpected: {result.result!r}"

    print("Running: node --version")
    result = sandbox.process.exec("node --version")
    print(f"  node: {result.result.strip()}")

    print("Deleting sandbox...")
    sandbox.delete()
    print("Done. Phase 0 PASSED.")

if __name__ == "__main__":
    main()
