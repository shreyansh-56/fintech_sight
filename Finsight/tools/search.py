"""Search utilities for FinSight data collection using Serper API."""
from __future__ import annotations

from typing import Any, Dict, List

import requests


class SearchClient:
    """Performs web/news searches using Serper API (Google Search)."""

    SEARCH_ENDPOINT = "https://google.serper.dev/search"
    NEWS_ENDPOINT = "https://google.serper.dev/news"

    def __init__(self, api_key: str, timeout: float = 15.0) -> None:
        if not api_key:
            raise ValueError("Serper API key must be provided for SearchClient")
        self.api_key = api_key
        self.timeout = timeout

    def _request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }
        response = requests.post(endpoint, headers=headers, json=payload, timeout=self.timeout)
        if response.status_code != 200:
            raise RuntimeError(f"Serper API error {response.status_code}: {response.text}")
        return response.json()

    def search_news(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        payload = {"q": query, "num": max_results}
        data = self._request(self.NEWS_ENDPOINT, payload)
        return data.get("news", [])[:max_results]

    def search_text(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        payload = {"q": query, "num": max_results}
        data = self._request(self.SEARCH_ENDPOINT, payload)
        return data.get("organic", [])[:max_results]
