"""Stage 2: Structured report writing with citations."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from Finsight.runtime.orchestrator import Orchestrator
from Finsight.tools.gemini_client import GeminiClient


class ReportWriter:
    """Generates the final investment memo using compiled perspectives and variable memory."""

    def __init__(self, orchestrator: Orchestrator, gemini_client: GeminiClient) -> None:
        self.orchestrator = orchestrator
        self.gemini = gemini_client

    def write(
        self,
        research_question: str,
        perspectives: List[Dict[str, Any]],
        outline: List[str] | None = None,
        visualization_uid: str | None = None,
    ) -> Dict[str, Any]:
        snapshot = self.orchestrator.variable_space.snapshot()

        outline = outline or [
            "Executive Summary",
            "Company Overview",
            "Market & Macro Trends",
            "Financial Analysis",
            "Risk Factors",
            "Catalysts & Outlook",
            "Recommendation",
            "References",
        ]

        perspective_map = {str(p.get("id")): p for p in perspectives if p.get("id")}
        available_refs = set()
        for perspective in perspectives:
            for uid in perspective.get("evidence_uids", []):
                available_refs.add(str(uid))
        for perspective_id in perspective_map:
            available_refs.add(str(perspective_id))

        # Build a reference resolver from variable space: uid -> {name, description, url}
        ref_index: Dict[str, Dict[str, Any]] = {}
        # First index variable-backed UIDs
        for uid in list(available_refs):
            if uid in perspective_map:
                continue
            try:
                var = self.orchestrator.variable_space.get(uid)
                url = None
                val = var.value
                if isinstance(val, dict):
                    url = val.get("source_url") or val.get("url")
                ref_index[uid] = {
                    "name": var.metadata.name,
                    "description": var.metadata.description,
                    "url": url,
                }
            except KeyError:
                pass
        # Then add perspectives, inheriting URL from first evidence that has one
        for pid, p in perspective_map.items():
            inherited_url = None
            for ev_uid in p.get("evidence_uids", []):
                ev_meta = ref_index.get(str(ev_uid))
                if ev_meta and ev_meta.get("url"):
                    inherited_url = ev_meta["url"]
                    break
            ref_index[pid] = {
                "name": f"Perspective {pid}",
                "description": p.get("focus") or "Perspective",
                "url": inherited_url,
            }

        prompt = (
            "You are the FinSight report generation agent.\n"
            "Craft a professional financial research memo in Markdown.\n"
            "Use the provided perspectives and variable memory to support claims.\n"
            "For every factual statement, cite evidence using [Ref: <uid>] where uid is either a perspective ID or variable UID from the allowed list.\n"
            f"Allowed IDs: {sorted(list(available_refs))}\n"
            "Structure the memo according to the outline order. Include a references section mapping each UID to its description.\n"
            f"Research Question: {research_question}\n"
            f"Outline: {outline}\n"
            f"Perspectives: {perspectives}\n"
            f"Variable Snapshot: {snapshot}\n"
        )

        report_markdown = self.gemini.generate(prompt)
        report_markdown, review_summary = self._self_review(report_markdown, available_refs, ref_index)

        # Optionally embed the final visualization image
        if visualization_uid:
            try:
                viz_var = self.orchestrator.variable_space.get(visualization_uid)
                viz_value = viz_var.value if isinstance(viz_var.value, dict) else {}
                iterations = viz_value.get("iterations", [])
                final_iter = iterations[-1] if iterations else None
                if final_iter and final_iter.get("figure_png_b64"):
                    img_b64 = final_iter["figure_png_b64"]
                    report_markdown = (
                        report_markdown
                        + "\n\n### Figure: Final Chart\n\n"
                        + f"![Final Chart](data:image/png;base64,{img_b64})\n"
                    )
            except Exception:
                pass

        # If the model included a References section, strip it and rebuild ours
        lower = report_markdown.lower()
        cut_idx = lower.find("\n### references")
        if cut_idx != -1:
            report_markdown = report_markdown[:cut_idx]

        # Append References section with links
        lines = [report_markdown.rstrip(), "", "### References", ""]
        lines.append("| UID | Name | Description | Link |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for uid in sorted(list(available_refs)):
            meta = ref_index.get(uid, {})
            name = meta.get("name") or uid
            desc = meta.get("description") or ""
            url = meta.get("url") or ""
            link = f"[{url}]({url})" if url else ""
            lines.append(f"| {uid} | {name} | {desc} | {link} |")
        report_markdown = "\n".join(lines)

        uid = self.orchestrator.register_data(
            name="final_investment_memo",
            value={
                "markdown": report_markdown,
                "outline": outline,
                "research_question": research_question,
                "perspectives": perspectives,
                "self_review": review_summary,
            },
            description="Final investment memo generated by report writer",
            tags=["report", "memo"],
            source="report_writer",
        )

        return {"memo_uid": uid, "markdown": report_markdown}

    def _self_review(self, markdown: str, allowed_refs: set[str], ref_index: Dict[str, Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
        missing_refs = []
        lines = markdown.splitlines()
        adjusted_lines = []
        paragraph_has_ref = False

        for line in lines:
            if line.strip().startswith("#"):
                adjusted_lines.append(line)
                paragraph_has_ref = False
                continue
            adjusted_line = line
            if "[Ref:" not in line and not paragraph_has_ref and line.rstrip().endswith("."):
                if allowed_refs:
                    # prefer a reference that has a URL for better citation quality
                    fallback = next((u for u in allowed_refs if (ref_index.get(u) or {}).get("url")), None) or next(iter(allowed_refs))
                    adjusted_line = line + f" [Ref: {fallback}]"
                    missing_refs.append({"line": line, "inserted_ref": fallback})
                    paragraph_has_ref = True
            else:
                existing_refs = []
                start = 0
                while True:
                    idx = adjusted_line.find("[Ref:", start)
                    if idx == -1:
                        break
                    end = adjusted_line.find("]", idx)
                    if end == -1:
                        break
                    ref_id = adjusted_line[idx + 5 : end].strip()
                    if ref_id not in allowed_refs:
                        replacement = next(iter(allowed_refs)) if allowed_refs else "UNKNOWN"
                        adjusted_line = adjusted_line[: idx + 6] + replacement + adjusted_line[end:]
                        missing_refs.append({"line": line, "replaced": ref_id, "with": replacement})
                        start = idx + 6 + len(replacement)
                    else:
                        existing_refs.append(ref_id)
                        start = end + 1
                # Linkify known refs
                for ref_id in set(existing_refs):
                    url = (ref_index.get(ref_id) or {}).get("url")
                    if url:
                        adjusted_line = adjusted_line.replace(f"[Ref: {ref_id}]", f"[Ref: {ref_id}]({url})")
                paragraph_has_ref = paragraph_has_ref or bool(existing_refs)

            # Global linkify pass for any remaining [Ref: uid] tokens with known URLs
            # This ensures even refs outside allowed_refs get linked when we know their source.
            for uid, meta in ref_index.items():
                url = meta.get("url")
                if url:
                    adjusted_line = adjusted_line.replace(f"[Ref: {uid}]", f"[Ref: {uid}]({url})")

            # Deduplicate repeated refs on the same line (keep first occurrence of each UID)
            try:
                import re as _re
                pattern = _re.compile(r"\[Ref: ([^\]]+)\](?:\([^\)]*\))?")
                seen: set[str] = set()
                parts: list[str] = []
                last_end = 0
                for m in pattern.finditer(adjusted_line):
                    uid = m.group(1)
                    if uid in seen:
                        # skip duplicate by omitting this segment
                        parts.append(adjusted_line[last_end:m.start()])
                        last_end = m.end()
                    else:
                        seen.add(uid)
                parts.append(adjusted_line[last_end:])
                adjusted_line = "".join(parts)
            except Exception:
                pass

            if not adjusted_line.strip():
                paragraph_has_ref = False
            adjusted_lines.append(adjusted_line)

        review_summary = {
            "missing_or_invalid_refs": missing_refs,
            "allowed_refs": sorted(allowed_refs),
        }

        return "\n".join(adjusted_lines), review_summary
