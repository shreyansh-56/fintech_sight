"""Unified LLM client supporting Groq and Gemini APIs with smart multi-model fallback."""
from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any, Dict, List, Optional, Sequence

from openai import OpenAI

from Finsight.config.settings import get_settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Token Budget Manager
# ─────────────────────────────────────────────────────────────────────────────

class TokenBudgetManager:
    """
    Tracks estimated daily token usage per model and routes to the best
    available model automatically.

    Priority order (highest quality → most available):
        gemini-2.5-flash  →  llama-3.3-70b-versatile
                          →  llama-3.1-8b-instant
                          →  gemma2-9b-it
                          →  template  (zero LLM calls)
    """

    DAILY_LIMITS: Dict[str, int] = {
        "gemini-2.5-flash":        999_999,   # effectively unlimited (250 req/day, not token-capped)
        "llama-3.3-70b-versatile": 100_000,   # Groq production — 100k TPD
        "llama-3.1-8b-instant":    500_000,   # Groq fast — 500k TPD
        "gemma2-9b-it":            500_000,   # Groq Google model — backup
    }

    # Quality-ordered preference list for writing tasks
    WRITER_PREFERENCE: List[str] = [
        "gemini-2.5-flash",
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
    ]

    # Quality-ordered preference list for analysis/reasoning tasks (short outputs)
    ANALYST_PREFERENCE: List[str] = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "gemma2-9b-it",
        "gemini-2.5-flash",
    ]

    def __init__(self) -> None:
        self.used: Dict[str, int] = {k: 0 for k in self.DAILY_LIMITS}

    def can_use(self, model: str, estimated_tokens: int) -> bool:
        limit = self.DAILY_LIMITS.get(model, 0)
        return self.used.get(model, 0) + estimated_tokens < limit

    def record_usage(self, model: str, tokens_used: int) -> None:
        if model in self.used:
            self.used[model] += tokens_used

    def get_best_writer_model(self, estimated_tokens: int = 3000) -> str:
        """Return best available model for writing long sections."""
        for model in self.WRITER_PREFERENCE:
            if self.can_use(model, estimated_tokens):
                return model
        return "template"

    def get_best_analyst_model(self, estimated_tokens: int = 2000) -> str:
        """Return best available model for short analysis/reasoning tasks."""
        for model in self.ANALYST_PREFERENCE:
            if self.can_use(model, estimated_tokens):
                return model
        return "template"

    def summary(self) -> str:
        lines = ["Token budget status:"]
        for model, used in self.used.items():
            limit = self.DAILY_LIMITS[model]
            pct = used / limit * 100
            lines.append(f"  {model}: {used:,} / {limit:,} ({pct:.1f}%)")
        return "\n".join(lines)


# Singleton — shared across all clients in one process
_budget = TokenBudgetManager()


def get_budget() -> TokenBudgetManager:
    return _budget


# ─────────────────────────────────────────────────────────────────────────────
# Unified LLM Client
# ─────────────────────────────────────────────────────────────────────────────

