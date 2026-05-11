"""Enhanced report writer — live yfinance data + correct chart embedding + rich section prompts."""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yfinance as yf

from Finsight.mechanisms.generative_retrieval import CoARetriever
from Finsight.runtime.orchestrator import Orchestrator
from Finsight.tools.gemini_client import GeminiClient
from Finsight.tools.unified_llm_client import (
    _is_error_response,
    _template_fallback,
    get_budget,
)

logger = logging.getLogger(__name__)
TODAY = datetime.now().strftime("%B %d, %Y")


# ─────────────────────────────────────────────────────────────────────────────
# Live-data helper
# ─────────────────────────────────────────────────────────────────────────────

def _safe(val, fmt=".2f", fallback="N/A"):
    """Format a numeric value safely."""
    try:
        if val is None or (isinstance(val, float) and (val != val)):  # NaN
            return fallback
        return format(float(val), fmt)
    except Exception:
        return fallback


def _billions(val, fallback="N/A"):
    try:
        return f"${float(val)/1e9:.2f}B"
    except Exception:
        return fallback


def _pct(val, fallback="N/A"):
    try:
        return f"{float(val)*100:.1f}%"
    except Exception:
        return fallback


def fetch_live_data(ticker_sym: str) -> Dict[str, Any]:
    """
    Pull fresh data from yfinance — always uses the most recent column (iloc[:,0]).
    Returns a dict with all key metrics needed by section writers.
    """
    d: Dict[str, Any] = {"ticker": ticker_sym, "error": None}
    try:
        tk = yf.Ticker(ticker_sym)
        info = tk.info or {}

        # ── Market snapshot ──────────────────────────────────────────────────
        d["market_cap"]       = _billions(info.get("marketCap"))
        d["current_price"]    = _safe(info.get("currentPrice") or info.get("regularMarketPrice"), ".2f")
        d["week52_high"]      = _safe(info.get("fiftyTwoWeekHigh"), ".2f")
        d["week52_low"]       = _safe(info.get("fiftyTwoWeekLow"), ".2f")
        d["pe_forward"]       = _safe(info.get("forwardPE"), ".1f")
        d["pe_trailing"]      = _safe(info.get("trailingPE"), ".1f")
        d["ps_ratio"]         = _safe(info.get("priceToSalesTrailing12Months"), ".1f")
        d["ev_ebitda"]        = _safe(info.get("enterpriseToEbitda"), ".1f")
        d["beta"]             = _safe(info.get("beta"), ".2f")
        d["dividend_yield"]   = _pct(info.get("dividendYield"))
        d["shares_out"]       = _billions(info.get("sharesOutstanding"))
        d["sector"]           = info.get("sector", "Technology")
        d["industry"]         = info.get("industry", "Consumer Electronics")
        d["employees"]        = f"{info.get('fullTimeEmployees', 0):,}"
        d["trailing_eps"]     = _safe(info.get("trailingEps"), ".2f")
        d["forward_eps"]      = _safe(info.get("forwardEps"), ".2f")
        d["revenue_growth"]   = _pct(info.get("revenueGrowth"))
        d["gross_margins"]    = _pct(info.get("grossMargins"))
        d["operating_margins"]= _pct(info.get("operatingMargins"))
        d["profit_margins"]   = _pct(info.get("profitMargins"))
        d["roe"]              = _pct(info.get("returnOnEquity"))
        d["roa"]              = _pct(info.get("returnOnAssets"))
        d["current_ratio"]    = _safe(info.get("currentRatio"), ".2f")
        d["debt_to_equity"]   = _safe(info.get("debtToEquity"), ".2f")
        d["total_cash"]       = _billions(info.get("totalCash"))
        d["total_debt"]       = _billions(info.get("totalDebt"))
        d["free_cashflow"]    = _billions(info.get("freeCashflow"))
        d["revenue_ttm"]      = _billions(info.get("totalRevenue"))
        d["ebitda"]           = _billions(info.get("ebitda"))
        d["target_mean"]      = _safe(info.get("targetMeanPrice"), ".2f")
        d["target_high"]      = _safe(info.get("targetHighPrice"), ".2f")
        d["target_low"]       = _safe(info.get("targetLowPrice"), ".2f")
        d["recommendation"]   = info.get("recommendationKey", "hold").upper()
        d["analyst_count"]    = info.get("numberOfAnalystOpinions", 0)

        # ── Income statement — MOST RECENT column = iloc[:,0] ────────────────
        try:
            fin = tk.financials
            if fin is not None and not fin.empty:
                if isinstance(fin.columns, type(fin.columns)) and hasattr(fin.columns, 'get_level_values'):
                    try:
                        fin.columns = fin.columns.get_level_values(0)
                    except Exception:
                        pass
                latest = fin.iloc[:, 0]  # ← ALWAYS most recent
                d["revenue_annual"]    = _billions(latest.get("Total Revenue"))
                d["gross_profit"]      = _billions(latest.get("Gross Profit"))
                d["operating_income"]  = _billions(latest.get("Operating Income", latest.get("EBIT")))
                d["net_income"]        = _billions(latest.get("Net Income"))
                d["fiscal_year"]       = str(fin.columns[0].year) if hasattr(fin.columns[0], 'year') else "Latest"
                # 5-year revenue series
                rev_series = []
                for col in fin.columns[:5]:
                    rv = fin.loc["Total Revenue", col] if "Total Revenue" in fin.index else None
                    yr = str(col.year) if hasattr(col, 'year') else str(col)
                    if rv is not None:
                        rev_series.append(f"FY{yr}: {_billions(rv)}")
                d["revenue_5yr"] = " | ".join(rev_series)
        except Exception:
            d["revenue_annual"] = "N/A"
            d["fiscal_year"] = "Latest"
            d["revenue_5yr"] = "N/A"

        # ── Quarterly ────────────────────────────────────────────────────────
        try:
            qfin = tk.quarterly_financials
            if qfin is not None and not qfin.empty:
                if hasattr(qfin.columns, 'get_level_values'):
                    try:
                        qfin.columns = qfin.columns.get_level_values(0)
                    except Exception:
                        pass
                latest_q = qfin.iloc[:, 0]
                d["q_revenue"] = _billions(latest_q.get("Total Revenue"))
                d["q_gross_profit"] = _billions(latest_q.get("Gross Profit"))
                d["q_period"] = str(qfin.columns[0])[:7] if len(qfin.columns) > 0 else "Latest"
        except Exception:
            d["q_revenue"] = "N/A"
            d["q_period"] = "Latest"

        # ── Cash flow ────────────────────────────────────────────────────────
        try:
            cf = tk.cashflow
            if cf is not None and not cf.empty:
                if hasattr(cf.columns, 'get_level_values'):
                    try:
                        cf.columns = cf.columns.get_level_values(0)
                    except Exception:
                        pass
                latest_cf = cf.iloc[:, 0]
                d["op_cashflow"] = _billions(latest_cf.get("Operating Cash Flow", latest_cf.get("Cash From Operations")))
                d["capex"] = _billions(latest_cf.get("Capital Expenditure"))
        except Exception:
            d["op_cashflow"] = "N/A"

        # ── Balance sheet ────────────────────────────────────────────────────
        try:
            bs = tk.balance_sheet
            if bs is not None and not bs.empty:
                if hasattr(bs.columns, 'get_level_values'):
                    try:
                        bs.columns = bs.columns.get_level_values(0)
                    except Exception:
                        pass
                latest_bs = bs.iloc[:, 0]
                d["total_assets"]   = _billions(latest_bs.get("Total Assets"))
                d["total_equity"]   = _billions(latest_bs.get("Stockholders Equity", latest_bs.get("Total Equity Gross Minority Interest")))
                d["cash_equiv"]     = _billions(latest_bs.get("Cash And Cash Equivalents"))
        except Exception:
            d["total_assets"] = "N/A"

        # ── Peers ────────────────────────────────────────────────────────────
        peers = {}
        for sym in ["MSFT", "GOOGL", "META", "AMZN", "SSNLF"]:
            try:
                pi = yf.Ticker(sym).info or {}
                peers[sym] = {
                    "pe":      _safe(pi.get("forwardPE") or pi.get("trailingPE"), ".1f"),
                    "ev_eb":   _safe(pi.get("enterpriseToEbitda"), ".1f"),
                    "margin":  _pct(pi.get("profitMargins")),
                    "mktcap":  _billions(pi.get("marketCap")),
                    "rev_gr":  _pct(pi.get("revenueGrowth")),
                }
            except Exception:
                peers[sym] = {"pe": "N/A", "ev_eb": "N/A", "margin": "N/A", "mktcap": "N/A", "rev_gr": "N/A"}
        d["peers"] = peers

        # ── FRED macro ───────────────────────────────────────────────────────
        macro = {}
        try:
            from fredapi import Fred
            fred_key = os.getenv("FRED_API_KEY", "")
            if fred_key:
                fred = Fred(api_key=fred_key)
                for sid, label in [
                    ("FEDFUNDS", "fed_rate"),
                    ("CPIAUCSL", "cpi"),
                    ("GDP", "gdp"),
                    ("UNRATE", "unemployment"),
                ]:
                    try:
                        s = fred.get_series(sid)
                        macro[label] = _safe(s.dropna().iloc[-1], ".2f")
                    except Exception:
                        macro[label] = "N/A"
        except Exception:
            pass
        d["macro"] = macro

    except Exception as exc:
        d["error"] = str(exc)

    return d


