"""Deep search agent using Gemini to iteratively explore web results."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from Finsight.interfaces.agent import Agent
from Finsight.runtime.orchestrator import Orchestrator
from Finsight.tools.gemini_client import GeminiClient
from Finsight.tools.search import SearchClient


class DeepSearchAgent(Agent):
    """Iterative search agent that gathers contextual snippets."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        gemini_client: GeminiClient,
        search_client: SearchClient,
        max_iterations: int = 3,
    ) -> None:
        super().__init__(name="deep_search_agent", description="Iterative web search via Gemini")
        self.orchestrator = orchestrator
        self.gemini = gemini_client
        self.search_client = search_client
        self.max_iterations = max_iterations

    def run(self, query: str) -> Dict[str, Any]:
        itinerary: List[Dict[str, Any]] = []
        context_snippets: List[str] = []
        current_query = query
        all_urls: List[str] = []

        for iteration in range(self.max_iterations):
            news_results = self.search_client.search_news(current_query, max_results=5)
            text_results = self.search_client.search_text(current_query, max_results=5)

            step_record = {
                "iteration": iteration + 1,
                "query": current_query,
                "news_results": news_results,
                "text_results": text_results,
            }
            itinerary.append(step_record)

            combined_snippets = [item.get("body") or item.get("snippet") or "" for item in news_results + text_results]
            combined_snippets = [snippet for snippet in combined_snippets if snippet]
            context_snippets.extend(combined_snippets)

            # Collect URLs for citation purposes (Serper items use 'link')
            urls_iter = [
                u
                for u in [*(r.get("link") for r in news_results), *(r.get("link") for r in text_results)]
                if u
            ]
            all_urls.extend(urls_iter)

            guidance_prompt = (
                "You are assisting a financial analyst. Based on the following snippets, "
                "propose a refined search query or return DONE if enough context is gathered.\n"
                f"Current query: {current_query}\n"
                f"Snippets: {combined_snippets[:5]}"
            )
            guidance = self.gemini.generate(guidance_prompt)
            if "DONE" in guidance.upper():
                break
            current_query = guidance.strip()

        canonical_url = all_urls[0] if all_urls else None

        uid = self.orchestrator.register_data(
            name="deep_search_summary",
            value={
                "initial_query": query,
                "itinerary": itinerary,
                "snippets": context_snippets,
                "sources": all_urls[:20],
                "url": canonical_url,
            },
            description="Deep search exploration results",
            tags=["search", "web"],
            source="deep_search_agent",
        )

        return {"deep_search_uid": uid, "iterations": len(itinerary)}
