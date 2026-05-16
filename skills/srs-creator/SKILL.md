---
name: srs-creator
description: Generate a Software Requirements Specification document from a Go API repository. Use when the user asks for an SRS, API spec document, or wants to update an existing SRS for a write/read API. Produces both srs.md and srs.docx in /home/daytona/output/.
---

# SRS Creator

Generates an IndiaMART-format Software Requirements Specification document from a Go API codebase. The deliverable is a `.docx` file ready for review; the intermediate `.md` is also kept for diffing.

## Inputs (from the prompt)

- `repo_url` — GitLab URL of the Go service. **The repo is already pre-fetched and extracted at `/home/daytona/workspace/repo/`.** Do not run `git clone`.
- `api_name` — descriptive service name (e.g. *PC Item Approval Rule Master Write API*).
- `business_requirement` — short prose: the problem this API solves, who consumes it.
- `ticket_id` — *optional*. If provided, the OpenProject ticket is pre-fetched to `/home/daytona/workspace/ticket.json` and contains the work package body, all activities/comments (mention tags flattened, author names resolved), and attachment metadata. Use it for context only — the SRS body must still come from real code, never from ticket text.

## Reference

The full SRS structure — all 7 sections, every field rule, every validation pattern, every common mistake — is in `/home/daytona/skills/srs-creator/references/srs-template.md`. **Read it before drafting.** Don't keep its content in the prompt; load it on demand.

## Workflow

```
Workflow Progress:
- [ ] Step 1: Orient in the pre-fetched repo
- [ ] Step 2: Identify the Go entry points (controller, service, repository, router)
- [ ] Step 3: Verify every fact from source — never invent
- [ ] Step 4: Draft srs.md following /home/daytona/skills/srs-creator/references/srs-template.md
- [ ] Step 5: Convert to srs.docx via scripts/md_to_docx.py
- [ ] Step 6: Verify both files exist and confirm in run.log
```

### Step 1 — Orient in the pre-fetched repo

The repo is already at `/home/daytona/workspace/repo/` — fetched on the host before this sandbox started. **Do not run `git clone`** and do not try to network out for source; if the tree is missing, fail loudly.

```bash
ls /home/daytona/workspace/repo
```

Expected layout for an IndiaMART Go service: `cmd/`, `internal/`, `pkg/`, `go.mod`, plus `Dockerfile.*` variants per deployable. Skim `README*`, `cmd/`, `internal/`, `pkg/` and find the service that matches `api_name`.

If `ticket_id` was provided, `/home/daytona/workspace/ticket.json` is also available — keys: `work_package` (subject, description, status, customFields), `activities` (comments + system events, each with `_resolved_author` and cleaned `comment.raw`), `attachments`. Read it for *context* about why the change is happening — do **not** lift field names, error messages, or behaviors from it into the SRS body.

### Step 2 — Find the four files

For an IndiaMART Go service the SRS draws from exactly four layers:

| Layer | Where | What you extract |
|---|---|---|
| Router | usually `cmd/*/main.go` or `routes.go` | HTTP method, URL path, action-flag dispatch |
| Controller | `internal/<service>/controller/*.go` | Request parsing, validation order, exact error messages |
| Service | `internal/<service>/service/*.go` | Business logic, success messages, MODID / SERVICE_NAME |
| Repository | `internal/<service>/repository/*.go` | SQL statements, table name, column names |

Use `Grep` for things like `STATUS.*FAILED`, `MESSAGE`, `RESPONSE_DATA`, `INSERT INTO`, `UPDATE.*SET`, `COALESCE`. Use `Read` for the matched files.

### Step 3 — Verify every fact

Hard rule from `/home/daytona/skills/srs-creator/references/srs-template.md`: **never invent fields, error messages, status codes, or behaviors. Everything must be traced to a specific line in the Go source.**