class UnifiedLLMClient:
    """
    Unified client for Groq and Gemini APIs with:
    - write_section(): Gemini primary → Groq llama-3.3-70b → llama-3.1-8b fallbacks → template
    - generate(): standard single-model call
    - generate_structured(): JSON output
    - generate_multimodal(): Gemini VLM only
    """

    def __init__(self, model_type: str = "llm") -> None:
        """
        Initialize the unified LLM client.

        Args:
            model_type: One of "llm", "writer", or "vlm"
        """
        self.settings = get_settings()
        self.model_type = model_type

        if model_type == "llm":
            self.client = OpenAI(
                api_key=self.settings.ds_api_key,
                base_url=self.settings.ds_base_url,
            )
            self.model_name = self.settings.ds_model_name
            self.provider = "groq"

        elif model_type == "writer":
            self.client = OpenAI(
                api_key=self.settings.writer_api_key,
                base_url=self.settings.writer_base_url,
            )
            self.model_name = self.settings.writer_model_name
            self.provider = "groq"

        elif model_type == "vlm":
            # Use OpenAI-compatible Gemini endpoint
            self.client = OpenAI(
                api_key=self.settings.vlm_api_key,
                base_url=self.settings.vlm_base_url,
            )
            self.model_name = self.settings.vlm_model_name
            self.provider = "gemini_openai"

        else:
            raise ValueError(f"Unknown model_type: {model_type}")

        # Groq clients for fallback models (lazy-built on first use)
        self._groq_clients: Dict[str, OpenAI] = {}

    def _get_groq_client(self) -> OpenAI:
        """Return (cached) Groq OpenAI-compatible client."""
        key = "groq"
        if key not in self._groq_clients:
            self._groq_clients[key] = OpenAI(
                api_key=self.settings.writer_api_key,
                base_url=self.settings.writer_base_url,
            )
        return self._groq_clients[key]

    def _get_gemini_openai_client(self) -> OpenAI:
        """Return (cached) Gemini OpenAI-compatible client."""
        key = "gemini"
        if key not in self._groq_clients:
            self._groq_clients[key] = OpenAI(
                api_key=self.settings.vlm_api_key,
                base_url=self.settings.vlm_base_url,
            )
        return self._groq_clients[key]

    # ── Core generation ──────────────────────────────────────────────────────

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text from the LLM."""
        if self.provider in ("groq", "gemini_openai"):
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get("temperature", 0.7),
                max_tokens=kwargs.get("max_tokens", 8192),
                timeout=30,
            )
            text = response.choices[0].message.content or ""
            # Estimate token usage for budget tracking
            _budget.record_usage(self.model_name, len(prompt.split()) + len(text.split()))
            return text
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def generate_structured(self, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        """Generate structured JSON output."""
        if self.provider in ("groq", "gemini_openai"):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=kwargs.get("temperature", 0.3),
                    max_tokens=kwargs.get("max_tokens", 8192),
                    timeout=30,
                )
                text = response.choices[0].message.content or "{}"
                return json.loads(text)
            except Exception:
                # Gemini doesn't always honour json_object; try plain then parse
                text = self.generate(prompt + "\n\nRespond with valid JSON only.", **kwargs)
                try:
                    return json.loads(text)
                except Exception:
                    return {}
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def generate_multimodal(self, parts: Sequence[Any], **kwargs: Any) -> str:
        """Generate text from multimodal input (text + image)."""
        # Build OpenAI-style content list from parts
        content: List[Any] = []
        for part in parts:
            if isinstance(part, str):
                content.append({"type": "text", "text": part})
            elif isinstance(part, dict) and "mime_type" in part:
                # Gemini-style image part
                b64 = base64.b64encode(part["data"]).decode("utf-8")
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{part['mime_type']};base64,{b64}"},
                })
            elif isinstance(part, bytes):
                b64 = base64.b64encode(part).decode("utf-8")
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                })

        client = self._get_gemini_openai_client()
        try:
            response = client.chat.completions.create(
                model=self.settings.vlm_model_name,
                messages=[{"role": "user", "content": content}],
                max_tokens=kwargs.get("max_tokens", 4096),
                timeout=30,
            )
            return response.choices[0].message.content or ""
        except Exception:
            # Text-only fallback
            text_parts = [p for p in parts if isinstance(p, str)]
            return self.generate(" ".join(text_parts))

    def complete_with_image(self, prompt: str, image_b64: str, image_type: str = "image/png") -> str:
        """Complete a prompt with an image (for VLM)."""
        image_bytes = base64.b64decode(image_b64)
        return self.generate_multimodal([prompt, {"mime_type": image_type, "data": image_bytes}])

    # ── Smart multi-model write_section ──────────────────────────────────────

    def write_section(
        self,
        prompt: str,
        section_name: str,
        estimated_tokens: int = 3000,
        fallback_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Write a long-form report section using the best available model.

        Fallback chain (tried in order until one succeeds):
            1. Gemini 2.5 Flash         (primary — no daily token cap)
            2. Groq llama-3.3-70b-versatile
            3. Groq llama-3.1-8b-instant
            4. Template (pure data formatting — no LLM)
        """
        # Always try all models in priority order
        priority_chain = [
            "gemini-2.5-flash",
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
        ]

        for model in priority_chain:
            if not _budget.can_use(model, estimated_tokens):
                logger.info(f"write_section '{section_name}': budget exhausted for {model}, skipping")
                continue
            logger.info(f"write_section '{section_name}': trying model={model}")
            result = self._try_write(prompt, model, estimated_tokens)
            if result:
                return result
            # Model failed (rate-limit or error) — mark as used-up to skip next time
            _budget.record_usage(model, _budget.DAILY_LIMITS.get(model, 100_000))

        # All models exhausted → template
        logger.warning(f"All LLM models exhausted for '{section_name}', using template fallback")
        return _template_fallback(section_name, fallback_data or {})

    def _try_write(self, prompt: str, model: str, estimated_tokens: int) -> str:
        """
        Attempt to generate using the given model.

        - Gemini: sends the full prompt in one call (large context window).
        - Groq models: compresses the prompt to a short, model-safe version
          (≤ 1,200 chars) to stay well under the 8k-token burst limit.
        Returns empty string on failure.
        """
        is_gemini = model.startswith("gemini")

        if is_gemini:
            # Gemini can handle large prompts — send as-is
            result = self._call_model(prompt, model, max_tokens=4096)
            if result is None:
                return ""
            if not result or _is_error_response(result):
                return ""
            _budget.record_usage(model, estimated_tokens)
            return result
        else:
            # Groq small models — use a compact version of the prompt
            compact = _compact_prompt(prompt)
            result = self._call_model(compact, model, max_tokens=2048)
            if result is None:
                return ""
            if not result or _is_error_response(result):
                return ""
            _budget.record_usage(model, estimated_tokens)
            return result

    def _call_model(self, prompt: str, model: str, max_tokens: int = 2800) -> Optional[str]:
        """
        Single LLM call against a named model.
        Returns None on rate-limit or hard error.
        
        Uses exponential backoff: 3s → 10s → 30s max.
        On persistent rate-limit, returns None so caller tries next model.
        """
        is_gemini = model.startswith("gemini")
        base_url = self.settings.vlm_base_url if is_gemini else self.settings.writer_base_url
        api_key = self.settings.vlm_api_key if is_gemini else self.settings.writer_api_key
        c = OpenAI(api_key=api_key, base_url=base_url)

        max_retries = 2  # Only retry once on rate-limit before giving up
        backoff_times = [3, 10]  # Seconds to wait before each retry

        for attempt in range(max_retries + 1):
            try:
                response = c.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=max_tokens,
                    timeout=30,
                )
                text = response.choices[0].message.content or ""
                if _is_error_response(text):
                    return None
                return text
            except Exception as e:
                err = str(e)
                # 413 = request too large → skip this model immediately, no retry
                if "413" in err or "too large" in err.lower() or "context_length" in err.lower():
                    logger.warning(f"Request too large for {model} — skipping to next model")
                    return None
                is_rate_limit = any(kw in err for kw in (
                    "rate", "429", "quota", "limit", "exhausted",
                    "RESOURCE", "ResourceExhausted", "overloaded",
                ))
                if is_rate_limit:
                    if attempt < max_retries:
                        wait = backoff_times[attempt]
                        logger.warning(
                            f"Rate-limit on {model} (attempt {attempt+1}/{max_retries}): "
                            f"waiting {wait}s before retry. Error: {err[:100]}"
                        )
                        time.sleep(wait)
                    else:
                        logger.warning(f"Rate-limit on {model}: giving up after {max_retries} retries")
                        return None
                else:
                    logger.error(f"Hard error on {model}: {err[:200]}")
                    return None

        return None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _is_error_response(text: str) -> bool:
    """Return True if the text contains an LLM error or rate-limit message."""
    bad_phrases = [
        "rate limit", "Rate limit", "Rate Limit",
        "Generation error", "generation error",
        "quota exceeded", "Quota exceeded",
        "ResourceExhausted", "RESOURCE_EXHAUSTED",
        "model is currently overloaded",
        "temporarily unavailable",
    ]
    return any(phrase in text for phrase in bad_phrases)


