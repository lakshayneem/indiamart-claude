# SRS Template — Section-by-Section Reference

The full IndiaMART Software Requirements Specification structure. The agent loads this only after deciding to draft (progressive disclosure). Every section here is mandatory in every SRS, even if minimal.

**Hard rule, applies everywhere below:** never invent fields, error messages, status codes, or behaviors. Everything must be verified from the actual Go source code first (controller, service, repository, router). If a value isn't in the code, write `_TBD_`.

## When to use this template

- Writing a new SRS document for a Go API (write or read).
- Updating an existing SRS to reflect code changes.
- The user says "create/update the SRS" or "write the spec document".

## Document structure

Fixed section order. Every section must be present.

1. Document Header (title page block)
2. Document Revision History
3. Table of Contents
4. SCOPE
5. SPECIFIC REQUIREMENT
   - Business Problem
   - Business Requirements (Input / Output Keys)
   - URL
   - Input: Common Parameters
   - Input: Action-specific tables
   - Successful Output
   - Validation Checks and Their Output
6. Logical Database Required
7. Table for Status and Code

---

## Section 1 — Document Header

Always starts with `# Document No. X` (sequential within the project), immediately followed by the metadata table.

```markdown
# Document No. 1

| Field | Value |
|---|---|
| Service Name | <Full Service Name - e.g. "PC Item Approval Rule Master Write API"> |
| Effective Date | _TBD_ |
| Version No. | 1.0 |
| Prepared By | _TBD_ |
| Reviewed By | _TBD_ |
| Approved By | _TBD_ |
```

Rules:
- `Service Name` must be descriptive: domain entity + operation type (Write API / Read API).
- Leave `Effective Date`, `Prepared By`, `Reviewed By`, `Approved By` as `_TBD_` unless the user provides them.
- Start at version `1.0` for new documents.

---

## Section 2 — Document Revision History

```markdown
## Document Revision History

A - Added, M - Modified, D - Deleted.

| Sr. No | Version | Date | A, M, D | Page Number | Changes incorporated in brief |
|---|---|---|---|---|---|
| 1 | 1.0 | _TBD_ | A | - | Initial release - <one line describing what the API does and key design choices> |
| 2 | | | | | |
| 3 | | | | | |
```

Rules:
- First row always describes the initial release.
- Brief must mention: what the API exposes (insert/update/read), the table it operates on, endpoint style (single POST, multiple endpoints, etc.).
- Keep 2-3 empty placeholder rows for future revisions.

---

## Section 3 — Table of Contents

```markdown
## Table of Contents

- SCOPE
- SPECIFIC REQUIREMENT
    - Business Problem
    - Business Requirements (Input / Output Keys)
    - Input & Output Parameters
    - URL
    - Input: Common Parameters
    - Input: <Action-specific sections>
    - Successful Output
    - Validation Checks and Their Output
- Logical Database Requirements
- Table for Status and Code
```

Rules:
- Always present, always matches the actual sections in the document.
- Sub-items under SPECIFIC REQUIREMENT must list each input section that exists (e.g., "Input: Insert Parameters (ACTION=I)", "Input: Update Parameters (ACTION=U)").

---

## Section 4 — SCOPE

```markdown
# SCOPE

<2-3 paragraphs explaining:>
1. Purpose of this document (guidelines for developers, QA, product team)
2. What the service does (entity it manages, which table, what operations)
3. Who uses it (GLADMIN users, internal tools, etc.) and how (HTTP method, endpoint pattern)
```

Rules:
- Mention the exact table name with schema prefix (e.g., `public.pc_item_approval_rule_master`).
- State the HTTP method and dispatch mechanism (e.g., "single POST endpoint, action-flag dispatch").
- Mention the consuming application/screen.

---

## Section 5 — SPECIFIC REQUIREMENT

### 5.1 Business Problem

```markdown
## Business Problem

<1-2 paragraphs explaining:>
1. What manual/problematic process this API replaces
2. Why automation is needed (speed, risk, operational load)
3. How the API will be consumed (which screen/tool)

Works on: HTTP.
Supported method: **POST** (or GET, etc.)
```