If the code says `"PARAM IS MANDATORY"`, the SRS says `"PARAM IS MANDATORY"` — same case, same punctuation. If the table column is `pc_rule_id` not `rule_id`, the SRS uses `pc_rule_id`. If you can't find a value in the code, leave it as `_TBD_` — don't guess.

### Step 4 — Draft `output/srs.md`

Read `/home/daytona/skills/srs-creator/references/srs-template.md` and follow it section by section. The 7 sections are fixed; every one must be present even if some rows are minimal.

Write to `/home/daytona/output/srs.md`. Append progress to `/home/daytona/output/run.log`.

### Step 5 — Convert to `output/srs.docx`

Run the converter, passing the `api_name` value you received in the prompt as `--api-name`. Substitute the literal string, do not rely on a shell variable.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/md_to_docx.py \
    /home/daytona/output/srs.md \
    /home/daytona/output/srs.docx \
    --api-name "<the api_name value from the prompt>"
```

For example, if the prompt says `api_name: PC Item Approval Rule Master Write API`, run:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/md_to_docx.py \
    /home/daytona/output/srs.md \
    /home/daytona/output/srs.docx \
    --api-name "PC Item Approval Rule Master Write API"
```

The script:

1. Pandoc-converts the SRS markdown body.
2. Stamps the IndiaMART cover page from `assets/srs-template.docx` with the api name (uppercased).
3. Inserts a page break so the SRS body begins on page 2.
4. Merges everything into the final `.docx`.

If the script exits non-zero, the message identifies which step failed:

| Exit | Meaning | Action |
|---|---|---|
| 1 | Bad arguments or empty/missing markdown | Re-check `/home/daytona/output/srs.md` exists and is non-empty |
| 2 | `pandoc` not installed | Snapshot `company-claude-v1` needs rebuild — flag this and stop |
| 3 | `python-docx` not installed | Same as 2 |
| 4 | Pandoc conversion failed | Usually a malformed markdown table; fix the markdown |
| 5 | Cover template missing/malformed | Don't touch the script — escalate |
| 6 | Body merge failed | Don't touch the script — escalate |

Do not modify `scripts/md_to_docx.py` to work around an error. Fix the input.

### Step 6 — Verify and report

```bash
ls -lh /home/daytona/output/srs.md /home/daytona/output/srs.docx
```

Both files must exist and be non-empty. End with a one-line confirmation in stdout: `Produced output/srs.md (<N> KB) and output/srs.docx (<N> KB).`

## Sample run log entry

```
2026-05-16 10:32:14 found pre-fetched repo at /home/daytona/workspace/repo (329 files, go.mod: service-api-go)
2026-05-16 10:32:16 ticket.json present (WP 650234, 38 activities)
2026-05-16 10:32:18 located controller at internal/pcrule/controller/write_controller.go
2026-05-16 10:33:01 extracted 14 validation messages from controller + service
2026-05-16 10:34:20 wrote /home/daytona/output/srs.md (38 KB)
2026-05-16 10:34:22 wrote /home/daytona/output/srs.docx (52 KB)
```

## Pre-flight checklist

Before declaring done, walk through `Pre-Submission Checklist` in `/home/daytona/skills/srs-creator/references/srs-template.md`. Don't skip the "everything verified from source code" line — that's the most common failure.

## Common pitfalls

- Calling `claude` recursively — the agent IS Claude. Just write the markdown.
- Stopping at `srs.md` — the deliverable is the `.docx`. Step 5 is mandatory.
- Inventing exact error message strings or table column names. If unverified, leave `_TBD_`.
- Mixing app-level (`STATUS: FAILED`) and middleware-level (`STATUS: FAILURE`) error envelopes — they're different shapes; see the template.
- Running `git clone` or any network fetch for source — the repo is pre-fetched at `/home/daytona/workspace/repo/`. The sandbox has no SCM credentials; clones will hang or fail.
- Lifting field names / error strings / SQL from `ticket.json` into the SRS body. The ticket is context only; the SRS body must trace to lines in `repo/`.
