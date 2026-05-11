"""Utilities to score a completed FinSight pipeline run using evaluation metrics."""
from __future__ import annotations

from typing import Dict, List, Optional

from Finsight.evaluation import metrics
from Finsight.pipeline.orchestrator import FinSightPipeline


def evaluate_pipeline_run(
    pipeline: FinSightPipeline,
    artifacts: Dict[str, str],
    reference_conclusions: Optional[List[str]] = None,
    key_points: Optional[List[str]] = None,
) -> Dict[str, Dict[str, float]]:
    """Compute FinSight-style metrics for a pipeline run."""

    variable_space = pipeline.orchestrator.variable_space

    memo_uid = artifacts.get("memo_uid")
    if not memo_uid:
        raise ValueError("memo_uid missing from artifacts; cannot evaluate run")
    memo_payload = variable_space.get(memo_uid).value
    memo_text = memo_payload.get("markdown") if isinstance(memo_payload, dict) else str(memo_payload)

    perspectives_uid = artifacts.get("perspectives_uid")
    perspectives = []
    evidence_uids: List[str] = []
    if perspectives_uid:
        perspectives_payload = variable_space.get(perspectives_uid).value
        if isinstance(perspectives_payload, list):
            perspectives = perspectives_payload
            for perspective in perspectives:
                evidence_uids.extend(perspective.get("evidence_uids", []))

    viz_uid = artifacts.get("visualization_uid")
    viz_iterations: List[Dict[str, str]] = []
    if viz_uid:
        viz_payload = variable_space.get(viz_uid).value
        viz_iterations = viz_payload.get("iterations", []) if isinstance(viz_payload, dict) else []

    reference_conclusions = reference_conclusions or []
    key_points = key_points or []

    factual = {
        "core_conclusion_consistency": metrics.core_conclusion_consistency(memo_text, reference_conclusions),
        "textual_faithfulness": metrics.textual_faithfulness(memo_text, evidence_uids),
        "text_image_coherence": metrics.text_image_coherence(
            memo_text, [item.get("feedback", "") for item in viz_iterations]
        ),
    }

    information = {
        "information_richness": metrics.information_richness(perspectives),
        "coverage": metrics.coverage_score(perspectives, key_points),
        "analytical_insight": metrics.analytical_insight(perspectives),
    }

    presentation = {
        "structural_logic": metrics.structural_logic(memo_text),
        "language_professionalism": metrics.language_professionalism(memo_text),
        "chart_expressiveness": metrics.chart_expressiveness(viz_iterations),
    }

    return {
        "factual_accuracy": factual,
        "information_effectiveness": information,
        "presentation_quality": presentation,
        "factual_accuracy_score": metrics.aggregate_dimension(factual),
        "information_effectiveness_score": metrics.aggregate_dimension(information),
        "presentation_quality_score": metrics.aggregate_dimension(presentation),
    }
