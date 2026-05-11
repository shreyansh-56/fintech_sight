"""Command-line entrypoint for running the FinSight pipeline and evaluation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from Finsight.evaluation.runner import evaluate_pipeline_run
from Finsight.pipeline.orchestrator import FinSightPipeline
from Finsight.tools.symbols import resolve_ticker


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the FinSight pipeline end-to-end")
    parser.add_argument("company", help="Company name to research (ticker auto-resolved)")
    parser.add_argument(
        "--analysis-goal",
        default="Generate a holistic investment memo",
        help="High-level analysis goal passed to the analysis and writing agents",
    )
    parser.add_argument(
        "--fred-series",
        nargs="*",
        metavar="LABEL=SERIES_ID",
        help="Optional FRED series to fetch (e.g., gdp=GDP unemployment=UNRATE)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("finsight_results.json"),
        help="Path to write artifacts and evaluation scores (JSON)",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        help="Optional JSONL file to capture variable memory events",
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="Enable price visualization refinement (requires stock history)",
    )
    return parser


def parse_fred_pairs(pairs: list[str] | None) -> dict[str, str] | None:
    if not pairs:
        return None
    mapping: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            continue
        label, series_id = pair.split("=", 1)
        mapping[label.strip()] = series_id.strip()
    return mapping or None


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    fred_series = parse_fred_pairs(args.fred_series)

    log_path = args.log_path if args.log_path else None
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    pipeline = FinSightPipeline(log_path=log_path)

    viz_spec = None
    viz_goal = None
    # Resolve ticker from company name
    try:
        ticker = resolve_ticker(args.company)
    except Exception as e:
        raise SystemExit(f"Failed to resolve ticker for '{args.company}': {e}")

    if args.visualize:
        viz_spec = {"type": "line", "y": ["Close"], "title": f"{ticker} Price"}
        viz_goal = f"Develop a presentation-ready price trend chart for {ticker}"

    artifacts = pipeline.run(
        company_name=args.company,
        ticker=ticker,
        analysis_goal=args.analysis_goal,
        fred_series_ids=fred_series,
        visualization_spec=viz_spec,
        visualization_goal=viz_goal,
    )

    scores = evaluate_pipeline_run(pipeline, artifacts)

    output = {
        "artifacts": artifacts,
        "scores": scores,
    }

    args.out.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Run complete. Artifacts and scores saved to {args.out}")


if __name__ == "__main__":
    main()