def _compact_prompt(prompt: str, max_chars: int = 1200) -> str:
    """
    Compress a long research prompt down to ≤ max_chars for Groq small-model calls.
    Keeps the instruction header and the first N chars of the body.
    """
    lines = prompt.strip().split("\n")
    header_lines: List[str] = []
    body_lines: List[str] = []
    in_body = False
    for line in lines:
        if not in_body and (line.startswith("###") or (line.startswith("**") and len(header_lines) > 5)):
            in_body = True
        if in_body:
            body_lines.append(line)
        else:
            header_lines.append(line)

    header = "\n".join(header_lines).strip()
    body   = "\n".join(body_lines).strip()

    # Hard-cap the header and body
    header_cap = header[:600]
    body_cap   = body[:max_chars - len(header_cap) - 100]

    compact = f"{header_cap}\n\nWrite a concise but informative analysis (400-600 words).\n\n{body_cap}"
    return compact[:max_chars]


def _chunk_prompt(prompt: str) -> List[str]:
    """Legacy helper — kept for backward compatibility.
    Returns the prompt as a single-element list (no chunking needed now).
    """
    return [prompt]


def _template_fallback(section_name: str, data: Dict[str, Any]) -> str:
    """
    Generate a structured 800-1,000 word section purely from data dict.
    No LLM required — always works regardless of quota.
    """
    ticker = data.get("ticker", "N/A")
    company = data.get("company_name", ticker)

    templates: Dict[str, str] = {
        "Executive Summary": _tmpl_executive(company, ticker, data),
        "Company Overview": _tmpl_company_overview(company, ticker, data),
        "Financial Analysis": _tmpl_financial(company, ticker, data),
        "Stock Performance": _tmpl_stock(company, ticker, data),
        "Business Segment Analysis": _tmpl_segments(company, ticker, data),
        "Competitive Analysis": _tmpl_competitive(company, ticker, data),
        "Risk Factors": _tmpl_risks(company, ticker, data),
        "Macro Environment": _tmpl_macro(company, ticker, data),
        "Outlook & Catalysts": _tmpl_outlook(company, ticker, data),
        "Investment Recommendation": _tmpl_recommendation(company, ticker, data),
    }
    # Match section name flexibly
    for key, content in templates.items():
        if key.lower() in section_name.lower() or section_name.lower() in key.lower():
            return content

    # Generic fallback
    return _tmpl_generic(section_name, company, ticker, data)