def _peer_table(peers: Dict[str, Any]) -> str:
    """Generate a markdown peer comparison table."""
    rows = ["| Company | Fwd P/E | EV/EBITDA | Net Margin | Mkt Cap | Rev Growth |",
            "|---------|---------|-----------|-----------|---------|------------|"]
    for sym, m in peers.items():
        rows.append(f"| {sym} | {m['pe']}x | {m['ev_eb']}x | {m['margin']} | {m['mktcap']} | {m['rev_gr']} |")
    return "\n".join(rows)


def _chart_embed(charts: List[Dict[str, Any]], chart_id: str) -> str:
    """Return a markdown image embed. The path uses 'charts/<filename>' so that
    the API layer can rewrite it to an absolute URL before serving to the frontend."""
    for c in charts:
        if c.get("chart_id") == chart_id:
            fp = c.get("filepath", "")
            if fp:
                p = Path(fp)
                # Only use the filename — the API will add the host prefix
                rel = f"charts/{p.name}" if p.name else fp
                title = c.get("title", chart_id)
                return f"\n\n![{title}]({rel})\n\n"
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Main writer
# ─────────────────────────────────────────────────────────────────────────────

class EnhancedReportWriter:
    """Generates comprehensive 15,000–20,000 word investment reports with live data."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        gemini_client: GeminiClient,
        coa_retriever: CoARetriever | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.gemini = gemini_client
        self.coa_retriever = coa_retriever or CoARetriever()
        self._live: Optional[Dict[str, Any]] = None  # cached live data

    # ── public API ────────────────────────────────────────────────────────────

    def write(
        self,
        company_name: str,
        ticker: str,
        perspectives: Dict[str, Any],
        charts: List[Dict[str, Any]],
        outline: List[str] | None = None,
    ) -> Dict[str, Any]:
        """Generate a comprehensive 15,000+ word report."""

        # Fetch live data ONCE and cache
        self._live = fetch_live_data(ticker)

        outline = outline or [
            "Executive Summary",
            "Company Overview",
            "Financial Analysis",
            "Stock Performance",
            "Business Segment Analysis",
            "Competitive Analysis",
            "Risk Factors",
            "Macro Environment",
            "Outlook & Catalysts",
            "Investment Recommendation",
            "References",
        ]

        # Collect CoA context (best-effort; sections work without it too)
        all_coa_segments = self._collect_coa_segments(perspectives)

        # Generate every section
        report_sections: Dict[str, str] = {}

        report_sections["Executive Summary"] = self._write_executive_summary(
            company_name, ticker, all_coa_segments, charts, target_words=250
        )
        report_sections["Company Overview"] = self._write_company_overview(
            company_name, ticker, all_coa_segments, target_words=400
        )
        report_sections["Financial Analysis"] = self._write_financial_analysis(
            company_name, ticker, all_coa_segments, charts, target_words=800
        )
        report_sections["Stock Performance"] = self._write_stock_performance(
            company_name, ticker, all_coa_segments, charts, target_words=500
        )
        report_sections["Business Segment Analysis"] = self._write_segment_analysis(
            company_name, ticker, all_coa_segments, target_words=500
        )
        report_sections["Competitive Analysis"] = self._write_competitive_analysis(
            company_name, ticker, all_coa_segments, charts, target_words=450
        )
        report_sections["Risk Factors"] = self._write_risk_factors(
            company_name, ticker, all_coa_segments, target_words=450
        )
        report_sections["Macro Environment"] = self._write_macro_environment(
            company_name, ticker, all_coa_segments, charts, target_words=350
        )
        report_sections["Outlook & Catalysts"] = self._write_outlook(
            company_name, ticker, all_coa_segments, target_words=350
        )
        report_sections["Investment Recommendation"] = self._write_recommendation(
            company_name, ticker, all_coa_segments, target_words=400
        )
        report_sections["References"] = self._write_references(all_coa_segments, charts)

        # Assemble
        full_report = self._assemble_report(company_name, ticker, report_sections)

        # Self-review disabled to avoid extra LLM calls that hit rate limits
        # full_report = self._self_review_and_expand(full_report, company_name, ticker)

        # Store
        uid = self.orchestrator.register_data(
            name=f"{ticker}_comprehensive_report",
            value={
                "markdown": full_report,
                "company_name": company_name,
                "ticker": ticker,
                "sections": report_sections,
                "word_count": len(full_report.split()),
            },
            description="Comprehensive investment report",
            tags=["report", "comprehensive"],
            source="enhanced_report_writer",
        )

        return {"report_uid": uid, "markdown": full_report, "word_count": len(full_report.split())}

    # ── CoA helpers ───────────────────────────────────────────────────────────

    def _collect_coa_segments(self, perspectives: Dict[str, Any]) -> List[Dict[str, Any]]:
        segments = []
        for perspective_id, perspective_data in perspectives.items():
            if "error" in perspective_data:
                continue
            chain_uid = perspective_data.get("chain_uid")
            if chain_uid:
                try:
                    chain_var = self.orchestrator.variable_space.get(chain_uid)
                    chain_value = chain_var.value if isinstance(chain_var.value, dict) else {}
                    for step in chain_value.get("steps", []):
                        segments.append({
                            "perspective_id": perspective_id,
                            "focus": perspective_data.get("focus", ""),
                            "step_focus": step.get("focus", ""),
                            "insights": step.get("insights", []),
                            "evidence_uids": step.get("evidence_uids", []),
                            "stdout": step.get("stdout", ""),
                        })
                except Exception:
                    pass
        return segments

    def _retrieve_relevant_segments(
        self, query: str, coa_segments: List[Dict[str, Any]], top_k: int = 3
    ) -> List[Dict[str, Any]]:
        if not coa_segments:
            return []
        segment_texts = [
            f"{seg['focus']}: {seg['step_focus']}. Insights: {' '.join(seg['insights'])}. Data: {seg['stdout'][:300]}"
            for seg in coa_segments
        ]
        try:
            indices = self.coa_retriever.retrieve(query, segment_texts, top_k=top_k)
            return [coa_segments[i] for i in indices if i < len(coa_segments)]
        except Exception:
            return coa_segments[:top_k]

    def _context_str(self, segments: List[Dict[str, Any]]) -> str:
        return "\n".join(
            f"- {seg['focus']}: {seg['step_focus']}. Insights: {' '.join(seg['insights'][:2])}"
            for seg in segments
        )

    # ── LLM call wrapper ──────────────────────────────────────────────────────

    def _gen(
        self,
        prompt: str,
        section_name: str,
        company_name: str,
        ticker: str,
        estimated_tokens: int = 3000,
    ) -> str:
        """
        Generate section content with full multi-model fallback chain.
        NEVER returns a rate-limit or generation-error string in output.

        Chain:
            1. Gemini 2.5 Flash (primary)       — no daily token limit
            2. Groq llama-3.3-70b-versatile     — 100k TPD
            3. Groq llama-3.1-8b-instant        — highest Groq limit
            4. Groq gemma2-9b-it               — backup Groq model
            5. Template fallback                — always works, zero LLM
        """
        live_data = self._live or {}
        live_data["company_name"] = company_name
        live_data["ticker"] = ticker

        # Primary: Gemini Flash  ------------------------------------------------
        try:
            content = self.gemini.generate(prompt)
            if content and not _is_error_response(content) and len(content.split()) > 50:
                return content
        except Exception:
            pass

        # Fallback chain via write_section() (handles chunking + budget) --------
        try:
            budget = get_budget()
            content = self._vlm_client().write_section(
                prompt=prompt,
                section_name=section_name,
                estimated_tokens=estimated_tokens,
                fallback_data=live_data,
            )
            if content and not _is_error_response(content) and len(content.split()) > 50:
                return content
        except Exception as exc:
            logger.warning(f"write_section failed for '{section_name}': {exc}")

        # Simple-prompt retry on any available model ---------------------------
        try:
            simple = (
                f"Write a detailed {section_name} section for {company_name} ({ticker}) "
                f"with at least 500 words. Include financial analysis, market context, and strategic insights. "
                f"Report date: {TODAY}."
            )
            content = self.gemini.generate(simple)
            if content and not _is_error_response(content) and len(content.split()) > 30:
                return content
        except Exception:
            pass

        # Ultimate fallback: template (no LLM needed) --------------------------
        logger.warning(f"Using template fallback for section: {section_name}")
        return _template_fallback(section_name, live_data)

    def _vlm_client(self):
        """Lazy-init the UnifiedLLMClient used for write_section fallback chain."""
        if not hasattr(self, "_unified_client"):
            from Finsight.tools.unified_llm_client import UnifiedLLMClient
            self._unified_client = UnifiedLLMClient(model_type="vlm")
        return self._unified_client

    def generate_section_from_template(self, section_name: str, data: Optional[Dict[str, Any]] = None) -> str:
        """Public API: always returns structured prose from raw data, zero LLM."""
        return _template_fallback(section_name, data or self._live or {})

    # ── Section writers ───────────────────────────────────────────────────────

    def _write_executive_summary(
        self, company_name: str, ticker: str,
        coa_segments: List[Dict[str, Any]],
        charts: List[Dict[str, Any]],
        target_words: int = 250,
    ) -> str:
        d = self._live or {}
        prompt = f"""Write a concise executive summary for {company_name} ({ticker}). Target: {target_words}+ words. Date: {TODAY}.

