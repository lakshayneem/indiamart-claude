# IM Agentic OS — Domain Rules

## Skill Naming Rules
- Skill names must be alphanumeric with spaces or hyphens only
- Maximum 60 characters
- Must be unique across skills_registry.json and pending_skills.json
- Skill IDs are auto-derived: lowercase, spaces replaced with hyphens

## Required Folder Structure
Every submitted skill must include:
```
your-skill/
├── SKILL.md          (required — must contain YAML frontmatter with name and description)
├── scripts/
│   └── *.py          (required — at least one Python script)
├── references/       (optional but recommended)
└── assets/           (optional)
```

## Description Format
- Must start with "Use this skill when..."
- Must name at least 2 concrete trigger phrases
- Maximum 300 characters in the submission form
- Full SKILL.md description can be longer

## Adoption Projection Requirements
All submitted skills must provide:
- X: Estimated minutes per occurrence (positive integer)
- Y: Occurrences per day per user (positive integer)
- N: Estimated number of adopters (positive integer)
Formula: Total hours saved/month = (X × Y × N × 22 working days) / 60

## Approval Workflow
1. Creator submits → status: "pending" in pending_skills.json
2. Admin reviews metadata, input fields, adoption projection
3. Admin approves → moved to skills_registry.json, status: "approved"
   OR Admin rejects → status: "rejected", rejection_reason set (min 20 chars)
4. Creator can resubmit a rejected skill after addressing the reason
5. Creator can edit an approved skill → creates a pending_update version
   The live approved version stays active until the update is approved

## Rate Limiting Rules
- Limits defined per role in assets/config.xlsx > RateLimits sheet
- Defaults: User: 20/day, Creator: 50/day, Admin: unlimited
- Per-skill limits also apply (separate from overall daily limit)
- Quota computed at runtime from data/adoptions.json filtered to today's date
- Resets at midnight (no explicit reset action required)

## File Upload Rules
- Accepted file types defined per skill by the creator
- Global allowed types sourced from assets/config.xlsx > FileTypes sheet
- Maximum file size: defined per skill (1MB / 5MB / 10MB / 25MB)
- Skill submission zips: max 50MB

## Privacy Rules
- User full names are never shown in public feedback — only initials
- Users cannot see other users' favourite skills
- Skill request requester shown as initials only on public board

## Audit Log Rules
- All admin actions must be logged to data/audit_log.json
- Log is append-only — no deletions or modifications to existing entries
- Failed actions are also logged with their error
- Log entries include: log_id, actor, action, target, details, created_at
