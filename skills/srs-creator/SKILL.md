# Skill: srs-creator
<!-- version: 1 | owner: product-team -->

## Task
Generate a Software Requirements Specification document from a GitHub repo, API name, and business requirement.

## Steps
1. Note the inputs: `repo_url`, `api_name`, `business_requirement`
2. Produce `output/srs.md` with these sections:
   - Project Overview (purpose, business context)
   - Functional Requirements (table: ID, requirement, priority)
   - User Stories (3–5 stories)
   - Non-Functional Requirements (performance, security, scalability)
   - API Specifications (endpoint, auth, request/response schemas, error codes)
   - Acceptance Criteria (checklist)
   - Out of Scope
   - Glossary
3. Append step-by-step entries to `output/run.log`
