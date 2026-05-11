"""Data analysis agent coordinating REPL execution and chain compilation."""
from __future__ import annotations

from typing import Any, Dict

from Finsight.analysis.executor import AnalysisExecutor
from Finsight.writing.chain_writer import ChainCompiler


class DataAnalysisAgent:
    """Wraps analysis executor and chain compiler as a single agent role."""

    def __init__(self, analysis_executor: AnalysisExecutor, chain_compiler: ChainCompiler) -> None:
        self.analysis_executor = analysis_executor
        self.chain_compiler = chain_compiler

    def run(self, analysis_goal: str) -> Dict[str, Any]:
        chain, step_logs = self.analysis_executor.run(analysis_goal=analysis_goal)
        result = self.chain_compiler.compile(chain, research_question=analysis_goal)
        return {"chain": chain, "analysis_logs": step_logs, **result}