def _fmt(data: Dict[str, Any], key: str, default: str = "N/A") -> str:
    return str(data.get(key, default) or default)


def _tmpl_executive(company: str, ticker: str, d: Dict[str, Any]) -> str:
    return f"""## Executive Summary

**{company} ({ticker})** is a leading company in the {_fmt(d,'sector')} sector ({_fmt(d,'industry')}).
As of the report date, the company trades at **${_fmt(d,'current_price')}** with a market capitalisation of **{_fmt(d,'market_cap')}**.

### Financial Highlights
| Metric | Value |
|--------|-------|
| Revenue (TTM) | {_fmt(d,'revenue_ttm')} |
| Net Income | {_fmt(d,'net_income')} |
| Free Cash Flow | {_fmt(d,'free_cashflow')} |
| Gross Margin | {_fmt(d,'gross_margins')} |
| Operating Margin | {_fmt(d,'operating_margins')} |
| Net Margin | {_fmt(d,'profit_margins')} |
| Forward P/E | {_fmt(d,'pe_forward')}x |
| EV/EBITDA | {_fmt(d,'ev_ebitda')}x |

### Investment Thesis
{company} demonstrates strong fundamentals: gross margins of {_fmt(d,'gross_margins')} and a free cash flow
of {_fmt(d,'free_cashflow')} underscore the company's capital efficiency. The balance sheet holds
{_fmt(d,'total_cash')} in cash against {_fmt(d,'total_debt')} in total debt, reflecting a
manageable leverage profile.

Analyst consensus stands at **{_fmt(d,'recommendation')}** with a mean 12-month price target of
**${_fmt(d,'target_mean')}** (range: ${_fmt(d,'target_low')} – ${_fmt(d,'target_high')}),
based on {_fmt(d,'analyst_count')} analysts. The 52-week range is
${_fmt(d,'week52_low')} – ${_fmt(d,'week52_high')}.

### Key Risks
- Regulatory and antitrust exposure across major markets
- Geographic concentration risk (see Risk Factors section)
- Premium valuation leaves limited margin of safety

### Conclusion
Given robust cash generation, industry-leading margins, and a clear growth roadmap,
{company} represents a compelling long-term investment for quality-oriented portfolios.
"""


