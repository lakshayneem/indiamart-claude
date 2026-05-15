# IM Agentic OS — App Details & Sandbox Integration Guide

## 1. Overview

IM Agentic OS is a multi-role internal platform for IndiaMART that bridges the gap
between technical skill creators and non-technical business users. Skills are published
through a governed approval workflow and executed by any IM employee via a Streamlit
dashboard — no terminal required.

**Entry point:** `app.py`
**Run command:** `streamlit run app.py` (from inside the `im-agentic-os/` directory)

---

## 2. Application Architecture

```
im-agentic-os/
├── app.py                          # Login page + role-based routing
├── pages/
│   ├── 1_user_dashboard.py         # Employee view (browse, run, favourite, request)
│   ├── 2_skill_creator.py          # Creator view (submit, manage, analytics)
│   └── 3_admin.py                  # Admin view (approvals, users, analytics, config)
├── components/
│   ├── auth.py                     # Login, session, role guard, user CRUD
│   ├── sandbox_client.py           # Sandbox API call + mock fallback
│   ├── quota_checker.py            # Per-user / per-skill daily rate limits
│   ├── hours_counter.py            # Hours-saved metric computation
│   ├── announcement_banner.py      # Audience-targeted announcements
│   ├── output_renderer.py          # Formatted markdown output panel
│   └── design_system.py            # Shared CSS, topnav, badges, cards, helpers
├── scripts/
│   ├── fetch_data.py               # Skill registry queries (standalone + importable)
│   ├── analyze.py                  # Wraps sandbox_client for CLI usage
│   └── render_report.py            # Appends metadata footer to skill output
├── data/                           # JSON flat-file store (no DB required)
│   ├── users.json
│   ├── skills_registry.json        # Approved skills
│   ├── pending_skills.json         # Pending / rejected skills
│   ├── adoptions.json              # Skill run log
│   ├── feedback.json               # User ratings + comments
│   ├── favourites.json             # Per-user favourited skill IDs
│   ├── skill_requests.json         # Employee skill requests + upvotes
│   ├── audit_log.json              # Append-only admin action log
│   └── announcements.json          # Platform announcements
├── assets/
│   ├── config.xlsx                 # Teams, Categories, RateLimits, FileTypes sheets
│   ├── report-template.md          # Output footer template
│   └── credentials.json            # (Unused placeholder)
├── references/
│   ├── domain-rules.md
│   ├── output-schema.md
│   └── second-workflow-walkthrough.md
├── SKILL.md                        # Hackathon submission document
├── requirements.txt
└── .venv/                          # Python virtual environment
```

---

## 3. Roles & Access

| Role | Username | Password | Access |
|------|----------|----------|--------|
| Employee | `im_user` | `User@1234` | User Dashboard (browse, run, favourite, request skills) |
| Skill Creator | `im_creator` | `Creator@1234` | Creator Portal (submit, manage, test, analytics) |
| Admin | `im_admin` | `Admin@1234` | Admin Panel (approvals, users, rate limits, audit log, announcements) |

Passwords are stored as SHA-256 hashes in `data/users.json`.
Authentication is session-based (Streamlit `st.session_state`).
`require_role()` in `components/auth.py` guards each page — unauthenticated or
wrong-role access triggers `st.stop()`.

---

## 4. Page-by-Page Flow

### 4.1 `app.py` — Login

- Two-column layout: left brand panel, right login form
- On submit: `components/auth.py → login()` hashes password and matches against `data/users.json`
- Success: sets `st.session_state` keys (`username`, `name`, `role`, `team`) and calls `st.rerun()`
- Post-rerun routing: `st.switch_page()` to the role-appropriate page
- Handles disabled accounts (returns `{"error": "disabled"}`) — does not reveal whether username exists

### 4.2 `pages/1_user_dashboard.py` — Employee View

Three sections switchable via sidebar pills:

**Browse Skills**
- Filter bar: Team, Category, Search, Sort (Default / Most used / Newest / Top rated)
- Data: `scripts/fetch_data.py → fetch_all_skills()` reads `data/skills_registry.json`, filters by `status == "approved"`
- Teams/Categories loaded from `assets/config.xlsx` (Teams / Categories sheets)
- Featured skills row shown first (max 3, `is_featured == true`)
- All skills grid: 3 columns, `render_skill_card()` per skill
- Skill card shows: name, team/category/featured/new badges, description, est. time, rating, run count, Run button, Favourite toggle
- "New" badge: `approved_at >= first day of current month`