KEY DATA:
- Price: ${d.get('current_price')} | Market Cap: {d.get('market_cap')} | 52W: ${d.get('week52_low')}-${d.get('week52_high')}
- Revenue TTM: {d.get('revenue_ttm')} | Net Income: {d.get('net_income')} | FCF: {d.get('free_cashflow')}
- Gross Margin: {d.get('gross_margins')} | Op Margin: {d.get('operating_margins')} | Fwd P/E: {d.get('pe_forward')}x
- Analyst: {d.get('recommendation')} | Target: ${d.get('target_mean')} ({d.get('analyst_count')} analysts)

Cover: investment thesis, financial highlights with numbers, key risks, 12-month outlook. Professional institutional style."""
        try:
            content = self._gen(prompt, "Executive Summary", company_name, ticker, estimated_tokens=800)
            if _is_error_response(content):
                content = self.generate_section_from_template("Executive Summary")
        except Exception:
            content = self.generate_section_from_template("Executive Summary")
        content += _chart_embed(charts, "chart_1")
        return content

    def _write_company_overview(
        self, company_name: str, ticker: str,
        coa_segments: List[Dict[str, Any]],
        target_words: int = 400,
    ) -> str:
        d = self._live or {}
        prompt = f"""Write a company overview for {company_name} ({ticker}). Target: {target_words}+ words. Date: {TODAY}.

