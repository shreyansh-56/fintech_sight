"""Utilities to resolve stock tickers from company names.

Uses SEC's public company_tickers.json mapping to find the ticker for a given
company name. Falls back to fuzzy-ish matching rules (case-insensitive exact,
normalized exact, startswith, and substring) and returns the first best match.
"""
from __future__ import annotations

from typing import Dict, Any, Optional, Tuple
import re
import requests

from Finsight.config.settings import get_settings

SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


def _normalize(name: str) -> str:
    name = name.lower().strip()
    # Remove common suffixes and punctuation
    name = re.sub(r"[.,'\-]", " ", name)
    name = re.sub(r"\b(incorporated|inc|corp|corporation|co|company|ltd|plc|llc|s\.a\.|s\.a|ag|nv)\b", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def resolve_ticker(company_name: str, user_agent: Optional[str] = None) -> str:
    """Resolve a stock ticker from a human-entered company name.

    Parameters
    - company_name: input company name (e.g., "NVIDIA", "Apple Inc.")
    - user_agent: SEC requires a descriptive User-Agent. If None, use settings.

    Returns: ticker symbol string (e.g., "NVDA"). Raises RuntimeError if not found.
    """
    if not company_name or not company_name.strip():
        raise RuntimeError("Company name is required to resolve ticker")

    settings = get_settings()
    ua = user_agent or settings.sec_user_agent

    resp = requests.get(SEC_COMPANY_TICKERS_URL, headers={"User-Agent": ua}, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError("Failed to download SEC company tickers mapping")

    mapping: Dict[str, Any] = resp.json()

    target_raw = company_name.strip()
    target_norm = _normalize(target_raw)

    exact: Optional[Tuple[str, Dict[str, Any]]] = None
    norm_exact: Optional[Tuple[str, Dict[str, Any]]] = None
    starts: Optional[Tuple[str, Dict[str, Any]]] = None
    contains: Optional[Tuple[str, Dict[str, Any]]] = None

    for entry in mapping.values():
        title = str(entry.get("title", ""))
        ticker = str(entry.get("ticker", "")).upper()
        if not ticker or not title:
            continue
        if title.strip().lower() == target_raw.strip().lower():
            exact = (ticker, entry)
            break
        tnorm = _normalize(title)
        if tnorm == target_norm and norm_exact is None:
            norm_exact = (ticker, entry)
        if tnorm.startswith(target_norm) and starts is None:
            starts = (ticker, entry)
        if target_norm in tnorm and contains is None:
            contains = (ticker, entry)

    for candidate in (exact, norm_exact, starts, contains):
        if candidate:
            return candidate[0]

    raise RuntimeError(f"Could not resolve ticker for company '{company_name}' from SEC mapping")