**Skill Execution (dialog)**
- Triggered by "Run skill" button → sets `st.session_state["active_skill"]` → `st.rerun()` → `@st.dialog` opens
- Quota check runs first via `components/quota_checker.py → can_run()` — blocks with message if limit exceeded
- Input form rendered dynamically from `skill["input_fields"]` (supports: text, textarea, number, dropdown, date, file_upload)
- On submit: calls `components/sandbox_client.py → run_skill(skill_id, inputs)`
- Result logged to `data/adoptions.json` regardless of status
- Success: renders formatted output via `components/output_renderer.py`, shows download button
- After output: inline feedback form (1–5 stars + comment) → saved to `data/feedback.json`

**My Favourites**
- Reads `data/favourites.json[username]` — dict keyed by username, value is list of skill_ids
- Same `render_skill_card()` as Browse view

**Skill Requests**
- View, upvote, and submit skill requests stored in `data/skill_requests.json`
- Max 3 open requests per user at a time
- Upvote disabled for own requests and already-voted requests
- Sort: Most upvoted / Newest / Mine

**Sidebar**
- Shows quota badge: `X / Y runs today` in green/orange/red
- Sign out button → `logout()` + `st.switch_page("app.py")`
- Announcements rendered at top of page (audience-filtered)

### 4.3 `pages/2_skill_creator.py` — Creator Portal

Four tabs:

**Submit Skill (4-step wizard)**

