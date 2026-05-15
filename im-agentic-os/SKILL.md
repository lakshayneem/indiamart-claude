---
name: im-agentic-os
description: >
  Use this skill when you need to deploy a multi-role AI skill platform that enables
  skill creators to publish Claude Code skills and non-technical internal employees
  to run those skills through a click-button dashboard — without terminal access.
  Trigger this skill when: setting up an internal AI skills marketplace, enabling
  non-technical team members to use Claude-powered workflows, or building a
  governed skill distribution platform with admin controls.
---

## Overview

IM Agentic OS is an internal IndiaMART platform that bridges the gap between
technical skill creators and non-technical business users. Skill creators build
and publish Claude Code skills through a structured submission workflow. Internal
employees discover and run those skills via a branded Streamlit dashboard —
no terminal, no code, no friction.

The platform supports three roles — Employee, Skill Creator, and Admin — each
with a separate authenticated experience. All skill executions are routed through
a sandbox API, with automatic mock fallback for demo reliability. Every interaction
is tracked for adoption analytics, surfacing hours saved and usage trends
across teams.

## When to Use

Use this skill when:
- You want to increase adoption of Claude Code skills across non-technical teams
- Internal employees need AI-powered workflows but cannot use the terminal
- A governed approval workflow is needed before skills reach end users
- You need to track skill usage, adoption metrics, and time saved at scale
- Skill creators need a structured publishing channel with feedback loops

Trigger phrases:
- "Deploy the IM Agentic OS platform"
- "Set up the skill marketplace"
- "Launch the skills dashboard"
- "Enable skill access for non-technical users"

## Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `skill_id` | string | Yes | The identifier of the skill to execute |
| `inputs` | dict | Yes | Key-value pairs matching the skill's input_fields definition |
| `username` | string | Yes | Authenticated user's username (from session) |
| `role` | string | Yes | User's role: user \| creator \| admin |

Input fields for each skill are dynamically defined by the skill creator at
submission time. The platform renders the correct form at runtime by reading
the skill's `input_fields` array from `data/skills_registry.json`.

## Workflow

1. **Authentication** (`app.py`)
   - User submits username + password
   - `components/auth.py` hashes password (SHA-256) and compares with stored hash
   - On success: session state populated with username, name, role, team
   - User routed to role-appropriate page

2. **Skill Discovery** (`pages/1_user_dashboard.py`)
   - `scripts/fetch_data.py` reads `data/skills_registry.json`
   - Skills filtered by team, category, and search query
   - Featured skills shown in hero row; "New" badge applied to skills approved in last 7 days
   - Hours-saved counter computed by `components/hours_counter.py`
   - Announcements rendered by `components/announcement_banner.py`

3. **Quota Check** (`components/quota_checker.py`)
   - Before execution: daily run count computed from `data/adoptions.json`
   - Rate limits read from `assets/config.xlsx` (RateLimits sheet)
   - If limit exceeded: Run button disabled, clear message shown

4. **Skill Execution** (`components/sandbox_client.py`)
   - `POST http://localhost:8000/run-skill` with `skill_id` and `inputs`
   - If sandbox unreachable: automatic fallback to mock response (see mock responses in sandbox_client.py)
   - Result returned as `{"status": "success"|"error", "output": str, "execution_time_seconds": float}`

5. **Output Rendering** (`components/output_renderer.py`, `scripts/render_report.py`)
   - `render_report.py` appends metadata footer to raw output
   - Output displayed as formatted markdown in Claude-chat-style panel
   - Download button provides `.md` file of the full output

6. **Run Logging** (`data/adoptions.json`)
   - Each successful run appended to adoptions log with: run_id, skill_id, username, status, execution_time, ran_at