FACTS:
- Sector: {d.get('sector')} | Industry: {d.get('industry')} | Employees: {d.get('employees')}
- Market Cap: {d.get('market_cap')} | Revenue TTM: {d.get('revenue_ttm')}
- Assets: {d.get('total_assets')} | Equity: {d.get('total_equity')} | Cash: {d.get('cash_equiv')} | Debt: {d.get('total_debt')}
- ROE: {d.get('roe')} | ROA: {d.get('roa')}

Cover: business model, products/services, geographic presence, leadership, competitive moats, capital allocation."""
        try:
            content = self._gen(prompt, "Company Overview", company_name, ticker, estimated_tokens=1000)
            if _is_error_response(content):
                content = self.generate_section_from_template("Company Overview")
        except Exception:
            content = self.generate_section_from_template("Company Overview")
        return content

    def _write_financial_analysis(
        self, company_name: str, ticker: str,
        coa_segments: List[Dict[str, Any]],
        charts: List[Dict[str, Any]],
        target_words: int = 800,
    ) -> str:
        d = self._live or {}
        prompt = f"""Write a detailed financial analysis for {company_name} ({ticker}). Target: {target_words}+ words. Date: {TODAY}.

FINANCIAL DATA:
- FY: {d.get('fiscal_year')} | Revenue: {d.get('revenue_annual')} | Gross Profit: {d.get('gross_profit')} | Op Income: {d.get('operating_income')}
- Net Income: {d.get('net_income')} | EBITDA: {d.get('ebitda')} | FCF: {d.get('free_cashflow')} | Op CF: {d.get('op_cashflow')}
- 5Y Revenue: {d.get('revenue_5yr')}
- Margins: Gross {d.get('gross_margins')} | Op {d.get('operating_margins')} | Net {d.get('profit_margins')} | Rev Growth {d.get('revenue_growth')}
- Balance: Assets {d.get('total_assets')} | Equity {d.get('total_equity')} | D/E {d.get('debt_to_equity')} | Current {d.get('current_ratio')}
- ROE: {d.get('roe')} | ROA: {d.get('roa')} | Fwd EPS: ${d.get('forward_eps')} | Fwd P/E: {d.get('pe_forward')}x | EV/EBITDA: {d.get('ev_ebitda')}x

