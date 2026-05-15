# Running IM Agentic OS

The platform is two processes:

| Process | Port | Command location |
|---|---|---|
| Backend (FastAPI) | `8000` | repo root |
| Frontend (Streamlit) | `8501` | `im-agentic-os/` |

Open the app at **http://localhost:8501** once both are running. Demo creds:

| Role | Username | Password |
|---|---|---|
| Employee | `im_user` | `User@1234` |
| Creator | `im_creator` | `Creator@1234` |
| Admin | `im_admin` | `Admin@1234` |

---

## Quick start — one command (PowerShell)

From the repo root:

```powershell
./run-dev.ps1
```

This opens a new PowerShell window for the backend (uvicorn, with reload) and runs Streamlit in the current window. Ctrl+C in either window to stop that process.

---

## Manual start — two terminals

If you prefer to see both logs side-by-side, open two terminals.

### Terminal 1 — backend

```powershell
cd C:\Users\IndiaMart\Downloads\indiamart-claude
.venv\Scripts\Activate.ps1
uvicorn backend.api:app --port 8000 --reload
```

Verify: `curl http://localhost:8000/health` → `{"status":"ok"}`

### Terminal 2 — frontend

```powershell
cd C:\Users\IndiaMart\Downloads\indiamart-claude\im-agentic-os
..\.venv\Scripts\Activate.ps1
streamlit run app.py
```

Streamlit will print the URL (default `http://localhost:8501`) and open it in your browser.

---

## First-time setup

If the venv is fresh, install dependencies first:

```powershell
cd C:\Users\IndiaMart\Downloads\indiamart-claude
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt              # backend deps (fastapi, uvicorn, daytona-sdk, pyyaml)
pip install -r im-agentic-os\requirements.txt  # frontend deps (streamlit, pandas, openpyxl, requests)
```

A `.env` at the repo root must define:

```env
DAYTONA_API_URL=http://localhost:3000/api
DAYTONA_API_KEY=<from local Daytona dashboard>
ANTHROPIC_BASE_URL=<your gateway>
ANTHROPIC_AUTH_TOKEN=<your token>
CLAUDE_MODEL=anthropic/claude-sonnet-4
```

---

## Stopping the servers

In the terminal running each process: `Ctrl + C`.

To force-kill anything stuck on the two ports:

```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { Stop-Process -Id $_ -Force }

Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { Stop-Process -Id $_ -Force }
```

---

## Useful URLs

| What | URL |
|---|---|
| Frontend (Streamlit) | http://localhost:8501 |
| Backend health | http://localhost:8000/health |
| Backend API docs (Swagger) | http://localhost:8000/docs |
| Backend skills list | http://localhost:8000/skills |