def _tmpl_company_overview(company: str, ticker: str, d: Dict[str, Any]) -> str:
    return f"""## Company Overview

**{company} ({ticker})** is classified in the **{_fmt(d,'sector')}** sector under the
**{_fmt(d,'industry')}** industry. The company employs approximately **{_fmt(d,'employees')}** full-time
staff globally and maintains a market capitalisation of **{_fmt(d,'market_cap')}**.

### Balance Sheet Snapshot
| Item | Value |
|------|-------|
| Total Assets | {_fmt(d,'total_assets')} |
| Total Equity | {_fmt(d,'total_equity')} |
| Cash & Equivalents | {_fmt(d,'cash_equiv')} |
| Total Debt | {_fmt(d,'total_debt')} |
| Return on Equity | {_fmt(d,'roe')} |
| Return on Assets | {_fmt(d,'roa')} |

### Business Model
{company} operates a diversified business across hardware, software, and services verticals.
The company's integrated ecosystem creates powerful switching costs and drives recurring revenue
through services and subscriptions.

### Capital Allocation Strategy
With free cash flow of {_fmt(d,'free_cashflow')}, management pursues disciplined capital
allocation including shareholder returns via buybacks (dividend yield: {_fmt(d,'dividend_yield')}),
strategic reinvestment in R&D, and selective M&A.
"""


def _tmpl_financial(company: str, ticker: str, d: Dict[str, Any]) -> str:
    return f"""## Financial Analysis

### Income Statement Summary (FY {_fmt(d,'fiscal_year')})
| Metric | Value |
|--------|-------|
| Annual Revenue | {_fmt(d,'revenue_annual')} |
| Gross Profit | {_fmt(d,'gross_profit')} |
| Operating Income | {_fmt(d,'operating_income')} |
| Net Income | {_fmt(d,'net_income')} |
| EBITDA | {_fmt(d,'ebitda')} |

**5-Year Revenue Trend:** {_fmt(d,'revenue_5yr')}

### Profitability Ratios
| Ratio | Value |
|-------|-------|
| Gross Margin | {_fmt(d,'gross_margins')} |
| Operating Margin | {_fmt(d,'operating_margins')} |
| Net Margin | {_fmt(d,'profit_margins')} |
| ROE | {_fmt(d,'roe')} |
| ROA | {_fmt(d,'roa')} |

### Cash Flow & Liquidity
| Item | Value |
|------|-------|
| Operating Cash Flow | {_fmt(d,'op_cashflow')} |
| Capital Expenditure | {_fmt(d,'capex')} |
| Free Cash Flow | {_fmt(d,'free_cashflow')} |
| Current Ratio | {_fmt(d,'current_ratio')} |
| Debt / Equity | {_fmt(d,'debt_to_equity')} |

### Valuation
| Multiple | Value |
|----------|-------|
| Trailing P/E | {_fmt(d,'pe_trailing')}x |
| Forward P/E | {_fmt(d,'pe_forward')}x |
| P/S Ratio | {_fmt(d,'ps_ratio')}x |
| EV/EBITDA | {_fmt(d,'ev_ebitda')}x |
| Trailing EPS | ${_fmt(d,'trailing_eps')} |
| Forward EPS | ${_fmt(d,'forward_eps')} |

{company}'s financial profile reflects a high-quality business: {_fmt(d,'gross_margins')} gross margins
combined with {_fmt(d,'profit_margins')} net margins place it among the most profitable companies in its sector.
Free cash flow of {_fmt(d,'free_cashflow')} provides ample capital for shareholder returns and reinvestment.
"""