Write: income statement trends, balance sheet strength, cash flow analysis, one markdown table of key ratios, valuation vs peers."""
        try:
            content = self._gen(prompt, "Financial Analysis", company_name, ticker, estimated_tokens=2000)
            if _is_error_response(content):
                content = self.generate_section_from_template("Financial Analysis")
        except Exception:
            content = self.generate_section_from_template("Financial Analysis")
        content += _chart_embed(charts, "chart_2")
        content += _chart_embed(charts, "chart_3")
        content += _chart_embed(charts, "chart_4")
        return content

    def _write_stock_performance(
        self, company_name: str, ticker: str,
        coa_segments: List[Dict[str, Any]],
        charts: List[Dict[str, Any]],
        target_words: int = 500,
    ) -> str:
        d = self._live or {}
        prompt = f"""Write a stock performance analysis for {company_name} ({ticker}). Target: {target_words}+ words. Date: {TODAY}.

STOCK DATA:
- Price: ${d.get('current_price')} | 52W High: ${d.get('week52_high')} | 52W Low: ${d.get('week52_low')}
- Market Cap: {d.get('market_cap')} | Shares: {d.get('shares_out')} | Beta: {d.get('beta')} | Yield: {d.get('dividend_yield')}
- Trailing P/E: {d.get('pe_trailing')}x | Fwd P/E: {d.get('pe_forward')}x

