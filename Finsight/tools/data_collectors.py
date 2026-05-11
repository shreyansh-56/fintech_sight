"""Data collection tools for FinSight."""
from __future__ import annotations

import json
import re
from typing import Any, Dict

import pandas as pd
import yfinance as yf
import requests
from fredapi import Fred


def clean_xbrl_tags(text: str) -> str:
    """Remove XBRL internal tags and clean up SEC filing text."""
    # Remove internal XBRL member names
    text = re.sub(r'\b\w+Member\b', '', text)
    text = re.sub(r'\b\w+Axis\b', '', text)
    text = re.sub(r'\b\w+Domain\b', '', text)
    # Clean UUID citations
    text = re.sub(r'Ref:\s*[a-f0-9-]{36}', '', text)
    # Remove other XBRL artifacts
    text = re.sub(r'\b\w+:Member\b', '', text)
    text = re.sub(r'\b\w+:Axis\b', '', text)
    # Clean up multiple whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

class MarketDataCollector:
    """Fetches market and macro data from yfinance and FRED."""

    def __init__(self, fred_api_key: str) -> None:
        if not fred_api_key:
            raise ValueError("FRED API key must be provided for MarketDataCollector")
        self.fred = Fred(api_key=fred_api_key)

    def get_stock_history(self, ticker: str, period: str = "2y") -> pd.DataFrame:
        data = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if data.empty:
            raise RuntimeError(f"No market data returned for {ticker}")
        return data

    def get_fred_series(self, series_id: str) -> pd.Series:
        series = self.fred.get_series(series_id)
        if series is None or series.empty:
            raise RuntimeError(f"No FRED data for series {series_id}")
        return series


class SECFilingCollector:
    """Retrieves SEC filings for a given ticker using direct requests."""

    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent
        self._ticker_cache: Dict[str, str] = {}

    def _lookup_cik(self, ticker: str) -> str:
        ticker = ticker.upper()
        if ticker in self._ticker_cache:
            return self._ticker_cache[ticker]

        url = "https://www.sec.gov/files/company_tickers.json"
        response = requests.get(url, headers={"User-Agent": self.user_agent}, timeout=30)
        if response.status_code != 200:
            raise RuntimeError("Failed to download SEC company tickers mapping")

        mapping: Dict[str, Any] = response.json()
        for entry in mapping.values():
            if entry.get("ticker", "").upper() == ticker:
                cik = str(entry.get("cik_str", "")).strip().zfill(10)
                self._ticker_cache[ticker] = cik
                return cik

        raise RuntimeError(f"Ticker {ticker} not found in SEC company ticker list")

    def get_latest_10k(self, ticker: str, truncate: int = 100000) -> Dict[str, Any]:
        """Get latest 10-K filing with error recovery chain."""
        
        # Try 1: SEC EDGAR direct request
        try:
            cik = self._lookup_cik(ticker)
            url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            response = requests.get(url, headers={"User-Agent": self.user_agent}, timeout=30)
            if response.status_code == 200:
                data = response.json()
                filings = data.get("filings", {}).get("recent", {})
                forms = filings.get("form", [])
                accession_numbers = filings.get("accessionNumber", [])
                primary_docs = filings.get("primaryDocument", [])

                target_index = None
                for idx, form in enumerate(forms):
                    if form == "10-K":
                        target_index = idx
                        break

                if target_index is not None:
                    accession = accession_numbers[target_index]
                    primary_doc = primary_docs[target_index]
                    if accession and primary_doc:
                        accession_path = accession.replace("-", "")
                        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_path}/{primary_doc}"
                        response = requests.get(url, headers={"User-Agent": self.user_agent}, timeout=30)
                        if response.status_code == 200:
                            content = clean_xbrl_tags(response.text)
                            return {"text": content[:truncate], "source_url": url}
        except Exception:
            pass

        # Try 2: yfinance financials
        try:
            stock = yf.Ticker(ticker)
            financials = stock.financials
            if not financials.empty:
                content = f"Financial data from yfinance for {ticker}:\n\n"
                content += financials.to_string()
                return {"text": clean_xbrl_tags(content)[:truncate], "source_url": f"https://finance.yahoo.com/quote/{ticker}/financials"}
        except Exception:
            pass

        # Try 3: Serper web search for financial data
        try:
            from tools.search import SearchClient
            search_client = SearchClient(api_key="")
            results = search_client.search_text(f"{ticker} 10-K annual report", max_results=3)
            if results:
                content = f"Financial data found via web search for {ticker}:\n\n"
                for result in results[:2]:
                    content += f"Source: {result.get('link', 'N/A')}\n"
                    content += f"{result.get('snippet', result.get('title', ''))}\n\n"
                return {"text": clean_xbrl_tags(content)[:truncate], "source_url": results[0].get('link', '')}
        except Exception:
            pass

        # Try 4: Return unavailable message
        return {
            "text": f"SEC 10-K filing data for {ticker} is temporarily unavailable. Please check the company's investor relations website or SEC EDGAR directly.",
            "source_url": f"https://www.sec.gov/edgar/search/"
        }


class StructuredArtifact:
    """Helper for storing collected artifacts with metadata."""

    def __init__(self, name: str, content: Any, metadata: Dict[str, Any] | None = None) -> None:
        self.name = name
        self.content = content
        self.metadata = metadata or {}

    def to_variable_payload(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "content": self.content,
            "metadata": self.metadata,
        }
