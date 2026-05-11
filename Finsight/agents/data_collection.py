"""Multi-source data collection agents for FinSight."""
from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from Finsight.interfaces.agent import Agent
from Finsight.runtime.orchestrator import Orchestrator
from Finsight.tools.data_collectors import (
    MarketDataCollector,
    SECFilingCollector,
    StructuredArtifact,
)


class DataCollectionAgent(Agent):
    """Collects heterogeneous financial data and stores it in the variable space."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        market_collector: MarketDataCollector,
        sec_collector: SECFilingCollector,
    ) -> None:
        super().__init__(name="multi_source_collector", description="Collects financial datasets")
        self.orchestrator = orchestrator
        self.market_collector = market_collector
        self.sec_collector = sec_collector

    def run(
        self,
        company_name: str,
        ticker: str,
        fred_series_ids: Optional[Dict[str, str]] = None,
        store_history_period: str = "2y",
    ) -> Dict[str, Any]:
        """Collect stock, macro, and filing data for the company."""

        artifacts: Dict[str, Any] = {}

        stock_df = self.market_collector.get_stock_history(ticker=ticker, period=store_history_period)
        stock_uid = self._store_dataframe(
            name=f"{ticker}_stock_history",
            df=stock_df,
            description=f"{ticker} historical prices ({store_history_period})",
            tags=["market", "price", ticker],
        )
        artifacts["stock_history_uid"] = stock_uid

        if fred_series_ids:
            macro_uids = {}
            for label, series_id in fred_series_ids.items():
                series = self.market_collector.get_fred_series(series_id)
                macro_df = series.to_frame(name=label)
                uid = self._store_dataframe(
                    name=f"fred_{label}",
                    df=macro_df,
                    description=f"FRED series {series_id} for {label}",
                    tags=["macro", "fred", series_id],
                )
                macro_uids[label] = uid
            artifacts["macro_series_uids"] = macro_uids

        filing_text = self.sec_collector.get_latest_10k(ticker)
        filing_artifact = StructuredArtifact(
            name=f"{ticker}_10k_excerpt",
            content=filing_text,
            metadata={"ticker": ticker, "company_name": company_name, "type": "10-K"},
        )
        filing_uid = self._store_text_artifact(filing_artifact)
        artifacts["sec_filing_uid"] = filing_uid

        return artifacts

    def _store_dataframe(
        self,
        name: str,
        df: pd.DataFrame,
        description: str,
        tags: Optional[list[str]] = None,
    ) -> str:
        payload = {
            "dataframe": df,
            "shape": df.shape,
            "columns": list(df.columns),
        }
        return self.orchestrator.register_data(
            name=name,
            value=payload,
            description=description,
            tags=tags,
            source="data_collection_agent",
        )

    def _store_text_artifact(self, artifact: StructuredArtifact) -> str:
        return self.orchestrator.register_data(
            name=artifact.name,
            value=artifact.content,
            description="SEC filing snippet",
            tags=["sec", "filing"],
            source="sec_edgar_api",
        )
