"""Analysis REPL executor for FinSight."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from Finsight.analysis.chain import ChainOfAnalysis, ChainStep
from Finsight.runtime.orchestrator import Orchestrator
from Finsight.tools.gemini_client import GeminiClient


class AnalysisExecutor:
    """Runs iterative analysis steps using the CAVM orchestrator."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        gemini_client: GeminiClient,
    ) -> None:
        self.orchestrator = orchestrator
        self.gemini = gemini_client

    def run(
        self,
        analysis_goal: str,
        max_steps: int = 5,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[ChainOfAnalysis, List[Dict[str, Any]]]:
        chain = ChainOfAnalysis()
        step_logs: List[Dict[str, Any]] = []

        prompt = (
            "You are the FinSight analysis agent operating in a code-first environment.\n"
            "Given the current variable memory snapshot, propose Python code that advances the analysis goal.\n"
            f"Analysis goal: {analysis_goal}\n"
            "Return JSON with fields: focus (str), code (python code string), commentary (list of insights), evidence (list of variable names)."
        )

        snapshot = self.orchestrator.variable_space.snapshot()
        prompt_with_context = f"{prompt}\nCurrent memory: {snapshot}"  # intentionally raw; further formatting later

        for step_id in range(1, max_steps + 1):
            plan = self.gemini.generate_structured(prompt_with_context)
            focus = plan.get("focus", f"Step {step_id}")
            code = plan.get("code", "")
            insights = plan.get("commentary", [])
            evidence = plan.get("evidence", [])

            execution_result = self.orchestrator.execute_agent_code(code, context=context)

            chain_step = ChainStep(
                step_id=step_id,
                focus=focus,
                code=code,
                stdout=execution_result.stdout,
                stderr=execution_result.stderr,
                success=execution_result.success,
            )

            for insight in insights:
                chain_step.add_insight(insight)
            for evidence_name in evidence:
                matches = self.orchestrator.variable_space.find_by_name(evidence_name)
                for match in matches:
                    chain_step.add_evidence(match.uid)

            chain.add_step(chain_step)

            step_logs.append(
                {
                    "step_id": step_id,
                    "prompt": prompt_with_context,
                    "plan": plan,
                    "stdout": execution_result.stdout,
                    "stderr": execution_result.stderr,
                    "success": execution_result.success,
                }
            )

            if not execution_result.success:
                break

            snapshot = self.orchestrator.variable_space.snapshot()
            prompt_with_context = (
                f"{prompt}\nCurrent memory: {snapshot}\n"
                f"Previous step stdout: {execution_result.stdout}\n"
                f"Previous insights: {insights}"
            )

        return chain, step_logs
