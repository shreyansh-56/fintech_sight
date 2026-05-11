"""End-to-end FinSight pipeline orchestrator."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from Finsight.analysis.executor import AnalysisExecutor
from Finsight.agents.analysis_agent import DataAnalysisAgent
from Finsight.agents.data_collection import DataCollectionAgent
from Finsight.agents.deep_search import DeepSearchAgent
from Finsight.agents.report_agent import ReportGenerationAgent
from Finsight.config.settings import get_settings
from Finsight.runtime.orchestrator import Orchestrator
from Finsight.tools.data_collectors import MarketDataCollector, SECFilingCollector
from Finsight.tools.gemini_client import GeminiClient
from Finsight.tools.search import SearchClient
from Finsight.visualization.iterative import IterativeVisualizer
from Finsight.writing.chain_writer import ChainCompiler
from Finsight.writing.report_writer import ReportWriter


class FinSightPipeline:
    """High-level controller that wires together all FinSight components."""

    def __init__(self, log_path: Path | None = None) -> None:
        self.settings = get_settings()
        self.orchestrator = Orchestrator(log_path=log_path)
        self.gemini = GeminiClient()

        self.market_collector = MarketDataCollector(fred_api_key=self.settings.fred_api_key)
        self.sec_collector = SECFilingCollector(user_agent=self.settings.sec_user_agent)
        self.search_client = SearchClient(api_key=self.settings.serper_api_key)

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
        self.analysis_executor = AnalysisExecutor(self.orchestrator, self.gemini)
        self.chain_compiler = ChainCompiler(self.orchestrator, self.gemini)
        self.analysis_agent = DataAnalysisAgent(self.analysis_executor, self.chain_compiler)

        self.visualizer = IterativeVisualizer(self.orchestrator, self.gemini)
        self.report_writer = ReportWriter(self.orchestrator, self.gemini)
        self.report_agent = ReportGenerationAgent(
            orchestrator=self.orchestrator,
            report_writer=self.report_writer,
            visualizer=self.visualizer,
        )

    def run(  # noqa: PLR0913
        self,
        company_name: str,
        ticker: str,
        analysis_goal: str,
        fred_series_ids: Optional[Dict[str, str]] = None,
        visualization_spec: Optional[Dict[str, str]] = None,
        visualization_goal: Optional[str] = None,
        report_outline: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        artifacts: Dict[str, str] = {}

        collection_result = self.data_collector_agent.run(
            company_name=company_name,
            ticker=ticker,
            fred_series_ids=fred_series_ids,
        )
        artifacts.update(collection_result)

        search_result = self.deep_search_agent.run(f"{company_name} latest developments")
        artifacts.update(search_result)

        analysis_result = self.analysis_agent.run(analysis_goal=analysis_goal)
        chain = analysis_result.pop("chain")
        analysis_logs = analysis_result.pop("analysis_logs", [])

        chain_uid = self.orchestrator.register_data(
            name="analysis_chain_steps",
            value=chain.to_dict(),
            description="Ordered chain-of-analysis steps",
            tags=["analysis", "chain"],
            source="data_analysis_agent",
        )
        artifacts["analysis_chain_uid"] = chain_uid

        if analysis_logs:
            logs_uid = self.orchestrator.register_data(
                name="analysis_reasoning_logs",
                value=analysis_logs,
                description="Prompts and plans used during analysis execution",
                tags=["analysis", "logs"],
                source="data_analysis_agent",
            )
            artifacts["analysis_logs_uid"] = logs_uid

        artifacts.update(analysis_result)

        if visualization_spec and visualization_goal:
            report_artifacts = self.report_agent.run(
                research_question=analysis_goal,
                perspectives=analysis_result.get("perspectives", []),
                stock_history_uid=collection_result.get("stock_history_uid"),
                visualization_spec=visualization_spec,
                visualization_goal=visualization_goal,
                outline=report_outline,
            )
        else:
            report_artifacts = self.report_agent.run(
                research_question=analysis_goal,
                perspectives=analysis_result.get("perspectives", []),
                outline=report_outline,
            )

        artifacts.update(report_artifacts)

        return artifacts
