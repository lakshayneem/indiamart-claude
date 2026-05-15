# Output Schema Reference

## skills_registry.json — Skill Object
```json
{
  "skill_id": "string (kebab-case, unique)",
  "name": "string (max 60 chars)",
  "description": "string (starts with 'Use this skill when...')",
  "team": "string (from config.xlsx Teams sheet)",
  "category": "string (from config.xlsx Categories sheet)",
  "tags": ["string"],
  "creator_id": "string (username of creator)",
  "status": "approved | pending | rejected | pending_update",
  "version": "integer (increments on each approved update)",
  "is_featured": "boolean",
  "created_at": "ISO 8601 datetime string",
  "approved_at": "ISO 8601 datetime string | null",
  "rejection_reason": "string | null",
  "input_fields": [
    {
      "key": "string (snake_case, unique within skill)",
      "label": "string",
      "type": "text | textarea | number | dropdown | file_upload | date",
      "required": "boolean",
      "placeholder": "string",
      "options": ["string"],
      "allowed_file_types": [".pdf", ".docx"],
      "max_file_size": "1MB | 5MB | 10MB | 25MB"
    }
  ],
  "adoption_projection": {
    "x_mins": "integer (minutes per occurrence)",
    "y_occurrences_per_day": "integer",
    "n_adopters": "integer",
    "hours_saved_per_month": "float"
  }
}
```

## Sandbox API — Run Skill Request
```json
{
  "skill_id": "string",
  "inputs": {
    "field_key": "field_value"
  }
}
```

## Sandbox API — Success Response
```json
{
  "status": "success",
  "skill_id": "string",
  "output": "string (markdown formatted)",
  "execution_time_seconds": "float",
  "source": "live | mock"
}
```

## Sandbox API — Error Response
```json
{
  "status": "error",
  "skill_id": "string",
  "error": "string (human-readable error message)"
}
```

## data/adoptions.json — Run Log Entry
```json
{
  "run_id": "string (uuid short)",
  "skill_id": "string",
  "username": "string",
  "status": "success | error",
  "execution_time": "float (seconds)",
  "ran_at": "ISO 8601 datetime string"
}
```

## data/audit_log.json — Audit Entry
```json
{
  "log_id": "string",
  "actor": "string (username)",
  "action": "skill_approved | skill_rejected | skill_submitted | role_changed | user_disabled | user_enabled | user_created | announcement_posted | announcement_deleted | rate_limit_changed",
  "target": "string (skill_id | username | announcement_id | role)",
  "details": "string (human-readable description)",
  "created_at": "ISO 8601 datetime string"
}
```

## Hours Saved Calculation
```
hours_saved = SUM(runs × x_mins) / 60
where x_mins = skill.adoption_projection.x_mins for each run's skill
```