def _tmpl_stock(company: str, ticker: str, d: Dict[str, Any]) -> str:
    return f"""## Stock Performance

{company} ({ticker}) currently trades at **${_fmt(d,'current_price')}**.

### Key Price Metrics
| Metric | Value |
|--------|-------|
| Current Price | ${_fmt(d,'current_price')} |
| 52-Week High | ${_fmt(d,'week52_high')} |
| 52-Week Low | ${_fmt(d,'week52_low')} |
| Market Cap | {_fmt(d,'market_cap')} |
| Shares Outstanding | {_fmt(d,'shares_out')} |
| Beta | {_fmt(d,'beta')} |
| Dividend Yield | {_fmt(d,'dividend_yield')} |
| Trailing P/E | {_fmt(d,'pe_trailing')}x |
| Forward P/E | {_fmt(d,'pe_forward')}x |

### Volatility & Risk Profile
Beta of **{_fmt(d,'beta')}** indicates the stock's sensitivity relative to the broader market.
A beta above 1.0 implies higher volatility; below 1.0 implies relative defensiveness.

### Analyst Sentiment
Consensus rating: **{_fmt(d,'recommendation')}** from {_fmt(d,'analyst_count')} analysts.
Mean 12-month target: **${_fmt(d,'target_mean')}** (Range: ${_fmt(d,'target_low')} – ${_fmt(d,'target_high')}).
"""


def _tmpl_segments(company: str, ticker: str, d: Dict[str, Any]) -> str:
    return f"""## Business Segment Analysis

{company} ({ticker}) operates across multiple business segments contributing to total TTM revenue of
**{_fmt(d,'revenue_ttm')}** with an overall gross margin of **{_fmt(d,'gross_margins')}**.

### Segment Overview
The company's diversified portfolio creates resilience against single-product concentration risk.
High-margin services and software segments offset hardware cyclicality, driving sustainable
operating margins of **{_fmt(d,'operating_margins')}**.

### Financial Context
| Metric | Value |
|--------|-------|
| Total Revenue (TTM) | {_fmt(d,'revenue_ttm')} |
| Revenue Growth (YoY) | {_fmt(d,'revenue_growth')} |
| Gross Margin | {_fmt(d,'gross_margins')} |
| Operating Margin | {_fmt(d,'operating_margins')} |
| Net Margin | {_fmt(d,'profit_margins')} |

### Strategic Priorities
Management continues to invest in high-margin recurring revenue streams while maintaining
hardware innovation as the primary customer acquisition channel. The services flywheel —
where hardware install base drives services adoption — is a key competitive differentiator.
"""


def _tmpl_competitive(company: str, ticker: str, d: Dict[str, Any]) -> str:
    peers = d.get("peers", {})
    peer_rows = ""
    for sym, m in peers.items():
        peer_rows += f"| {sym} | {m.get('pe','N/A')}x | {m.get('ev_eb','N/A')}x | {m.get('margin','N/A')} | {m.get('mktcap','N/A')} | {m.get('rev_gr','N/A')} |\n"

    return f"""## Competitive Analysis

### {company} Valuation vs Peers
| Company | Fwd P/E | EV/EBITDA | Net Margin | Mkt Cap | Rev Growth |
|---------|---------|-----------|------------|---------|------------|
| **{ticker}** | **{_fmt(d,'pe_forward')}x** | **{_fmt(d,'ev_ebitda')}x** | **{_fmt(d,'profit_margins')}** | **{_fmt(d,'market_cap')}** | **{_fmt(d,'revenue_growth')}** |
{peer_rows}
### Competitive Moats
{company} benefits from deep competitive advantages including:
- **Ecosystem lock-in**: Integrated hardware, software, and services create high switching costs
- **Brand premium**: Consistent ability to command price premiums over competitors
- **Supply chain mastery**: Vertical integration and proprietary silicon development
- **Network effects**: Large installed base drives services adoption and developer engagement

### Porter's Five Forces Assessment
| Force | Rating | Commentary |
|-------|--------|------------|
| Competitive Rivalry | High | Intense competition from global tech giants |
| Threat of New Entrants | Low | Enormous capital and brand barriers to entry |
| Bargaining Power of Suppliers | Medium | Concentrated chip supply (TSMC) creates some risk |
| Bargaining Power of Buyers | Low-Medium | Strong brand loyalty limits buyer leverage |
| Threat of Substitutes | Medium | Android ecosystem and cloud services as alternatives |
"""