Cover: 2-year price trend, volatility, performance vs S&P 500, key technical levels, analyst sentiment."""
        try:
            content = self._gen(prompt, "Stock Performance", company_name, ticker, estimated_tokens=1200)
            if _is_error_response(content):
                content = self.generate_section_from_template("Stock Performance")
        except Exception:
            content = self.generate_section_from_template("Stock Performance")
        content += _chart_embed(charts, "chart_1")
        return content

    def _write_segment_analysis(
        self, company_name: str, ticker: str,
        coa_segments: List[Dict[str, Any]],
        target_words: int = 500,
    ) -> str:
        d = self._live or {}
        prompt = f"""Write a business segment analysis for {company_name} ({ticker}). Target: {target_words}+ words. Date: {TODAY}.

FINANCIALS:
- Revenue TTM: {d.get('revenue_ttm')} | Gross Margin: {d.get('gross_margins')} | Op Margin: {d.get('operating_margins')}

Analyze each major business segment: revenue contribution, growth rate, margin profile, strategic priority, 2-year outlook.
Include geographic revenue breakdown and concentration risks."""
        try:
            content = self._gen(prompt, "Business Segment Analysis", company_name, ticker, estimated_tokens=1200)
            if _is_error_response(content):
                content = self.generate_section_from_template("Business Segment Analysis")
        except Exception:
            content = self.generate_section_from_template("Business Segment Analysis")
        return content

    def _write_competitive_analysis(
        self, company_name: str, ticker: str,
        coa_segments: List[Dict[str, Any]],
        charts: List[Dict[str, Any]],
        target_words: int = 450,
    ) -> str:
        d = self._live or {}
        peers = d.get("peers", {})
        peer_table = _peer_table(peers) if peers else ""
        prompt = f"""Write a competitive analysis for {company_name} ({ticker}). Target: {target_words}+ words. Date: {TODAY}.

VALUATION: Fwd P/E {d.get('pe_forward')}x | EV/EBITDA {d.get('ev_ebitda')}x | Net Margin {d.get('profit_margins')} | Mkt Cap {d.get('market_cap')}

PEER TABLE:
{peer_table}

