# Daytona Snapshot Guide — IM Agentic OS

A snapshot is a pre-built Docker image registered with Daytona. Every skill run starts a fresh sandbox from the snapshot — no install time, no drift between runs. This guide walks you from a blank machine to a working snapshot that the platform's `skill_runner.py` can use.

---

## Prerequisites

| Tool | Version | Check |
|---|---|---|
| Docker Desktop | 24+ | `docker --version` |
| Daytona CLI | latest | `daytona version` |
| Self-hosted Daytona | running at `http://localhost:3000` | `curl http://localhost:3000/health` |
| `DAYTONA_API_KEY` | from dashboard | Settings → API Keys |

If Docker Desktop is not running, start it before continuing.

---

## What goes into the snapshot

The snapshot bakes in everything that is **slow to install or constant across all skill runs**. Things that change per-run are injected at runtime instead.

| Baked in (snapshot) | Injected at runtime |
|---|---|
| Node.js 20 runtime | `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_BASE_URL` |
| Claude Code CLI (pinned version) | `CLAUDE.md` — global agent instructions |
| Org-wide tool permissions (`managed-settings.json`) | `SKILL.md` — per-skill task instructions |
| Default model + auto-compact settings | User-uploaded input files |
| Python 3 + pandas, matplotlib, openpyxl, requests | |
| Directory structure (`workspace/`, `output/`, `.claude/`) | |

**Never bake in API keys or skill content.** Keys are a security risk; skills change often and belong in the skill registry.

---

## Step 1 — Review the snapshot files

All four files live in `snapshot/`:

```
snapshot/
├── Dockerfile            ← image definition
├── managed-settings.json ← org-wide Claude Code permissions (highest precedence)
├── claude-settings.json  ← default model and auto-compact
└── CLAUDE.md             ← global agent instructions injected at sandbox start
```

### `Dockerfile`

```dockerfile
FROM node:20-bookworm-slim
ARG CLAUDE_VERSION=2.1.94

ENV DEBIAN_FRONTEND=noninteractive
ENV DISABLE_AUTOUPDATER=1

RUN apt-get update && apt-get install -y \
    curl git python3 python3-pip jq unzip \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash daytona

RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_VERSION}

RUN mkdir -p /etc/claude-code
COPY managed-settings.json /etc/claude-code/managed-settings.json

RUN mkdir -p /home/daytona/.claude
COPY claude-settings.json /home/daytona/.claude/settings.json

RUN mkdir -p /home/daytona/skills \
             /home/daytona/output \
             /home/daytona/workspace \
             /home/daytona/.claude/projects

RUN pip3 install pandas matplotlib requests openpyxl --break-system-packages

COPY CLAUDE.md /home/daytona/CLAUDE.md

RUN chown -R daytona:daytona /home/daytona

USER daytona
WORKDIR /home/daytona
```

### `managed-settings.json`

Controls which Claude Code tools are allowed. Stored at `/etc/claude-code/managed-settings.json` — this is the **highest-precedence** settings file; it cannot be overridden by the agent or by user settings.

```json
{
  "permissions": {
    "allow": ["Bash", "Read", "Write", "Edit", "Glob", "Grep"],
    "deny": []
  },
  "autoUpdaterStatus": "disabled",
  "env": {
    "DISABLE_AUTOUPDATER": "1"
  }
}
```

To lock down further (e.g. no Bash), move `"Bash"` to `"deny"`. To add tools like `WebFetch`, add to `"allow"`.

### `claude-settings.json`

Sets defaults for the Claude Code session. Stored at `/home/daytona/.claude/settings.json`.

```json
{
  "model": "anthropic/claude-sonnet-4-6",
  "autoCompact": true
}
```

`autoCompact: true` means Claude Code silently compresses its context at ~95% usage — long-running skills stay within the context window without any handling on your side.

---

## Step 2 — Build the Docker image

**Important: Daytona requires AMD64. Always build for that platform even on Apple Silicon or ARM.**

```bash
cd snapshot/

docker buildx build \
  --platform linux/amd64 \
  -t company-claude:1.0.0 \
  --load \
  .
```

`--load` writes the image to your local Docker daemon (needed for the next step). This takes 2–5 minutes on first build; subsequent builds use the layer cache.

To pin a different Claude Code version:

```bash
docker buildx build \
  --platform linux/amd64 \
  --build-arg CLAUDE_VERSION=2.2.0 \
  -t company-claude:2.0.0 \
  --load \
  .
```

Check the latest version at: https://www.npmjs.com/package/@anthropic-ai/claude-code

---

## Step 3 — Register the snapshot with Daytona

Daytona needs to know about the image before sandboxes can be created from it.

### Option A — Push image to Daytona directly

```bash
daytona snapshot create \
  --name company-claude-v1 \
  --image company-claude:1.0.0 \
  --cpu 2 \
  --memory 4096 \
  --disk 8192
```

### Option B — Let Daytona build from Dockerfile

If your Daytona server has Docker access:

```bash
daytona snapshot create \
  --name company-claude-v1 \
  --dockerfile ./Dockerfile \
  --context . \
  --cpu 2 \
  --memory 4096 \
  --disk 8192
```

### Verify

```bash
daytona snapshot list
```

You should see `company-claude-v1` with status `ready`.

---

## Step 4 — Smoke test

Verify the snapshot creates a working sandbox and that Claude Code can run inside it.

