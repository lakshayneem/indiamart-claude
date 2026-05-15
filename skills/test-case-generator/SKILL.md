# Skill: test-case-generator
<!-- version: 1 | owner: qa-team -->

## Task
Generate structured test cases from an SRS document or feature description.

## Steps
1. Parse `srs_document` for functional requirements, NFRs, API specs, acceptance criteria
2. Produce test cases organised by category:
   - Positive (happy path)
   - Negative (edge / error)
   - Performance (if NFRs specify targets)
3. Each test case: ID, title, input, expected result, priority (P0/P1/P2)
4. Write `output/test_cases.md` with a suite overview table followed by each `### TC-NNN` section
5. Append step-by-step entries to `output/run.log`
