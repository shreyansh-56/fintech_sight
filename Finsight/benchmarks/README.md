# FinSight Benchmark Scaffold

The FinSight paper evaluates the system on a curated benchmark of 20 targets (10 company-level, 10 industry-level) with corresponding professional reference reports and automated metrics.

This folder provides a scaffold you can populate with your own benchmark data:

```
Finsight/benchmarks/
├── README.md              # This document
├── data/
│   ├── company/
│   │   └── sample_company.json
│   └── industry/
│       └── sample_industry.json
└── references/
    └── sample_company_report.md
```

## Data Format

Each entry under `benchmarks/data/` should be a JSON file with the following structure:

```json
{
  "research_question": "Research the future of the robotics industry.",
  "ticker": "Example",
  "company_name": "Example Corp",
  "analysis_goal": "Assess Example Corp's financial health and growth outlook.",
  "fred_series_ids": {
    "gdp": "GDP",
    "unemployment": "UNRATE"
  },
  "reference_conclusions": [
    "Example Corp maintains strong margins",
    "Example Corp expanding into emerging markets"
  ],
  "key_points": [
    "Revenue growth across segments",
    "Capital expenditure trends"
  ]
}
```

Place the corresponding professional or authoritative report in `benchmarks/references/` (Markdown or PDF), and update the JSON with the filename if you want to link them explicitly.

## Running Benchmarks

1. Populate the data and references folders.
2. Use the CLI to run each benchmark target and log the outputs:
   ```bash
   python Finsight/cli.py "Example Corp" EXAMPLE --analysis-goal "Assess Example Corp's financial health" --fred-series gdp=GDP --visualize
   ```
3. Use `evaluation/runner.py` to compute automated scores, optionally comparing against the stored reference conclusions.

This scaffold keeps the project aligned with the FinSight paper and provides a place to store reproducible evaluations.