def _tmpl_risks(company: str, ticker: str, d: Dict[str, Any]) -> str:
    return f"""## Risk Factors

### Risk Summary Matrix
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Geographic Concentration | High | High | Diversify manufacturing; expand markets |
| Regulatory / Antitrust | High | High | Engage regulators; modify commission structures |
| Supply Chain Concentration | Medium | High | Multi-source; domestic fab investment |
| Market Saturation | Medium | Medium | Services growth; emerging markets |
| AI Competition | Medium | Medium | Accelerate AI integration (Apple Intelligence) |
| Valuation Risk | Medium | Medium | Maintain FCF growth to justify premium |
| Currency Headwinds | Low-Medium | Medium | Natural hedging; FX derivatives |

### Key Financial Risk Metrics
| Metric | Value | Risk Implication |
|--------|-------|-----------------|
| Total Debt | {_fmt(d,'total_debt')} | Manageable vs cash position |
| Cash & Equivalents | {_fmt(d,'total_cash')} | Strong liquidity buffer |
| Debt / Equity | {_fmt(d,'debt_to_equity')} | Leverage assessment needed |
| Beta | {_fmt(d,'beta')} | Market sensitivity indicator |
| Forward P/E | {_fmt(d,'pe_forward')}x | Valuation risk if growth disappoints |
| Revenue Growth | {_fmt(d,'revenue_growth')} | Sustaining growth is critical |

Investors should monitor these risk factors through quarterly earnings calls,
regulatory filings, and industry data releases.
"""


def _tmpl_macro(company: str, ticker: str, d: Dict[str, Any]) -> str:
    macro = d.get("macro", {})
    return f"""## Macro Environment

### Current FRED Macro Indicators
| Indicator | Value | Impact on {company} |
|-----------|-------|---------------------|
| Fed Funds Rate | {macro.get('fed_rate', 'N/A')}% | Higher rates compress high-P/E valuations |
| CPI Index | {macro.get('cpi', 'N/A')} | Input cost inflation risk |
| US GDP | ${macro.get('gdp', 'N/A')}T | Consumer spending environment |
| Unemployment Rate | {macro.get('unemployment', 'N/A')}% | Labour market health |

### Macro Impact Assessment
**Interest Rates**: At current levels, elevated rates create modest headwinds for premium-valued technology stocks
by increasing the discount rate applied to future earnings in DCF models.

**Inflation**: Component cost inflation affects hardware margins. However, {company}'s pricing power
and long-term supplier agreements partially offset this pressure.

**Consumer Spending**: Employment near historic lows supports continued premium hardware purchases.
Any recessionary shock could extend replacement cycles and dampen near-term unit volumes.

**Currency**: Approximately 60% of revenue is generated outside the US; USD strength represents
an ongoing translation headwind on international earnings.
"""


