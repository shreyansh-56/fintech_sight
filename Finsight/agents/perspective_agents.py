"""Parallel perspective agents for FinSight analysis."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yfinance as yf

from Finsight.analysis.chain import ChainOfAnalysis, ChainStep
from Finsight.analysis.executor import AnalysisExecutor
from Finsight.runtime.orchestrator import Orchestrator
from Finsight.tools.data_collectors import MarketDataCollector
from Finsight.tools.gemini_client import GeminiClient
from Finsight.visualization.chart_generator import ChartGenerator


class PerspectiveAgent:
    """Base class for perspective-specific analysis agents."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        gemini_client: GeminiClient,
        market_collector: MarketDataCollector,
        chart_generator: ChartGenerator,
    ) -> None:
        self.orchestrator = orchestrator
        self.gemini = gemini_client
        self.market_collector = market_collector
        self.chart_generator = chart_generator
        self.analysis_executor = AnalysisExecutor(orchestrator, gemini_client)

    def run(self, ticker: str, company_name: str) -> Dict[str, Any]:
        """Run the perspective analysis. To be overridden by subclasses."""
        raise NotImplementedError


class FinancialConditionAgent(PerspectiveAgent):
    """Perspective 1: Financial condition (revenue, margins, cash flow, ratios)."""

    def run(self, ticker: str, company_name: str) -> Dict[str, Any]:
        """Analyze financial condition with code execution."""
        
        analysis_goal = (
            f"Analyze the financial condition of {company_name} ({ticker}). "
            "Focus on: revenue trends, gross margins, operating margins, cash flow, "
            "key financial ratios (ROE, ROA, debt-to-equity, current ratio). "
            "Write Python code to calculate these metrics from the available data."
        )
        
        chain, step_logs = self.analysis_executor.run(analysis_goal=analysis_goal, max_steps=3)
        
        # Store chain in variable space
        chain_dict = chain.to_dict()
        chain_uid = self.orchestrator.register_data(
            name=f"{ticker}_financial_condition_chain",
            value=chain_dict,
            description="Financial condition analysis chain",
            tags=["perspective", "financial_condition"],
            source="financial_condition_agent",
        )
        
        # Generate chart
        chart = self.chart_generator.chart_4_revenue_vs_net_income(ticker)
        chart_uid = self.orchestrator.register_data(
            name=f"{ticker}_financial_condition_chart",
            value=chart,
            description="Revenue vs Net Income chart",
            tags=["chart", "financial_condition"],
            source="financial_condition_agent",
        )
        
        return {
            "perspective_id": "perspective_1",
            "focus": "financial_condition",
            "chain_uid": chain_uid,
            "chart_uid": chart_uid,
            "analysis_logs": step_logs,
        }


class StockPerformanceAgent(PerspectiveAgent):
    """Perspective 2: Stock performance (2yr price chart, volume, returns vs index)."""

    def run(self, ticker: str, company_name: str) -> Dict[str, Any]:
        """Analyze stock performance with code execution."""
        
        analysis_goal = (
            f"Analyze the stock performance of {company_name} ({ticker}). "
            "Focus on: 2-year price trend, trading volume, volatility, "
            "returns relative to market index, key support/resistance levels. "
            "Write Python code to calculate these metrics from stock history data."
        )
        
        chain, step_logs = self.analysis_executor.run(analysis_goal=analysis_goal, max_steps=3)
        
        chain_dict = chain.to_dict()
        chain_uid = self.orchestrator.register_data(
            name=f"{ticker}_stock_performance_chain",
            value=chain_dict,
            description="Stock performance analysis chain",
            tags=["perspective", "stock_performance"],
            source="stock_performance_agent",
        )
        
        chart = self.chart_generator.chart_1_stock_price_with_volume(ticker)
        chart_uid = self.orchestrator.register_data(
            name=f"{ticker}_stock_performance_chart",
            value=chart,
            description="Stock price and volume chart",
            tags=["chart", "stock_performance"],
            source="stock_performance_agent",
        )
        
        return {
            "perspective_id": "perspective_2",
            "focus": "stock_performance",
            "chain_uid": chain_uid,
            "chart_uid": chart_uid,
            "analysis_logs": step_logs,
        }


