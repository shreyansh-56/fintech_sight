"""Report generation agent orchestrating visualization refinement and final memo."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from Finsight.runtime.orchestrator import Orchestrator
from Finsight.visualization.iterative import IterativeVisualizer
from Finsight.writing.report_writer import ReportWriter


class ReportGenerationAgent:
    """Coordinated agent for producing visualizations and final memo."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        report_writer: ReportWriter,
        visualizer: Optional[IterativeVisualizer] = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.report_writer = report_writer
        self.visualizer = visualizer

    def run(
        self,
        research_question: str,
        perspectives: List[Dict[str, Any]],
        stock_history_uid: Optional[str] = None,
        visualization_spec: Optional[Dict[str, Any]] = None,
        visualization_goal: Optional[str] = None,
        outline: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        artifacts: Dict[str, Any] = {}

        if (
            self.visualizer
            and stock_history_uid
            and visualization_spec is not None
            and visualization_goal is not None
        ):
            viz_result = self.visualizer.run(
                dataframe_uid=stock_history_uid,
                spec=visualization_spec,
                goal=visualization_goal,
            )
            artifacts.update(viz_result)
            visualization_uid = viz_result.get("visualization_uid")
        else:
            visualization_uid = None

        memo_result = self.report_writer.write(
            research_question=research_question,
            perspectives=perspectives,
            outline=outline,
            visualization_uid=visualization_uid,
        )
        artifacts.update(memo_result)

        return artifacts