```python
# smoke_test.py
import os
from daytona import Daytona, DaytonaConfig, CreateSandboxFromSnapshotParams

daytona = Daytona(DaytonaConfig(
    api_key=os.environ["DAYTONA_API_KEY"],
    api_url=os.environ.get("DAYTONA_API_URL", "http://localhost:3000"),
))

sandbox = daytona.create(CreateSandboxFromSnapshotParams(
    snapshot="company-claude-v1",
    env_vars={
        "ANTHROPIC_BASE_URL": os.environ["ANTHROPIC_BASE_URL"],
        "ANTHROPIC_AUTH_TOKEN": os.environ["ANTHROPIC_AUTH_TOKEN"],
    },
    auto_stop_interval=10,
))

try:
    # Check Claude Code is installed
    result = sandbox.process.exec("claude --version")
    print("Claude Code version:", result.result.strip())

    # Check directories exist
    result = sandbox.process.exec("ls /home/daytona/")
    print("Home directories:", result.result.strip())

    # Run a minimal skill
    result = sandbox.process.exec(
        "claude -p 'Write hello world to output/hello.txt' "
        "--output-format stream-json "
        "--dangerously-skip-permissions"
    )
    print("Run output (last 200 chars):", result.result[-200:])

    # Check the file was created
    result = sandbox.process.exec("cat /home/daytona/output/hello.txt")
    print("Output file contents:", result.result.strip())

finally:
    sandbox.delete()
    print("Sandbox deleted.")
```

Run it:

```bash
python smoke_test.py
```

Expected output:
```
Claude Code version: 2.1.94
Home directories: CLAUDE.md  output  skills  workspace  .claude
Run output (last 200 chars): ...{"type":"result","subtype":"success",...}
Output file contents: Hello, World!
Sandbox deleted.
```

---

## Step 5 — Wire it to the platform

In `backend/skill_runner.py`, the snapshot name is controlled by the `SNAPSHOT_NAME` env var (defaults to `company-claude-v1`):

```python
SNAPSHOT = os.environ.get("SNAPSHOT_NAME", "company-claude-v1")
```

Add to your `.env`:

```env
SNAPSHOT_NAME=company-claude-v1
```

That's it. Every `POST /run-skill` call now spins a sandbox from this snapshot.

---

## Updating the snapshot

When you need to add new tools, update Claude Code, or change permissions:

1. Edit `Dockerfile` or `managed-settings.json`
2. Rebuild with a new tag:
   ```bash
   docker buildx build --platform linux/amd64 -t company-claude:1.1.0 --load .
   ```
3. Register as a new snapshot:
   ```bash
   daytona snapshot create --name company-claude-v2 --image company-claude:1.1.0 \
     --cpu 2 --memory 4096 --disk 8192
   ```
4. Update `SNAPSHOT_NAME=company-claude-v2` in `.env` and restart the backend
5. Once validated, delete the old snapshot:
   ```bash
   daytona snapshot delete company-claude-v1
   ```

Keep at least one previous snapshot registered during rollout. If something breaks, revert `SNAPSHOT_NAME` and restart — no code changes needed.

---

## Adding more tools / runtimes to the snapshot

Edit the `Dockerfile` `RUN` section before `pip3 install`:

```dockerfile
# Java (for skills that analyse JVM projects)
RUN apt-get update && apt-get install -y default-jdk && rm -rf /var/lib/apt/lists/*

# Node packages available to the agent
RUN npm install -g typescript ts-node

# More Python packages
RUN pip3 install scipy scikit-learn boto3 --break-system-packages
```

Adding tools here means zero install time per skill run. Only add what multiple skills actually need — per-skill dependencies can be installed at run time via `Bash` in the SKILL.md steps.

---

## Allowing additional Claude Code tools

To allow `WebFetch` (for skills that need to call external APIs):

```json
{
  "permissions": {
    "allow": ["Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebFetch"],
    "deny": []
  }
}
```

To block `Bash` entirely (read-only analysis skills):

```json
{
  "permissions": {
    "allow": ["Read", "Glob", "Grep"],
    "deny": ["Bash", "Write", "Edit"]
  }
}
```

Changes to `managed-settings.json` require a snapshot rebuild.

---

## Snapshot versioning convention

```
company-claude-v1    ← production (current)
company-claude-v2    ← staged / canary
```

Update `SNAPSHOT_NAME` in `.env` to switch versions with no code deploy. Test with a single skill before switching all traffic.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `snapshot not found` error | Snapshot not registered or wrong name | `daytona snapshot list` and check `SNAPSHOT_NAME` in `.env` |
| `claude: command not found` inside sandbox | Wrong platform (ARM image on AMD64 host) | Rebuild with `--platform linux/amd64` |
| `ANTHROPIC_AUTH_TOKEN not set` inside sandbox | env_vars not passed at sandbox creation | Check `skill_runner.py` `CreateSandboxFromSnapshotParams` |
| Skill outputs nothing | `managed-settings.json` blocking `Write` | Check `"allow"` list includes `"Write"` and `"Bash"` |
| Claude Code auto-updates and breaks | `DISABLE_AUTOUPDATER` not set | Confirm it is in both `ENV` in Dockerfile and `managed-settings.json` |
| Sandbox keeps running after skill finishes | `auto_stop_interval` not set | Set `auto_stop_interval=30` in `CreateSandboxFromSnapshotParams` |