class RevenueBreakdownAgent(PerspectiveAgent):
    """Perspective 3: Revenue breakdown (by segment/product/geography)."""

    def run(self, ticker: str, company_name: str) -> Dict[str, Any]:
        """Analyze revenue breakdown with code execution."""
        
        analysis_goal = (
            f"Analyze the revenue breakdown of {company_name} ({ticker}). "
            "Focus on: revenue by segment, product lines, geographic regions, "
            "concentration risk, growth trends by segment. "
            "Write Python code to analyze revenue data."
        )
        
        chain, step_logs = self.analysis_executor.run(analysis_goal=analysis_goal, max_steps=3)
        
        chain_dict = chain.to_dict()
        chain_uid = self.orchestrator.register_data(
            name=f"{ticker}_revenue_breakdown_chain",
            value=chain_dict,
            description="Revenue breakdown analysis chain",
            tags=["perspective", "revenue_breakdown"],
            source="revenue_breakdown_agent",
        )
        
        chart = self.chart_generator.chart_2_revenue_by_segment(ticker)
        chart_uid = self.orchestrator.register_data(
            name=f"{ticker}_revenue_breakdown_chart",
            value=chart,
            description="Revenue by segment chart",
            tags=["chart", "revenue_breakdown"],
            source="revenue_breakdown_agent",
        )
        
        return {
            "perspective_id": "perspective_3",
            "focus": "revenue_breakdown",
            "chain_uid": chain_uid,
            "chart_uid": chart_uid,
            "analysis_logs": step_logs,
        }


class RiskAnalysisAgent(PerspectiveAgent):
    """Perspective 4: Risk analysis (regulatory, credit, market, operational)."""

    def run(self, ticker: str, company_name: str) -> Dict[str, Any]:
        """Analyze risk factors with code execution."""
        
        analysis_goal = (
            f"Analyze the risk profile of {company_name} ({ticker}). "
            "Focus on: regulatory risks, credit risk (debt levels), market risk (beta, volatility), "
            "operational risks, key risk factors from SEC filings. "
            "Write Python code to calculate risk metrics."
        )
        
        chain, step_logs = self.analysis_executor.run(analysis_goal=analysis_goal, max_steps=3)
        
        chain_dict = chain.to_dict()
        chain_uid = self.orchestrator.register_data(
            name=f"{ticker}_risk_analysis_chain",
            value=chain_dict,
            description="Risk analysis chain",
            tags=["perspective", "risk_analysis"],
            source="risk_analysis_agent",
        )
        
        # Generate a risk visualization (using gross margin trend as proxy)
        chart = self.chart_generator.chart_3_gross_margin_trend(ticker)
        chart_uid = self.orchestrator.register_data(
            name=f"{ticker}_risk_analysis_chart",
            value=chart,
            description="Gross margin trend (risk indicator)",
            tags=["chart", "risk_analysis"],
            source="risk_analysis_agent",
        )
        
        return {
            "perspective_id": "perspective_4",
            "focus": "risk_analysis",
            "chain_uid": chain_uid,
            "chart_uid": chart_uid,
            "analysis_logs": step_logs,
        }


class CompetitiveLandscapeAgent(PerspectiveAgent):
    """Perspective 5: Competitive landscape (market share, peer comparison)."""

    def run(self, ticker: str, company_name: str) -> Dict[str, Any]:
        """Analyze competitive landscape with code execution."""
        
        analysis_goal = (
            f"Analyze the competitive landscape for {company_name} ({ticker}). "
            "Focus on: market position, key competitors, market share, "
            "relative valuation (P/E, EV/EBITDA), competitive advantages. "
            "Write Python code to compare with peer companies."
        )
        
        chain, step_logs = self.analysis_executor.run(analysis_goal=analysis_goal, max_steps=3)
        
        chain_dict = chain.to_dict()
        chain_uid = self.orchestrator.register_data(
            name=f"{ticker}_competitive_landscape_chain",
            value=chain_dict,
            description="Competitive landscape analysis chain",
            tags=["perspective", "competitive_landscape"],
            source="competitive_landscape_agent",
        )
        
        chart = self.chart_generator.chart_5_peer_comparison(ticker)
        chart_uid = self.orchestrator.register_data(
            name=f"{ticker}_competitive_landscape_chart",
            value=chart,
            description="Peer comparison chart",
            tags=["chart", "competitive_landscape"],
            source="competitive_landscape_agent",
        )
        
        return {
            "perspective_id": "perspective_5",
            "focus": "competitive_landscape",
            "chain_uid": chain_uid,
            "chart_uid": chart_uid,
            "analysis_logs": step_logs,
        }


