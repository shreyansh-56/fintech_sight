"""Enhanced FinSight pipeline orchestrator with parallel perspectives and comprehensive reporting."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

from Finsight.agents.data_collection import DataCollectionAgent
from Finsight.agents.deep_search import DeepSearchAgent
from Finsight.agents.perspective_agents import ParallelPerspectiveRunner
from Finsight.config.settings import get_settings
from Finsight.mechanisms.generative_retrieval import CoARetriever
from Finsight.runtime.orchestrator import Orchestrator
from Finsight.tools.data_collectors import MarketDataCollector, SECFilingCollector
from Finsight.tools.gemini_client import GeminiClient
from Finsight.tools.search import SearchClient
from Finsight.visualization.chart_generator import ChartGenerator
from Finsight.writing.enhanced_report_writer import EnhancedReportWriter


class EnhancedFinSightPipeline:
    """Enhanced pipeline with parallel perspectives and 20,000+ word reports."""

    def __init__(self, output_dir: Path | None = None, log_path: Path | None = None) -> None:
        self.settings = get_settings()
        self.orchestrator = Orchestrator(log_path=log_path)
        self.gemini = GeminiClient()
        
        # Set output directory — charts go into output_dir/charts
        self.output_dir = output_dir or Path(self.settings.output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        charts_dir = self.output_dir / "charts"
        charts_dir.mkdir(parents=True, exist_ok=True)

        # Data collectors
        self.market_collector = MarketDataCollector(fred_api_key=self.settings.fred_api_key)
        self.sec_collector = SECFilingCollector(user_agent=self.settings.sec_user_agent)
        self.search_client = SearchClient(api_key=self.settings.serper_api_key)

        # Agents
        self.data_collector_agent = DataCollectionAgent(
            orchestrator=self.orchestrator,
            market_collector=self.market_collector,
            sec_collector=self.sec_collector,
        )
        self.deep_search_agent = DeepSearchAgent(
            orchestrator=self.orchestrator,
            gemini_client=self.gemini,
            search_client=self.search_client,
        )

        # Chart generator — always writes to output_dir/charts/
        self.chart_generator = ChartGenerator(output_dir=charts_dir)

        # Parallel perspective runner
        self.perspective_runner = ParallelPerspectiveRunner(
            orchestrator=self.orchestrator,
            gemini_client=self.gemini,
            market_collector=self.market_collector,
            chart_generator=self.chart_generator,
        )

        # Enhanced report writer with CoA retrieval
        self.coa_retriever = CoARetriever(self.orchestrator)
        self.report_writer = EnhancedReportWriter(
            orchestrator=self.orchestrator,
            gemini_client=self.gemini,
            coa_retriever=self.coa_retriever,
        )

    def run(
        self,
        company_name: str,
        ticker: str,
        analysis_goal: str,
        fred_series_ids: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """Run enhanced pipeline synchronously. Timeout is enforced by the API layer."""
        artifacts: Dict[str, str] = {}

        # Stage 1: Data Collection
        collection_result = self.data_collector_agent.run(
            company_name=company_name,
            ticker=ticker,
            fred_series_ids=fred_series_ids,
        )
        artifacts.update(collection_result)

        # Stage 2: Deep Search
        search_result = self.deep_search_agent.run(f"{company_name} latest developments")
        artifacts.update(search_result)

        # Stage 3: Parallel Perspectives (6 perspectives running in parallel)
        perspective_result = self.perspective_runner.run_all(
            ticker=ticker,
            company_name=company_name,
        )
        artifacts.update(perspective_result)

        # Stage 4: Generate all 6 mandatory charts
        chart_result = self._generate_all_charts(ticker, fred_series_ids)
        artifacts.update(chart_result)

        # Stage 5: Generate comprehensive report (20,000+ words)
        report_result = self.report_writer.write(
            company_name=company_name,
            ticker=ticker,
            perspectives=perspective_result.get("perspectives", {}),
            charts=chart_result.get("charts", []),
        )
        artifacts.update(report_result)

        return artifacts

    def _generate_all_charts(
        self, ticker: str, fred_series_ids: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Generate all 6 mandatory charts."""
        fred_series = fred_series_ids.get("gdp", "GDP") if fred_series_ids else "GDP"
        
        charts = self.chart_generator.generate_all_charts(ticker, fred_series)
        
        # Store charts in variable space
        chart_uids = {}
        for chart in charts:
            uid = self.orchestrator.register_data(
                name=f"{ticker}_{chart['chart_id']}",
                value=chart,
                description=chart["description"],
                tags=["chart", chart["chart_id"]],
                source="chart_generator",
            )
            chart_uids[chart["chart_id"]] = uid

        return {"charts": charts, "chart_uids": chart_uids}

    def _get_partial_report(self, company_name: str, ticker: str) -> Dict[str, str]:
        """Return a minimal partial report when the pipeline times out or crashes."""
        from Finsight.tools.unified_llm_client import _template_fallback
        try:
            from Finsight.writing.enhanced_report_writer import fetch_live_data
            data = fetch_live_data(ticker)
        except Exception:
            data = {"ticker": ticker, "company_name": company_name}
        markdown = (
            f"# {company_name} ({ticker}) — Partial Report\n\n"
            "**Note:** Report generation was interrupted (5-minute timeout). "
            "Showing template-based summary.\n\n"
        )
        for section in [
            "Executive Summary", "Financial Analysis", "Risk Factors", "Investment Recommendation"
        ]:
            markdown += f"## {section}\n\n{_template_fallback(section, data)}\n\n---\n\n"
        return {"markdown": markdown, "word_count": str(len(markdown.split()))}

    def _save_report_to_file(self, company_name: str, ticker: str, report_markdown: str) -> None:
        """Save the generated report to a file."""
        import uuid

        job_id = str(uuid.uuid4())
        filename = f"{job_id}_{ticker}_report.md"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report_markdown)

        print(f"Report saved to: {filepath}")
        print(f"Word count: {len(report_markdown.split())}")