Rules:
- End with the protocol and method declaration.
- If single-endpoint with action dispatch, state that clearly.

### 5.2 Business Requirements — Input Keys

```markdown
## Business Requirements

Please find below the Keys used for Input and Output.

### Input Keys (JSON body)

- `<FIELD_NAME>` (**Mandatory**/**Optional**) - <Description>. <DB type/constraint if applicable>. Eg; <example value>
```

Rules for each key entry:
- Format: `` `field_name` (**Mandatory**/**Optional**) - Description. DB constraint. Eg; example ``
- For conditional mandatory fields, state the condition: `(**Mandatory on INSERT**)`, `(**Mandatory on UPDATE**)`.
- For fields mandatory only when another is absent: `(**Mandatory on INSERT when \`other_field\` is absent**)`.
- After listing all keys, provide a summary block:

```markdown
Required inputs on INSERT - `AK`, `VALIDATION_KEY`, `ACTION=I`, <list all mandatory insert fields>.
Required inputs on UPDATE - `AK`, `VALIDATION_KEY`, `ACTION=U`, `rule_id`, plus at least one writable field.
```

### 5.3 Business Requirements — Output Keys

```markdown
### Output Keys (JSON response)

- `STATUS` - Operation result. Eg; SUCCESSFUL, FAILED
- `CODE` - Logical code. Eg; 200, 500
- `MESSAGE` - Human-readable result message. Eg; INSERT SUCCESS, UPDATE SUCCESS
- `<ID_FIELD>` - <Description>. Present only on <condition>.
- `SERVICE_NAME` - Always `<service_name from code>`.
- `RESPONSE_DATA` - Request/response metadata block.
    - `MODID` - Resolved module name from `VALIDATION_KEY` via `Gateway_v1`.
    - `SEARCH_ID` - <Description or "Empty string for this endpoint.">.
    - `PROCESS_NAME` - Mirrors the resolved `MODID`.
    - `REQUEST_CAME_AT` - Request arrival timestamp in `YYYYMMDDHHmmss.ffffff` format, Asia/Kolkata.
    - `RESPONSE_GIVEN_AT` - Response dispatch timestamp in same format.
    - `RESPONSE_TIME` - Overall request processing time in microseconds.
    - `QUERY_EXECUTION_TIME` - Nested object `{ "QUERY_EXECUTION_TIME": <ms> }`.
```

Rules:
- Every key in the actual JSON response must be documented.
- Note which keys appear conditionally (e.g., "Present only on a successful INSERT response").
- For nested objects, use indented sub-list.

### 5.4 URL

```markdown
## URL

<Brief description of endpoint pattern.>

- **dev**: `http://dev-service.intermesh.net/<path>`
- **stage**: `http://stg-service.intermesh.net/<path>`
- **live**: `http://service.intermesh.net/<path>`
```

Rules:
- Always list all three environments (dev, stage, live).
- If single endpoint with action dispatch, state that.
- No path or query parameters if dispatch is via body field.

### 5.5 Input: Common Parameters Table

```markdown
## INPUT: COMMON PARAMETERS

These are required on every call, regardless of ACTION.

| Parameters | Values | Mandatory / Optional | Description |
|---|---|---|---|
| `AK` | Example: `<jwt>` | M | <Description of auth mechanism> |
| `VALIDATION_KEY` | `<hash>` | M | <What it resolves to and how> |
| `ACTION` | `I` (insert) or `U` (update) | M | <What it controls> |
```

Rules:
- Table columns are always: Parameters, Values, Mandatory / Optional, Description.
- Use `M` for Mandatory, `O` for Optional.
- Values column shows example values.
- Description column explains purpose and mechanism.

### 5.6 Input: Action-Specific Parameter Tables

One section per action. Title format: `` ## INPUT: <ACTION_NAME> PARAMETERS (`ACTION=<X>`) ``.

```markdown
## INPUT: INSERT PARAMETERS (`ACTION=I`)

| Parameters | Values | Mandatory / Optional | Description |
|---|---|---|---|
| `field_name` | <example> | M or O | <Description>. <db_type>. <constraint>. |
```

After each table, include a sample request body as a fenced JSON block:

````markdown
### Sample INSERT request body

```json
{
    "AK": "<jwt>",
    "VALIDATION_KEY": "<hash>",
    "ACTION": "I",
    ...all mandatory and some optional fields with realistic values...
}
```
````

Rules:
- Every field in the table must appear in the sample (mandatory ones required, optional ones can be included as examples).
- For UPDATE, add a note about COALESCE behavior: `Omitted fields are preserved in the DB via COALESCE($n, col)`.
- State explicitly: "At least one writable field must be supplied alongside `rule_id`."

### 5.7 Successful Output

````markdown
## SUCCESSFUL OUTPUT

### <Action> success

```json
{
    "STATUS": "SUCCESSFUL",
    "CODE": "200",
    "MESSAGE": "<EXACT success message from code>",
    ...other top-level keys...
    "SERVICE_NAME": "<service_name>",
    "RESPONSE_DATA": {
        "MODID": "<resolved module>",
        "SEARCH_ID": "",
        "PROCESS_NAME": "<process>",
        "REQUEST_CAME_AT": "<timestamp>",
        "RESPONSE_GIVEN_AT": "<timestamp>",
        "RESPONSE_TIME": <microseconds>,
        "QUERY_EXECUTION_TIME": { "QUERY_EXECUTION_TIME": <ms> }
    }
}
```
````

Rules:
- One subsection per distinct success response shape.
- Copy exact MESSAGE strings from the Go code.
- Timestamps use `YYYYMMDDHHmmss.ffffff` format.
- `RESPONSE_TIME` is in microseconds, `QUERY_EXECUTION_TIME` inner value is in milliseconds.

### 5.8 Validation Checks and Their Output

This is the most detailed section. Document EVERY validation failure the API can produce.

```markdown
## VALIDATION CHECKS AND THEIR OUTPUT

The transport-level HTTP status is always `200`. The logical failure is expressed through `STATUS`, `CODE`, and `MESSAGE`.

For app-level validation failures, no DB query is executed, so `QUERY_EXECUTION_TIME` is returned as an empty array. ...

The updater field used by this API is `<field_name>`.
```

Then for EACH validation scenario:

1. A description line: `` If `field_name` is absent: `` or `` If `field_name` is not numeric: ``
2. The full JSON response body as a fenced code block.

````markdown
If `field_name` is absent:

```json
{
    "CODE": "500",
    "MESSAGE": "<EXACT error message from code>",
    "RESPONSE_DATA": {
        "MODID": "<module>",
        "PROCESS_NAME": "<process>",
        "QUERY_EXECUTION_TIME": [],
        "REQUEST_CAME_AT": "<timestamp>",
        "RESPONSE_GIVEN_AT": "<timestamp>",
        "RESPONSE_TIME": <number>,
        "SEARCH_ID": ""
    },
    "SERVICE_NAME": "<service_name>",
    "STATUS": "FAILED"
}
```
````

Rules:
- **Copy error messages EXACTLY from Go source code** — never paraphrase.
- Group validations logically:
  1. Common validations (`VALIDATION_KEY`, `ACTION`).
  2. Insert-specific required field checks.
  3. Numeric type validations.
  4. String length validations.
  5. Update-specific validations (`rule_id`, at least one field).
  6. DB-level errors (connection, constraint violations).
  7. Middleware-level auth failures (`AK` missing/invalid/expired).
- For DB/infrastructure errors, use format: `"<operation description>: <driver error>"`.
- For middleware auth failures, document the different response envelope (different keys like `HTTP_X_FORWARDED_FOR`, `REMOTE_ADDR`, `REQUEST_URI`, `unique_id`, `log_type`).
- Note at the start: "For app-level validation failures, no DB query is executed, so `QUERY_EXECUTION_TIME` is returned as an empty array."
- JSON keys in error responses are alphabetically sorted (as Go's `json.Marshal` produces).

---

## Section 6 — Logical Database Required

```markdown
# LOGICAL DATABASE REQUIRED

- Database: **<DB Name>** (application connection pool name: `<pool_name>`).
- Table: `<schema.table_name>`.
- Primary key: `<pk_column>` (NOT NULL; DEFAULT `nextval('<sequence_name>')`).
- Replication: <replication details if any>.
```

Then the schema table:

```markdown
Schema of `<schema.table_name>`:

| Column | Data Type | Nullable | Default |
|---|---|---|---|
| `column_name` | <exact postgres type> | NOT NULL / YES | <default or -> |
```

Then index information:

```markdown
Index: `<index_name>` - <type>, <what it indexes>.
```

Then the SQL statements used by the API:

````markdown
### SQL statements issued by the API

**INSERT** (one statement per request):

```sql
INSERT INTO TABLE_NAME (
    COL1, COL2, ...
) VALUES (
    $1, $2, ...
)
RETURNING PK_COLUMN;
```

**UPDATE** (one statement per request; `COALESCE` preserves omitted columns):

```sql
UPDATE TABLE_NAME SET
    COL1 = COALESCE($1, COL1),
    ...
WHERE PK = $N;
```
````

Rules:
- Use exact column names and types from the database (verify from migration or schema dump).
- Document COALESCE pattern for partial updates.
- Note transaction behavior: "No explicit `BEGIN`/`COMMIT`/`ROLLBACK` — each statement runs under Postgres autocommit."
- SQL uses uppercase keywords and uppercase table/column names (matching the actual queries in repository code).

---

## Section 7 — Table for Status and Code

```markdown
# TABLE FOR STATUS AND CODE

| CODE | STATUS | MESSAGE |
|---|---|---|
| 200 | SUCCESSFUL | `<success messages and when they occur>` |
| 500 | FAILED | <Category of failure>. Exact message from service/controller. |
| 400 | FAILURE | Middleware: `AK` missing. Produced before the controller runs. |
| 401 | FAILURE | Middleware: `AK` signature validation failed. |
| 402 | FAILURE | Middleware: `AK` token expired. |
| 403 | FAILURE | Middleware: `AK` token format invalid. |
```

Rules:
- Group `500` errors by category (app-level validation vs infrastructure).
- Reference the Validation Checks section for exact messages.
- Middleware codes (`400`–`403`) are standard across all APIs — always include them.
- Note: `STATUS` is `SUCCESSFUL`/`FAILED` for app-level, `FAILURE` for middleware-level.

---

## Pre-Submission Checklist

Before finishing the SRS, verify:

| # | Check |
|---|---|
| 1 | All 7 sections present in correct order |
| 2 | Metadata table has correct service name |
| 3 | All input fields documented with type, mandatory/optional, example |
| 4 | All output keys documented including nested `RESPONSE_DATA` |
| 5 | All 3 environment URLs listed |
| 6 | Every validation error has exact message from code + full JSON example |
| 7 | DB schema table matches actual table definition |
| 8 | SQL statements match actual repository code |
| 9 | Status/Code table covers all possible responses |
| 10 | No invented information — everything verified from source code |
| 11 | Error response JSON keys are alphabetically ordered |
| 12 | Timestamps use `YYYYMMDDHHmmss.ffffff` format in examples |
| 13 | Markdown tables render correctly (consistent column counts) |

---

## Common Mistakes to Avoid

- Do NOT invent error messages — copy them exactly from Go source.
- Do NOT skip the middleware auth failure section — it's standard for all APIs.
- Do NOT use different timestamp formats in different examples.
- Do NOT forget to document the `COALESCE` behavior for update operations.
- Do NOT omit the "at least one of X or Y" conditional mandatory rules.
- Do NOT skip documenting the `QUERY_EXECUTION_TIME` empty-array behavior on validation failures.
- Do NOT mix up STATUS values: app-level uses `SUCCESSFUL`/`FAILED`, middleware uses `FAILURE`.
- Do NOT forget the revision history placeholder rows.
- Do NOT put code-specific information in the SCOPE that should be in Business Problem.