class MacroEnvironmentAgent(PerspectiveAgent):
    """Perspective 6: Macro environment (FRED data: GDP, rates, inflation impact)."""

    def run(self, ticker: str, company_name: str) -> Dict[str, Any]:
        """Analyze macro environment with code execution."""
        
        analysis_goal = (
            f"Analyze the macro environment affecting {company_name} ({ticker}). "
            "Focus on: GDP growth trends, interest rates, inflation, "
            "macroeconomic indicators relevant to the company's industry. "
            "Write Python code to analyze FRED macro data."
        )
        
        chain, step_logs = self.analysis_executor.run(analysis_goal=analysis_goal, max_steps=3)
        
        chain_dict = chain.to_dict()
        chain_uid = self.orchestrator.register_data(
            name=f"{ticker}_macro_environment_chain",
            value=chain_dict,
            description="Macro environment analysis chain",
            tags=["perspective", "macro_environment"],
            source="macro_environment_agent",
        )
        
        chart = self.chart_generator.chart_6_fred_macro("GDP")
        chart_uid = self.orchestrator.register_data(
            name=f"{ticker}_macro_environment_chart",
            value=chart,
            description="FRED GDP chart",
            tags=["chart", "macro_environment"],
            source="macro_environment_agent",
        )
        
        return {
            "perspective_id": "perspective_6",
            "focus": "macro_environment",
            "chain_uid": chain_uid,
            "chart_uid": chart_uid,
            "analysis_logs": step_logs,
        }


class ParallelPerspectiveRunner:
    """Runs all 6 perspectives in parallel."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        gemini_client: GeminiClient,
        market_collector: MarketDataCollector,
        chart_generator: ChartGenerator,
    ) -> None:
        self.orchestrator = orchestrator
        self.gemini = gemini_client
        self.market_collector = market_collector
        self.chart_generator = chart_generator

        self.agents = {
            "perspective_1": FinancialConditionAgent(
                orchestrator, gemini_client, market_collector, chart_generator
            ),
            "perspective_2": StockPerformanceAgent(
                orchestrator, gemini_client, market_collector, chart_generator
            ),
            "perspective_3": RevenueBreakdownAgent(
                orchestrator, gemini_client, market_collector, chart_generator
            ),
            "perspective_4": RiskAnalysisAgent(
                orchestrator, gemini_client, market_collector, chart_generator
            ),
            "perspective_5": CompetitiveLandscapeAgent(
                orchestrator, gemini_client, market_collector, chart_generator
            ),
            "perspective_6": MacroEnvironmentAgent(
                orchestrator, gemini_client, market_collector, chart_generator
            ),
        }

    def run_all(self, ticker: str, company_name: str) -> Dict[str, Any]:
        """Run all 6 perspectives in parallel."""
        
        def run_agent(perspective_id: str) -> Dict[str, Any]:
            agent = self.agents[perspective_id]
            return agent.run(ticker, company_name)

        # Run all perspectives in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(run_agent, pid): pid 
                for pid in self.agents.keys()
            }
            
            results = {}
            for future in futures:
                perspective_id = futures[future]
                try:
                    result = future.result()
                    results[perspective_id] = result
                except Exception as e:
                    # Store error but continue
                    results[perspective_id] = {
                        "perspective_id": perspective_id,
                        "focus": perspective_id.replace("_", " "),
                        "error": str(e),
                    }

        # Store all perspective results
        perspectives_uid = self.orchestrator.register_data(
            name=f"{ticker}_all_perspectives",
            value=results,
            description="All 6 perspective analysis results",
            tags=["perspectives", "parallel"],
            source="parallel_perspective_runner",
        )

        return {
            "perspectives_uid": perspectives_uid,
            "perspectives": results,
            "count": len(results),
        }