def _tmpl_outlook(company: str, ticker: str, d: Dict[str, Any]) -> str:
    return f"""## Outlook & Catalysts

### 12-Month Price Target Summary
| Scenario | Target | Key Assumptions |
|----------|--------|-----------------|
| Bull | ${_fmt(d,'target_high')} | AI upgrade supercycle; services acceleration |
| Base | ${_fmt(d,'target_mean')} | Steady growth; margins stable |
| Bear | ${_fmt(d,'target_low')} | Macro slowdown; regulatory headwinds |

### Near-Term Catalysts (0–12 Months)
- **AI Integration**: On-device AI features driving device upgrade motivation
- **Services Momentum**: Continued gross margin expansion in high-margin services segment
- **Product Cycle**: Next-generation hardware releases with new form factors and capabilities
- **Shareholder Returns**: Ongoing buyback programme reducing share count

### Medium-Term Catalysts (1–3 Years)
- **Emerging Markets Expansion**: Growing middle-class populations in Asia and Middle East
- **Health Technology**: Medical-grade sensors expanding addressable market
- **Spatial Computing**: Next-generation mixed reality platform at accessible price points
- **Manufacturing Diversification**: Reduced supply chain concentration risk

### Metrics to Watch
- Quarterly revenue and units per segment
- Services gross margin trajectory (currently {_fmt(d,'gross_margins')})
- International revenue trends
- Share repurchase pace vs guidance
- Analyst price target revisions (current mean: ${_fmt(d,'target_mean')})

Revenue growth of {_fmt(d,'revenue_growth')} YoY demonstrates the business's resilience.
Analyst consensus of **{_fmt(d,'recommendation')}** reflects cautious optimism heading into
the next product cycle.
"""


def _tmpl_recommendation(company: str, ticker: str, d: Dict[str, Any]) -> str:
    rec = _fmt(d, "recommendation", "HOLD")
    return f"""## Investment Recommendation

### Rating: {rec}
**12-Month Price Target: ${_fmt(d,'target_mean')}**
Implied change from current price of ${_fmt(d,'current_price')}.

### Valuation Summary
| Method | Implied Value | Notes |
|--------|---------------|-------|
| Analyst Consensus | ${_fmt(d,'target_mean')} | Mean of {_fmt(d,'analyst_count')} analysts |
| 52-Week High | ${_fmt(d,'week52_high')} | Recent peak |
| Forward P/E ({_fmt(d,'pe_forward')}x) | Market-implied | vs sector median |

### Bull / Base / Bear Cases
| Case | Target | Probability | Key Driver |
|------|--------|-------------|------------|
| Bull | ${_fmt(d,'target_high')} | 25% | AI upgrade cycle + services surge |
| Base | ${_fmt(d,'target_mean')} | 55% | Steady execution, buybacks |
| Bear | ${_fmt(d,'target_low')} | 20% | Macro shock or regulatory action |

**Probability-weighted target:** Calculated from scenario weights above.

### Investor Suitability
- **Suitable for**: Long-term growth investors, dividend growth investors, quality-focused portfolios
- **Less suitable for**: Deep value investors seeking large margin of safety
- **Position sizing**: 3–7% of diversified equity portfolio

### Entry Strategy
- **Ideal entry**: On pullbacks toward or below current market price
- **Time horizon**: Minimum 2–3 years to capture next product and services cycle
- **Key risk to monitor**: {_fmt(d,'sector')} regulatory environment and geographic concentration

Free cash flow of **{_fmt(d,'free_cashflow')}** and dividend yield of **{_fmt(d,'dividend_yield')}**
support the income component of the total return thesis.
"""


def _tmpl_generic(section_name: str, company: str, ticker: str, d: Dict[str, Any]) -> str:
    return f"""## {section_name}

This section provides structured financial data for **{company} ({ticker})**.

### Key Metrics
| Metric | Value |
|--------|-------|
| Market Cap | {_fmt(d,'market_cap')} |
| Revenue (TTM) | {_fmt(d,'revenue_ttm')} |
| Net Income | {_fmt(d,'net_income')} |
| Free Cash Flow | {_fmt(d,'free_cashflow')} |
| Gross Margin | {_fmt(d,'gross_margins')} |
| Forward P/E | {_fmt(d,'pe_forward')}x |
| Analyst Target | ${_fmt(d,'target_mean')} |
| Consensus | {_fmt(d,'recommendation')} |

Data sourced from Yahoo Finance and FRED as of the report date.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Embedding Client (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

class EmbeddingClient:
    """Local embedding client using sentence-transformers."""

    def __init__(self, model_name: Optional[str] = None) -> None:
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

    def encode_single(self, text: str) -> list[float]:
        return self.encode([text])[0]
