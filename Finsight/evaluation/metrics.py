"""Automated evaluation metrics approximating those in the FinSight paper."""
from __future__ import annotations

import math
import re
from statistics import mean
from typing import Dict, List


_CITATION_PATTERN = re.compile(r"\[Ref:\s*([^\]]+)\]")


def _round(score: float) -> float:
    return round(max(0.0, min(10.0, score)), 1)


def core_conclusion_consistency(memo: str, reference_conclusions: List[str]) -> float:
    """Score whether the memo reinforces the core conclusions (0-10)."""
    if not reference_conclusions:
        return 8.0 if memo.strip() else 0.0
    hits = sum(1 for conclusion in reference_conclusions if conclusion.lower() in memo.lower())
    ratio = hits / len(reference_conclusions)
    return _round(ratio * 10)


def textual_faithfulness(memo: str, evidence_uids: List[str]) -> float:
    """Reward coverage of evidence items with diminishing returns (0-10)."""
    if not memo.strip():
        return 0.0

    cited_uids = [match.group(1).strip() for match in _CITATION_PATTERN.finditer(memo)]
    unique_cited = set(cited_uids)
    if not unique_cited:
        return 1.0

    evidence_set = set(evidence_uids)
    matched_evidence = unique_cited & evidence_set

    if not evidence_set:
        # When we have no evidence list, treat unique citations as partial credit.
        coverage_ratio = min(1.0, len(unique_cited) / 8)
        return _round(coverage_ratio * 7)

    coverage_ratio = len(matched_evidence) / len(evidence_set)

    # Penalize heavy reuse of the same source: duplicates beyond first count as noise.
    duplicate_citations = sum(max(0, cited_uids.count(uid) - 1) for uid in matched_evidence)
    reuse_penalty = min(0.4, duplicate_citations / 10)

    # Reward detailed citation usage but cap to temper runaway scores.
    total_mentions = sum(cited_uids.count(uid) for uid in matched_evidence)
    depth_bonus = min(0.3, total_mentions / (len(evidence_set) * 4))

    score = (coverage_ratio * 9) + (depth_bonus * 10) - (reuse_penalty * 10)
    if len(matched_evidence) == 0:
        score = min(score, 3.0)
    return _round(score)


def text_image_coherence(_: str, viz_feedback: List[str]) -> float:
    """Score alignment of memo with charts. Penalise repeated REVISE feedback (0-10)."""
    if not viz_feedback:
        return 5.0  # neutral when no chart generated
    revise = sum(1 for feedback in viz_feedback if feedback.upper().startswith("REVISE"))
    approved = any(feedback.upper().startswith("APPROVED") for feedback in viz_feedback)
    score = 10 - (3 * revise)
    if approved and score < 8:
        score = 8
    return _round(score)


def information_richness(perspectives: List[Dict[str, any]]) -> float:
    distinct_focus = {p.get("focus") for p in perspectives if p.get("focus")}
    if not distinct_focus:
        return 3.0 if perspectives else 0.0
    diversity_ratio = min(1.0, len(distinct_focus) / 5)
    return _round(diversity_ratio * 10)


def coverage_score(perspectives: List[Dict[str, any]], key_points: List[str]) -> float:
    if not key_points:
        return 7.0 if perspectives else 0.0
    narrative_text = "\n".join(p.get("narrative", "") for p in perspectives)
    hits = sum(1 for point in key_points if point.lower() in narrative_text.lower())
    return _round((hits / len(key_points)) * 10)


def analytical_insight(perspectives: List[Dict[str, any]]) -> float:
    token_count = sum(len(p.get("narrative", "").split()) for p in perspectives)
    if not token_count:
        return 0.0
    # 800+ tokens of analysis earns full marks
    ratio = min(1.0, token_count / 800)
    return _round(ratio * 10)


def structural_logic(memo: str) -> float:
    sections = [line for line in memo.splitlines() if line.startswith("#")]
    if not sections:
        return 2.0 if memo.strip() else 0.0
    ratio = min(1.0, len(sections) / 6)
    return _round(ratio * 10)


def language_professionalism(memo: str) -> float:
    if not memo.strip():
        return 0.0
    jargon = {
        "ebitda",
        "yoy",
        "guidance",
        "valuation",
        "margin",
        "liquidity",
        "free cash flow",
        "run-rate",
        "operating leverage",
        "capital allocation",
    }
    memo_lower = memo.lower()
    hits = sum(1 for term in jargon if term in memo_lower)
    richness_bonus = min(0.3, len(memo.split()) / 2000)
    return _round(min(1.0, hits / 5 + richness_bonus) * 10)


def chart_expressiveness(iterations: List[Dict[str, str]]) -> float:
    if not iterations:
        return 0.0
    revise = sum(1 for item in iterations if item.get("feedback", "").upper().startswith("REVISE"))
    approved = any(item.get("feedback", "").upper().startswith("APPROVED") for item in iterations)
    if approved:
        return 10.0
    return _round(max(2.0, 10 - 3 * revise))


def aggregate_dimension(scores: Dict[str, float]) -> float:
    if not scores:
        return 0.0
    return _round(mean(scores.values()))
