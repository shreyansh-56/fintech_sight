"""Stage 1: Chain-of-Analysis compilation."""
from __future__ import annotations

from typing import Any, Dict, List

from Finsight.analysis.chain import ChainOfAnalysis
from Finsight.runtime.orchestrator import Orchestrator
from Finsight.tools.gemini_client import GeminiClient


class ChainCompiler:
    """Compiles raw chain steps into structured perspectives via Gemini."""

    def __init__(self, orchestrator: Orchestrator, gemini_client: GeminiClient) -> None:
        self.orchestrator = orchestrator
        self.gemini = gemini_client

    def compile(self, chain: ChainOfAnalysis, research_question: str) -> Dict[str, Any]:
        chain_dict = chain.to_dict()
        snapshot = self.orchestrator.variable_space.snapshot()

        prompt = (
            "You are the FinSight Chain-of-Analysis compiler.\n"
            "Given the raw analytical steps, produce structured perspectives.\n"
            "Respond with JSON containing: perspectives (list of {id, focus, narrative, evidence_uids, referenced_variables})\n"
            "Ensure evidence_uids align with provided chain entries and variable snapshot.\n"
            f"Research Question: {research_question}\n"
            f"Chain Steps: {chain_dict}\n"
            f"Variable Snapshot: {snapshot}\n"
        )

        result = self.gemini.generate_structured(prompt)

        if isinstance(result, list):
            perspectives = result
        else:
            perspectives = result.get("perspectives", [])

        enriched_perspectives = []

        for perspective in perspectives:
            perspective_id = perspective.get("id") or f"P-{len(enriched_perspectives)+1}"
            evidence_uids = perspective.get("evidence_uids", [])

            resolved_variables = []
            for uid in evidence_uids:
                try:
                    variable = self.orchestrator.variable_space.get(uid)
                    resolved_variables.append(
                        {
                            "uid": uid,
                            "name": variable.metadata.name,
                            "type": variable.metadata.type,
                            "description": variable.metadata.description,
                        }
                    )
                except KeyError:
                    resolved_variables.append({"uid": uid, "name": "UNKNOWN", "type": "unknown"})

            enriched_perspectives.append(
                {
                    "id": perspective_id,
                    "focus": perspective.get("focus"),
                    "narrative": perspective.get("narrative"),
                    "evidence_uids": evidence_uids,
                    "resolved_variables": resolved_variables,
                }
            )

        uid = self.orchestrator.register_data(
            name="chain_of_analysis_perspectives",
            value=enriched_perspectives,
            description="Structured perspectives from chain-of-analysis",
            tags=["chain_of_analysis"],
            source="chain_compiler",
        )

        return {"perspectives": enriched_perspectives, "perspectives_uid": uid}
