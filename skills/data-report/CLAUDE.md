# Skill: data-report
<!-- version: 1.0 | owner: analytics-team -->

## Context
You are running inside a Daytona sandbox for the Company Skill Platform.
Working directory: /home/daytona/workspace
Output directory: /home/daytona/output
Available tools: Bash, Read, Write, Edit, Glob, Grep
Available libraries: pandas, matplotlib, openpyxl, requests

## Your task
Analyze the data file(s) uploaded to /home/daytona/workspace/ and generate a formatted report.
- Summarize key statistics (row count, column types, nulls, numeric summaries)
- Produce charts where meaningful (save as PNG to /home/daytona/output/)
- Write a final report to /home/daytona/output/report.md
- Log each step to /home/daytona/output/run.log

## Constraints
- Never access external URLs
- Write all outputs to /home/daytona/output/
- If no data file is found, write an error to run.log and exit cleanly
