# Skill: data-report
<!-- version: 1.1 | owner: analytics-team -->

## Task
Analyze the data file(s) found in `/home/daytona/workspace/` and produce a formatted analytics report.

## Steps
1. Discover the data file(s) in `workspace/` (CSV, XLSX, JSON — use the first one if multiple)
2. Load with `pandas` and compute:
   - Row count, column count, column dtypes
   - Null counts per column
   - Numeric summary (mean, median, min, max, std) for numeric columns
   - Top-5 value counts for categorical columns
3. Generate charts where meaningful — save as PNG to `output/` (e.g. `output/distribution.png`)
4. Write the final report to `output/report.md` with sections:
   - Overview (file name, size, shape)
   - Schema (columns + dtypes + null counts)
   - Numeric summary
   - Categorical summary
   - Charts (embed PNGs with markdown links)
5. If no data file is found, write the error to `run.log` and exit cleanly with a single-line message