7. **Skill Submission** (`pages/2_skill_creator.py`)
   - 4-step form: Source → Metadata → Input Fields → Projection & Submit
   - Zip validation checks for SKILL.md and scripts/*.py
   - Skill preview renders card and input form as users will see them
   - On submit: saved to `data/pending_skills.json` with status: "pending"

8. **Admin Approval** (`pages/3_admin.py`)
   - Admin reviews pending skills; approves or rejects with mandatory reason
   - Bulk approval supported for multiple skills simultaneously
   - Approved skills moved to `data/skills_registry.json`
   - All actions logged to `data/audit_log.json`

## Outputs

The platform produces the following outputs per skill run:

```json
{
  "status": "success",
  "skill_id": "srs-creator",
  "output": "# Software Requirements Specification\n...",
  "execution_time_seconds": 12.4,
  "source": "live | mock"
}
```

Formatted outputs are downloadable as `.md` files. Analytics outputs include:
- Hours saved per month (platform-wide and per creator)
- Skill-wise usage stats (runs, unique users, avg rating)
- User-wise activity stats
- Audit log entries (CSV export available)

## Environment Variables

No external API keys required for the base platform.
The sandbox integration uses:

| Variable | Description | Default |
|----------|-------------|---------|
| `SANDBOX_URL` | Base URL of the skill execution sandbox | `http://localhost:8000` |
| `SANDBOX_TIMEOUT` | Request timeout in seconds | `30` |

To connect a live sandbox, set `SANDBOX_URL` in `components/sandbox_client.py`.
Mock mode activates automatically when the sandbox is unreachable.

## Edge Cases

**1. Sandbox unavailable**
Platform detects connection failure (requests.exceptions.ConnectionError) and
silently falls back to mock responses. User experience is unaffected. Admin
dashboard shows sandbox status indicator (🟢 / 🔴).

**2. Rate limit reached**
Run button is disabled before the API call. Quota computed at runtime from
adoptions.json filtered to today's date. Message shows remaining time until
midnight reset. No wasted sandbox calls on rate-limited users.

**3. Invalid zip upload**
Zip is validated before any processing. Missing SKILL.md or empty scripts/
directory results in a clear itemised error list. No partial uploads stored.

**4. Skill name collision**
Duplicate skill name check runs against both skills_registry.json and
pending_skills.json before submission is accepted.

**5. Disabled user account**
Login returns a specific disabled state (distinct from wrong credentials).
User sees "Your account has been disabled. Contact admin." — username
existence is not revealed to prevent enumeration.

**6. Admin self-modification**
UI disables role and enabled toggles for the logged-in admin's own row.
Prevents accidental self-lockout.

## Example

**Input (SRS Creator skill):**
```json
{
  "skill_id": "srs-creator",
  "inputs": {
    "repo_url": "https://github.com/indiamart/product-search",
    "api_name": "Product Search API",
    "business_requirement": "We need to improve search relevance for buyer queries and reduce zero-result rate from 18% to under 5%."
  }
}
```

**Output (truncated):**
```markdown
# Software Requirements Specification
**Project:** IndiaMART Product Search Enhancement
**API / Feature:** Product Search API

## 1. Project Overview
The Product Search API enables buyers to discover supplier listings through
keyword search and category filtering...

## 2. Functional Requirements
| ID | Requirement | Priority |
|----|-------------|----------|
| FR-01 | Return ranked results by relevance score | P0 |
...
```

**Execution time:** ~12 seconds | **Download:** `srs-creator_output.md`

## Second Workflow

The same IM Agentic OS platform is used by the **QA Team** to run the
**Test Case Generator** skill — a completely different workflow, different
team, same platform.

**User:** QA Analyst (Internal IM Employee role)
**Skill:** Test Case Generator
**Input:** SRS document (paste from clipboard or upload .txt)
**Output:** Structured test cases with positive and negative scenarios, grouped
by functional area, with priority labels (P0/P1/P2)

The QA analyst browses to the QA Team category, selects "Test Case Generator",
pastes the SRS document, clicks "Run Skill", and downloads a `.md` file of
test cases — all without writing a single line of code.

This demonstrates the platform's modularity: one deployment serves Catalog Team,
Product Team, QA Team, Seller Success, and any future team that has an approved
skill — without any platform code changes.

**Second workflow reference:** `references/second-workflow-walkthrough.md`