| Step | Content |
|------|---------|
| 1 — Source | ZIP upload (validated for SKILL.md + scripts/*.py) or Git Repo URL |
| 2 — Metadata | Name (60 chars, alphanumeric/hyphens/spaces), Description (must start with "Use this skill when"), Team, Category, Tags (max 5). Duplicate name check against both `pending_skills.json` and `skills_registry.json` |
| 3 — Input Fields | Dynamic field builder: label, key (auto-derived), type, required, placeholder. Types: text / textarea / number / dropdown / file_upload / date. Dropdown fields require at least 1 option. Live preview toggle shows card + input form as users will see it |
| 4 — Projection & Submit | X (mins/occurrence) × Y (occurrences/day) × N (adopters) × 22 days → hours/month. Projected impact shown live. On submit: written to `data/pending_skills.json` with `status: "pending"` |

**My Skills**
- Lists all skills created by this user (approved + pending from both JSON files)
- Status badges: Approved (green) / Pending (yellow) / Rejected (red)
- Approved: Test button (inline test form, not counted in adoption stats) + Edit button
- Rejected: Resubmit button + rejection reason shown

**Feedback & Ratings**
- Select skill dropdown (approved skills only)
- Avg rating, total ratings, rating distribution bar chart
- Individual feedback cards: initials, star rating, comment, days ago

**Adoption Analytics**
- Metrics: total runs, unique users, hours saved (current month)
- Bar chart: runs per day (from `data/adoptions.json`, `format="ISO8601"` for timestamp parsing)

### 4.4 `pages/3_admin.py` — Admin Panel

Seven sections in sidebar nav:

| Section | What it does |
|---------|-------------|
| Dashboard | Platform-wide metrics (active skills, pending, total users, runs today, hours saved) + last 10 audit log entries |
| Skill Approvals | Filter/search pending skills. Per-skill: view metadata, input fields, projected impact. Approve or reject (reason ≥ 20 chars). Bulk select + bulk approve/reject. Approved skills move from `pending_skills.json` to `skills_registry.json` |
| User Management | List all users. Add new user (generates temp password). Edit role, toggle enabled. Self-modification disabled (cannot lock yourself out) |
| Rate Limits | Read from `assets/config.xlsx → RateLimits`. Edit per role: max_runs_per_day + max_runs_per_skill_per_day. Saves back to xlsx via openpyxl |
| Analytics | All-time + monthly: hours saved, total runs, unique users. Skill-wise stats table (runs, users, avg rating, hrs saved). User-wise stats table. Both downloadable as CSV |
| Audit Log | Paginated (25/page), filterable by action type, searchable by actor/details. All admin actions are logged here. CSV download |
| Announcements | Post announcements with title, message, audience (all / creators / team), type (info/success/warning/critical), optional expiry. Toggle active/inactive. Delete with confirmation |

---

## 5. Data Layer

All state is stored in JSON flat files under `data/`. No database required.

### `data/users.json`
```json
{
  "username": "im_user",
  "password_hash": "<sha256>",
  "role": "user | creator | admin",
  "name": "Full Name",
  "team": "Team Name",
  "enabled": true,
  "created_at": "2026-05-01T09:00:00",
  "last_login": "2026-05-15T08:45:00"
}
```

### `data/skills_registry.json` (approved skills)
```json
{
  "skill_id": "srs-creator",
  "name": "SRS Creator",
  "description": "Use this skill when...",
  "team": "Product Team",
  "category": "SRS & Docs",
  "tags": ["srs", "documentation"],
  "creator_id": "im_creator",
  "status": "approved",
  "version": 1,
  "is_featured": true,
  "source_type": "zip | repo",
  "source_ref": "<filename or URL>",
  "input_fields": [
    {
      "key": "repo_url",
      "label": "GitHub Repo URL",
      "type": "text | textarea | number | dropdown | file_upload | date",
      "required": true,
      "placeholder": "...",
      "options": [],
      "allowed_file_types": [],
      "max_file_size": "10MB"
    }
  ],
  "adoption_projection": {
    "x_mins": 4,
    "y_occurrences_per_day": 3,
    "n_adopters": 200,
    "hours_saved_per_month": 40
  },
  "created_at": "2026-05-08T10:00:00",
  "approved_at": "2026-05-09T14:30:00",
  "rejection_reason": null
}
```

### `data/adoptions.json` (run log)
```json
{
  "run_id": "ab12cd34",
  "skill_id": "srs-creator",
  "username": "im_user",
  "status": "success | error",
  "execution_time": 12.4,
  "ran_at": "2026-05-15T14:32:11.827782"
}
```

**Note:** `ran_at` uses `datetime.now().isoformat()` which includes microseconds.
Any `pd.to_datetime()` call on this field must use `format="ISO8601"`.

### `data/feedback.json`
```json
{
  "feedback_id": "fbabcd12",
  "skill_id": "srs-creator",
  "username": "im_user",
  "rating": 5,
  "comment": "Saved me 4 hours.",
  "created_at": "2026-05-15T14:35:00.123456"
}
```

### `data/favourites.json`
```json
{
  "im_user": ["srs-creator", "test-case-generator"],
  "im_creator": []
}
```

### `data/skill_requests.json`
```json
{
  "request_id": "reqabcd12",
  "requested_by": "im_user",
  "title": "Email Draft Generator",
  "description": "Automate email drafting for buyer follow-ups...",
  "team": "Seller Success",
  "category": "...",
  "estimated_adopters": 30,
  "priority": "High",
  "status": "open | in_progress | fulfilled",
  "assigned_to": null,
  "linked_skill_id": null,
  "upvotes": ["im_user2", "im_user3"],
  "created_at": "2026-05-15T10:00:00.000000"
}
```

### `data/audit_log.json`
```json
{
  "log_id": "logabcd12",
  "actor": "im_admin",
  "action": "skill_approved | skill_rejected | skill_submitted | role_changed | user_disabled | user_enabled | user_created | announcement_posted | announcement_deleted | rate_limit_changed",
  "target": "srs-creator",
  "details": "Approved skill: SRS Creator",
  "created_at": "2026-05-15T14:00:00.000000"
}
```

### `data/announcements.json`
```json
{
  "announcement_id": "annabcd12",
  "title": "New skill available",
  "message": "The SRS Creator skill is now live.",
  "audience": "all | creators | team",
  "team": "Product Team",
  "type": "info | success | warning | critical",
  "created_by": "im_admin",
  "created_at": "2026-05-15T09:00:00.000000",
  "expires_at": "2026-05-20",
  "is_active": true
}
```

### `assets/config.xlsx` — Sheets

| Sheet | Columns | Purpose |
|-------|---------|---------|
| Teams | `team_id`, `team_name`, `is_active` | Team filter options |
| Categories | `category_id`, `category_name`, `team_id`, `is_active` | Category filter options, linked to team |
| RateLimits | `role`, `max_runs_per_day`, `max_runs_per_skill_per_day` | Quota limits per role |
| FileTypes | `extension`, `is_active` | Allowed file upload extensions |

---

## 6. Components Reference

### `components/auth.py`
| Function | Signature | Description |
|----------|-----------|-------------|
| `login` | `(username, password) → dict \| None` | Returns user dict, `{"error": "disabled"}`, or `None` |
| `logout` | `() → None` | Clears session state keys |
| `is_authenticated` | `() → bool` | Checks `"username" in st.session_state` |
| `get_current_user` | `() → dict` | Returns `{username, name, role, team}` from session |
| `require_role` | `(allowed_roles: list) → bool` | Calls `st.stop()` if unauthenticated or wrong role |
| `get_all_users` | `() → list` | Reads `data/users.json` |
| `update_user` | `(username, updates: dict) → None` | Patches user record in place |
| `add_user` | `(user: dict) → None` | Appends new user to `data/users.json` |

### `components/sandbox_client.py`
| Function | Signature | Description |
|----------|-----------|-------------|
| `check_sandbox_health` | `() → bool` | GET `/health` on sandbox URL, returns `True` if reachable |
| `run_skill` | `(skill_id, inputs: dict) → dict` | POST `/run-skill`, falls back to `_mock_response` on any exception |
| `_mock_response` | `(skill_id, inputs) → dict` | Returns hardcoded mock for `srs-creator` and `test-case-generator`; generic output for all others |

**Response format:**
```json
{
  "status": "success | error",
  "skill_id": "srs-creator",
  "output": "# Markdown output string...",
  "execution_time_seconds": 12.4,
  "source": "live | mock",
  "error": "Optional error message"
}
```

### `components/quota_checker.py`
| Function | Signature | Description |
|----------|-----------|-------------|
| `compute_quota` | `(username, role, skill_id=None) → dict` | Returns full quota state for a user |
| `can_run` | `(username, role, skill_id) → (bool, str)` | Returns `(True, "")` or `(False, reason_message)` |

**Quota dict fields:** `total_today`, `max_day`, `remaining_day`, `skill_today`, `max_skill`, `remaining_skill`, `is_blocked_day`, `is_blocked_skill`

### `components/hours_counter.py`
| Function | Signature | Description |
|----------|-----------|-------------|
| `compute_hours_saved` | `(scope, creator_id=None, period="month") → dict` | Aggregates hours saved from adoptions × `x_mins` per skill |
| `format_hours` | `(h: float) → str` | Formats `1500 → "1.5K"`, `40 → "40"`, `40.5 → "40.5"` |

Period options: `"month"` (current calendar month), `"today"`, `"all"`.

### `components/announcement_banner.py`
Functions: `get_active_announcements(role, team)`, `render_banners(announcements)`,
`post_announcement(data)`, `update_announcement(id, updates)`, `delete_announcement(id)`.

Filtering: active announcements where `is_active == true`, `expires_at` is null or in the future,
and audience matches the current user's role/team.

### `components/output_renderer.py`
Functions: `render_output(output, exec_time, skill_name, source)`, `render_error(message)`.
Renders skill output in a styled markdown panel with a metadata header line.

### `components/design_system.py`
Global CSS injection and reusable UI building blocks:
`inject_css()`, `topnav(name, role)`, `hero_banner(title, subtitle, kpi_value, kpi_label)`,
`badge(text, variant)`, `section_heading(title, icon)`, `empty_state(icon, title, subtitle)`,
`loading_animation()`, `stars(rating)`, `metric_card(value, label)`.

---

## 7. Scripts Reference

### `scripts/fetch_data.py`
| Function | Signature | Description |
|----------|-----------|-------------|
| `fetch_all_skills` | `(team, category, search) → list` | Filters `skills_registry.json` by `status == "approved"` + optional filters |
| `fetch_skill` | `(skill_id) → dict \| None` | Returns single approved skill by ID |
| `fetch_creator_skills` | `(creator_id, include_pending=True) → list` | Returns all skills (approved + optionally pending) for a creator |

**CLI usage:** `python scripts/fetch_data.py [skill_id]`

### `scripts/analyze.py`
Wraps `sandbox_client.run_skill()` with input validation.
**CLI usage:** `python scripts/analyze.py <skill_id> '<inputs_json>'`
Example: `python scripts/analyze.py srs-creator '{"repo_url":"https://github.com/x/y","api_name":"Search","business_requirement":"Improve search"}'`

### `scripts/render_report.py`
Appends a metadata footer to raw skill output. Used by the output renderer.
**CLI usage:** `python scripts/render_report.py <skill_id> <output_text>`

---

## 8. Rate Limiting

Limits are defined per role in `assets/config.xlsx → RateLimits`:

| Role | Default max/day | Default max/skill/day |
|------|-----------------|-----------------------|
| user | 20 | 5 |
| creator | 50 | 10 |
| admin | 999 (unlimited) | 999 (unlimited) |

Quota is computed at runtime by counting `data/adoptions.json` entries where
`username == current_user` and `ran_at[:10] == today`. Resets automatically at midnight —
no cron or reset action required.

The Run button is **disabled before the API call** if the quota is exceeded.
No sandbox calls are wasted on rate-limited users.

---

## 9. Sandbox Integration

### 9.1 What the Sandbox Is

The sandbox is an external HTTP service that receives a skill ID and input values,
executes the corresponding Claude Code skill, and returns structured output.
The platform treats it as a black box — it only calls two endpoints.

The sandbox URL defaults to `http://localhost:8000` (set in `components/sandbox_client.py`).

### 9.2 Sandbox Endpoints Required

#### `GET /health`
Used by `check_sandbox_health()` to verify connectivity.

**Request:** No body, no auth headers required.

**Expected response:**
```json
{"status": "ok"}
```
Any HTTP 2xx response is treated as healthy. Connection error or timeout → sandbox considered down.

---

#### `POST /run-skill`
Main execution endpoint. Called by `run_skill(skill_id, inputs)`.

**Request headers:**
```
Content-Type: application/json
```

**Request body:**
```json
{
  "skill_id": "srs-creator",
  "inputs": {
    "repo_url": "https://github.com/indiamart/product-search",
    "api_name": "Product Search API",
    "business_requirement": "Reduce zero-result rate from 18% to under 5%."
  }
}
```

- `skill_id` (string, required): matches the `skill_id` field in `skills_registry.json`
- `inputs` (object, required): key-value pairs matching the skill's `input_fields[].key` definitions
- Input values are always strings (text/textarea/date/dropdown) or numbers (number type)
- File upload fields pass only the filename string — actual file bytes are not forwarded in the current implementation

**Success response (HTTP 200):**
```json
{
  "status": "success",
  "skill_id": "srs-creator",
  "output": "# Software Requirements Specification\n\n...(markdown string)...",
  "execution_time_seconds": 12.4,
  "source": "live"
}
```

**Error response (HTTP 200 with error status, or HTTP 4xx/5xx):**
```json
{
  "status": "error",
  "skill_id": "srs-creator",
  "output": "",
  "error": "Human-readable error message shown to the user",
  "execution_time_seconds": 0
}
```

**Notes:**
- The platform calls `response.raise_for_status()` — any HTTP 4xx/5xx triggers the mock fallback
- Any `requests.exceptions.ConnectionError` or timeout also triggers mock fallback
- Timeout is set to 30 seconds (`requests.post(..., timeout=30)`)
- The `source` field ("live" vs "mock") is displayed in the output panel header

### 9.3 Mock Fallback Behaviour

When the sandbox is unreachable (any exception in `run_skill()`), the platform
automatically calls `_mock_response()` with no visible error to the user.

Mock responses are defined for:
- `srs-creator` → returns a full SRS document (hardcoded in `sandbox_client.py`)
- `test-case-generator` → returns 16 structured test cases
- Any other `skill_id` → returns a generic "inputs received" summary

Mock execution simulates a delay: `time.sleep(min(exec_time / 10, 2))` where
`exec_time` is a random float between 8.5 and 17.5 seconds.

The output panel shows `source: "mock"` so demo viewers can see fallback is active.

### 9.4 Connecting a Live Sandbox

To connect the live sandbox, update the `SANDBOX_URL` constant in
`components/sandbox_client.py`:

```python
# components/sandbox_client.py
SANDBOX_URL = "https://your-sandbox-host.example.com"   # change this line
```

No other code changes are needed. The platform will automatically use the live
sandbox for all new runs and fall back to mock only on connection failure.

**Optional: Add authentication headers**

If the sandbox requires an API key or Bearer token, modify `run_skill()`:

```python
def run_skill(skill_id: str, inputs: dict) -> dict:
    try:
        response = requests.post(
            f"{SANDBOX_URL}/run-skill",
            json={"skill_id": skill_id, "inputs": inputs},
            headers={"Authorization": f"Bearer {SANDBOX_API_KEY}"},  # add this
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception:
        return _mock_response(skill_id, inputs)
```

Set `SANDBOX_API_KEY` as an environment variable or read from `assets/credentials.json`.

### 9.5 Sandbox Contract Summary

| Property | Value |
|----------|-------|
| Protocol | HTTP/HTTPS |
| Base URL | Configurable (`SANDBOX_URL` in `sandbox_client.py`) |
| Health endpoint | `GET /health` → any 2xx |
| Execution endpoint | `POST /run-skill` |
| Request format | JSON body: `{skill_id: str, inputs: {key: value}}` |
| Success response | `{status: "success", output: str, execution_time_seconds: float, source: str}` |
| Error response | `{status: "error", error: str}` |
| Timeout | 30 seconds |
| Fallback | Auto mock on any exception or non-2xx status |
| Auth | None required by default; can be added in `run_skill()` |

### 9.6 Testing the Sandbox Connection

From inside the `im-agentic-os/` directory with the venv active:

```bash
# Health check
python -c "from components.sandbox_client import check_sandbox_health; print(check_sandbox_health())"

# Run a skill
python scripts/analyze.py srs-creator '{"repo_url":"https://github.com/x/y","api_name":"Search API","business_requirement":"Improve results"}'
```

---

## 10. Configuration Reference

### `assets/config.xlsx` Sheet Details

**Teams sheet:**
| Column | Type | Example |
|--------|------|---------|
| team_id | string | `team_001` |
| team_name | string | `Product Team` |
| is_active | boolean | `True` |

**Categories sheet:**
| Column | Type | Example |
|--------|------|---------|
| category_id | string | `cat_001` |
| category_name | string | `SRS & Docs` |
| team_id | string | `team_001` (FK to Teams) |
| is_active | boolean | `True` |

**RateLimits sheet:**
| Column | Type | Example |
|--------|------|---------|
| role | string | `user` |
| max_runs_per_day | integer | `20` |
| max_runs_per_skill_per_day | integer | `5` |

**FileTypes sheet:**
| Column | Type | Example |
|--------|------|---------|
| extension | string | `.pdf` |
| is_active | boolean | `True` |

All sheets have hardcoded fallback defaults in the code if the xlsx is missing or
a sheet is unreadable.

---

## 11. Known Constraints & Edge Cases

| Constraint | How it's handled |
|------------|-----------------|
| `ran_at` timestamps include microseconds (e.g. `2026-05-15T14:32:11.827782`) | `pd.to_datetime(..., format="ISO8601")` required — already fixed in `2_skill_creator.py:453` |
| Sandbox unreachable | Silent mock fallback; admin dashboard shows health indicator |
| Duplicate skill name | Checked against both `skills_registry.json` + `pending_skills.json` before submission |
| Admin self-lockout | Role/enabled toggles disabled for the currently logged-in admin's own row |
| Rate limit hit | Run button disabled before any API call is made |
| Invalid zip upload | Validated for SKILL.md + scripts/*.py before storing; itemised error list shown |
| File upload fields | Current implementation captures filename only — actual bytes are not forwarded to sandbox |
| Concurrency | JSON flat files have no locking — race conditions possible under concurrent writes (not a concern for single-tenant demo) |

---

## 12. Running the App

```bash
# Navigate to project folder
cd "C:\Users\Akshat Jain\Desktop\Trade & Tender\Code\Hackathon\im-agentic-os"

# Activate virtual environment
.venv\Scripts\activate

# Start the app
streamlit run app.py
```

Default URL: `http://localhost:8501`

Demo credentials visible on the login screen left panel:
- `im_user` / `User@1234`
- `im_creator` / `Creator@1234`
- `im_admin` / `Admin@1234`
