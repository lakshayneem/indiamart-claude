# Second Workflow: Test Case Generator — QA Team

This document demonstrates how the same IM Agentic OS platform serves a
completely different team and workflow, proving the skill's modularity (Axis 5).

## Workflow Overview

**Team:** QA Team
**User:** QA Analyst (Internal IM Employee role)
**Skill:** Test Case Generator
**Problem:** QA analysts spend 3–5 hours manually writing test cases for each
feature SRS. With 5 feature releases per sprint and 3 QA analysts, that is
45–75 analyst-hours per sprint on test case writing alone.

## Step-by-Step Walkthrough

### 1. Login
QA Analyst logs in as `im_user` (Employee role).
Platform routes them to the User Dashboard.

### 2. Skill Discovery
- Analyst selects "QA Team" from the Team filter
- Category automatically filters to QA Team categories
- "Test Case Generator" appears in the skill grid with:
  - Team badge: "QA Team"
  - Category badge: "Test Cases"
  - Estimated run time: ~3 minutes
  - Rating: ★★★★☆ (4.0)

### 3. Running the Skill
Analyst clicks "Run Skill" on the Test Case Generator card.

Input form shows one field:
- **SRS Document** (textarea, required)
  Placeholder: "Paste your SRS document or feature description here..."

Analyst pastes the SRS document for the new "Buyer Verification Flow" feature
(generated earlier using the SRS Creator skill — natural skill chaining).

Analyst clicks "▶ Run Skill".

### 4. Execution
- IndiaMART-branded loading animation plays
- Status messages: "Connecting to skill..." → "Processing your request..." → "Generating output..."
- Sandbox receives: `{"skill_id": "test-case-generator", "inputs": {"srs_document": "..."}}`
- Response arrives in ~9 seconds

### 5. Output
Claude-chat style output panel shows:

```
✅ Skill Output — Test Case Generator | Completed in 9.2s | 15 May 2026, 14:32
```

Output includes 16 structured test cases:
- 8 positive (happy path) cases
- 6 negative (edge/error) cases
- 2 performance test cases

Each test case includes: Input, Expected Output, Priority label (P0/P1/P2)

### 6. Download
Analyst clicks "⬇ Download Output" → downloads `test-case-generator_output.md`
File is immediately usable in JIRA, Confluence, or the QA tracking tool.

### 7. Feedback
Analyst rates the skill 5 stars, leaves comment:
"Covered all the edge cases I would have written manually. Saved me 4 hours."

## Impact Comparison

| Metric | Manual | With Skill |
|--------|--------|-----------|
| Time per SRS | 4–5 hours | ~9 seconds |
| Test cases produced | 10–15 | 16 (structured) |
| Consistency | Variable | Standardised format |
| Analyst effort | High | Review + adjust |

**Adoption projection:** 3 min × 5 runs/day × 150 QA analysts = **37 hours saved/month**

## Why This Proves Modularity

The Test Case Generator skill runs on the exact same:
- Platform infrastructure (Streamlit dashboard, same login, same nav)
- Sandbox API integration (`POST /run-skill` with `skill_id` + `inputs`)
- Rate limiting and quota system
- Output rendering and download flow
- Feedback and rating system
- Admin approval governance

Only the `skill_id` and `input_fields` are different.
The platform requires zero code changes to support a new team or skill.
Any approved skill — for any IM team — is immediately available to all
users in that team through the same interface.

This is the core value proposition of IM Agentic OS:
**one platform, infinite skills, any team, no terminal.**