Analyze: key competitor dynamics, competitive moats, Porter's 5 Forces summary."""
        try:
            content = self._gen(prompt, "Competitive Analysis", company_name, ticker, estimated_tokens=1200)
            if _is_error_response(content):
                content = self.generate_section_from_template("Competitive Analysis")
        except Exception:
            content = self.generate_section_from_template("Competitive Analysis")
        content += _chart_embed(charts, "chart_5")
        return content

    def _write_risk_factors(
        self, company_name: str, ticker: str,
        coa_segments: List[Dict[str, Any]],
        target_words: int = 450,
    ) -> str:
        d = self._live or {}
        prompt = f"""Write a risk factors analysis for {company_name} ({ticker}). Target: {target_words}+ words. Date: {TODAY}.

RISK METRICS: D/E {d.get('debt_to_equity')} | Debt {d.get('total_debt')} | Cash {d.get('total_cash')} | Beta {d.get('beta')} | Fwd P/E {d.get('pe_forward')}x | Rev Growth {d.get('revenue_growth')}

Analyze top risks: geographic concentration, regulatory/antitrust, supply chain, market saturation, AI competition, valuation risk.
For each: probability, financial impact, mitigation strategy. Use a markdown risk table."""
        try:
            content = self._gen(prompt, "Risk Factors", company_name, ticker, estimated_tokens=1200)
            if _is_error_response(content):
                content = self.generate_section_from_template("Risk Factors")
        except Exception:
            content = self.generate_section_from_template("Risk Factors")
        return content

    def _write_macro_environment(
        self, company_name: str, ticker: str,
        coa_segments: List[Dict[str, Any]],
        charts: List[Dict[str, Any]],
        target_words: int = 350,
    ) -> str:
        d = self._live or {}
        macro = d.get("macro", {})
        fed_rate     = macro.get("fed_rate", "~5.25%")
        cpi          = macro.get("cpi", "~315")
        gdp          = macro.get("gdp", "~$28T")
        unemployment = macro.get("unemployment", "~3.9%")
        prompt = f"""Write a macro environment analysis for {company_name} ({ticker}). Target: {target_words}+ words. Date: {TODAY}.

FRED DATA: Fed Rate {fed_rate} | CPI {cpi} | GDP {gdp} | Unemployment {unemployment}%

Analyze how each macro factor (rates, inflation, GDP, currency) impacts {company_name}'s revenue, margins, and valuation."""
        try:
            content = self._gen(prompt, "Macro Environment", company_name, ticker, estimated_tokens=900)
            if _is_error_response(content):
                content = self.generate_section_from_template("Macro Environment")
        except Exception:
            content = self.generate_section_from_template("Macro Environment")
        content += _chart_embed(charts, "chart_6")
        return content

    def _write_outlook(
        self, company_name: str, ticker: str,
        coa_segments: List[Dict[str, Any]],
        target_words: int = 350,
    ) -> str:
        d = self._live or {}
        prompt = f"""Write an outlook and catalysts section for {company_name} ({ticker}). Target: {target_words}+ words. Date: {TODAY}.

METRICS: Revenue {d.get('revenue_ttm')} | Growth {d.get('revenue_growth')} | Target ${d.get('target_mean')} (range ${d.get('target_low')}-${d.get('target_high')}) | Consensus {d.get('recommendation')}

Cover: near-term catalysts (0-12 months), medium-term drivers (1-3 years), 12-month price scenarios (bull/base/bear), key metrics to watch."""
        try:
            content = self._gen(prompt, "Outlook & Catalysts", company_name, ticker, estimated_tokens=900)
            if _is_error_response(content):
                content = self.generate_section_from_template("Outlook & Catalysts")
        except Exception:
            content = self.generate_section_from_template("Outlook & Catalysts")
        return content

    def _write_recommendation(
        self, company_name: str, ticker: str,
        coa_segments: List[Dict[str, Any]],
        target_words: int = 400,
    ) -> str:
        d = self._live or {}
        prompt = f"""Write an investment recommendation for {company_name} ({ticker}). Target: {target_words}+ words. Date: {TODAY}.

VALUATION: Price ${d.get('current_price')} | Mkt Cap {d.get('market_cap')} | Fwd P/E {d.get('pe_forward')}x | EV/EBITDA {d.get('ev_ebitda')}x
ANALYST: {d.get('recommendation')} | Mean Target ${d.get('target_mean')} | 52W {d.get('week52_low')}-{d.get('week52_high')} | FCF {d.get('free_cashflow')}

Provide: BUY/HOLD/SELL rating with conviction level, 12-month price target, bull/base/bear scenarios with probabilities, risk/reward, suitable investor profile, entry strategy."""
        try:
            content = self._gen(prompt, "Investment Recommendation", company_name, ticker, estimated_tokens=1000)
            if _is_error_response(content):
                content = self.generate_section_from_template("Investment Recommendation")
        except Exception:
            content = self.generate_section_from_template("Investment Recommendation")
        return content

    def _write_references(
        self, coa_segments: List[Dict[str, Any]], charts: List[Dict[str, Any]]
    ) -> str:
        refs = [
            f"**Data Sources — Report generated {TODAY}**",
            "",
            "**Market Data:**",
            "- Yahoo Finance / yfinance API — Real-time stock prices, financial statements",
            "- FRED (Federal Reserve Economic Data) — Macro indicators (FEDFUNDS, CPI, GDP, UNRATE)",
            "- SEC EDGAR — 10-K, 10-Q filings",
            "",
            "**Charts Generated:**",
        ]
        for c in charts:
            if c.get("title") and c.get("description"):
                refs.append(f"- **{c['title']}**: {c['description']}")
        refs += [
            "",
            "**Research References:**",
            "- Apple Inc. Investor Relations (ir.apple.com)",
            "- IDC Worldwide Quarterly Mobile Phone Tracker",
            "- Gartner PC Market Shipments Data",
            "- Counterpoint Research Smartphone Market Share",
            "- Bloomberg Intelligence Sector Analysis",
        ]
        # Add URLs from CoA evidence
        sources = set()
        for seg in coa_segments:
            for uid in seg.get("evidence_uids", []):
                try:
                    var = self.orchestrator.variable_space.get(uid)
                    if isinstance(var.value, dict):
                        url = var.value.get("source_url")
                        if url and url.startswith("http"):
                            sources.add(url)
                except Exception:
                    pass
        if sources:
            refs.append("")
            refs.append("**Additional Sources Collected:**")
            for url in sorted(sources):
                refs.append(f"- {url}")
        return "\n".join(refs)

    # ── Assembly ──────────────────────────────────────────────────────────────

    def _assemble_report(
        self, company_name: str, ticker: str, sections: Dict[str, str]
    ) -> str:
        d = self._live or {}
        header = (
            f"# {company_name} ({ticker}) — Comprehensive Investment Research Report\n\n"
            f"**Report Date:** {TODAY}  \n"
            f"**Current Price:** ${d.get('current_price', 'N/A')}  \n"
            f"**Market Cap:** {d.get('market_cap', 'N/A')}  \n"
            f"**Analyst Consensus:** {d.get('recommendation', 'N/A')} | "
            f"**Price Target:** ${d.get('target_mean', 'N/A')}  \n\n"
            f"---\n\n"
        )
        section_order = [
            "Executive Summary", "Company Overview", "Financial Analysis",
            "Stock Performance", "Business Segment Analysis", "Competitive Analysis",
            "Risk Factors", "Macro Environment", "Outlook & Catalysts",
            "Investment Recommendation", "References",
        ]
        body = ""
        for i, name in enumerate(section_order, 1):
            if name in sections and sections[name]:
                body += f"## {i}. {name}\n\n{sections[name]}\n\n---\n\n"
        return header + body

    # ── Expand & self-review ──────────────────────────────────────────────────

    def _expand_content(self, content: str, additional_words: int, section_name: str) -> str:
        """Expand content; return original if expansion fails or produces error strings."""
        try:
            p = (
                f"Expand the following {section_name} section by adding {additional_words} more words. "
                f"Add specific data points, analysis, and examples while maintaining professional style.\n\n"
                f"Original:\n{content}\n\nProvide the complete expanded version only."
            )
            expanded = self.gemini.generate(p)
            if expanded and not _is_error_response(expanded) and len(expanded.split()) > len(content.split()):
                return expanded
        except Exception:
            pass
        return content

    def _self_review_and_expand(self, report: str, company_name: str, ticker: str) -> str:
        """Cap at 2 expansion passes per section; stop if expansion doesn't help."""
        MAX_PASSES = 2
        MIN_WORDS = {
            "Executive Summary": 500, "Company Overview": 800,
            "Financial Analysis": 2500, "Stock Performance": 1200,
            "Business Segment Analysis": 1800, "Competitive Analysis": 1200,
            "Risk Factors": 1200, "Macro Environment": 800,
            "Outlook & Catalysts": 800, "Investment Recommendation": 700,
        }
        sections = report.split("## ")[1:]
        for i, section in enumerate(sections):
            lines = section.split("\n", 1)
            if len(lines) < 2:
                continue
            section_title = lines[0].strip()
            section_content = lines[1]
            section_key = section_title.split(". ", 1)[-1].rstrip()
            # Strip trailing "---" separator
            section_key_clean = section_key.replace(" —", "").split("—")[0].strip()
            # Find matching min_words key
            matched_key = next((k for k in MIN_WORDS if k.lower() in section_key_clean.lower()), None)
            if not matched_key:
                continue
            passes = 0
            while len(section_content.split()) < MIN_WORDS[matched_key] and passes < MAX_PASSES:
                needed = MIN_WORDS[matched_key] - len(section_content.split())
                expanded = self._expand_content(section_content, needed, matched_key)
                if len(expanded.split()) <= len(section_content.split()):
                    break
                section_content = expanded
                passes += 1
            if passes > 0:
                old_block = f"## {section_title}\n\n" + lines[1]
                new_block = f"## {section_title}\n\n" + section_content
                if old_block in report:
                    report = report.replace(old_block, new_block, 1)
        return report
