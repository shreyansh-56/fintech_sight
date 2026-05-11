"""Tests for the DataCollectionAgent."""
from __future__ import annotations

import pandas as pd

from Finsight.agents.data_collection import DataCollectionAgent
from Finsight.runtime.orchestrator import Orchestrator


class FakeMarketCollector:
    def get_stock_history(self, ticker: str, period: str = "2y"):
        data = {
            "Close": [100.0, 101.5],
            "Volume": [1000, 1500],
        }
        index = pd.to_datetime(["2023-01-01", "2023-01-02"])
        return pd.DataFrame(data, index=index)

    def get_fred_series(self, series_id: str):
        series = pd.Series([1.0, 2.0], index=pd.to_datetime(["2023-01-01", "2023-02-01"]))
        series.name = series_id
        return series


class FakeSECFilingCollector:
    def get_latest_10k(self, ticker: str, truncate: int = 100000) -> str:
        return "Sample SEC 10-K content"


def test_data_collection_agent_registers_artifacts():
    orchestrator = Orchestrator()
    market = FakeMarketCollector()
    sec = FakeSECFilingCollector()

    agent = DataCollectionAgent(orchestrator, market, sec)

    result = agent.run(
        company_name="Sample Corp",
        ticker="SAMPLE",
        fred_series_ids={"gdp": "GDP"},
        store_history_period="2d",
    )

    snapshot = orchestrator.variable_space.snapshot()

    assert "stock_history_uid" in result
    assert result["stock_history_uid"] in snapshot

    assert "macro_series_uids" in result
    for uid in result["macro_series_uids"].values():
        assert uid in snapshot

    assert "sec_filing_uid" in result
    assert result["sec_filing_uid"] in snapshot
