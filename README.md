# FinSight — AI-Powered Financial Research Platform

> **Institutional-grade equity research in one click.** Multi-agent AI pipeline that generates comprehensive investment reports with live market data, professional charts, and deep financial analysis.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-14-black?logo=next.js)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## What is FinSight?

FinSight is a full-stack financial research platform that runs a **6-stage AI pipeline** to produce publication-ready investment reports — automatically, from a single stock ticker.

### Sample Report Output
A FinSight report includes:
- **Executive Summary** with investment thesis and key metrics
- **Financial Analysis** — income statement trends, balance sheet, cash flows, valuation multiples
- **Stock Performance** — 2-year price chart, MA50/200, RSI, technical levels
- **Business Segment Analysis** — revenue breakdown by segment with YoY growth
- **Competitive Analysis** — sector-aware peer comparison (P/E, EV/EBITDA, P/S)
- **Risk Factors** — probability/impact rated risk table
- **Macro Environment** — live FRED data (Fed Funds, CPI, GDP, Nasdaq)
- **Outlook & Catalysts** — near-term and medium-term drivers
- **Investment Recommendation** — Bull/Base/Bear scenario price targets

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (Next.js 14)                  │
│  Claude-style sidebar layout · State-driven panels       │
│  Report Viewer · PDF Export · History (localStorage)     │
└────────────────────┬────────────────────────────────────┘
                     │ REST + WebSocket
┌────────────────────▼────────────────────────────────────┐
│                   BACKEND (FastAPI)                       │
│  WebSocket progress streaming · Async job queue          │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              AI PIPELINE (6 stages)                       │
│                                                           │
│  1. Data Collection   → yfinance, SEC EDGAR, FRED, Serper│
│  2. Deep Search       → Web intelligence gathering       │
│  3. Parallel Analysis → 6 simultaneous AI perspectives   │
│  4. Chart Generation  → 6 professional matplotlib charts │
│  5. Report Writing    → Multi-model LLM with fallbacks   │
│  6. Assembly          → Structured markdown report       │
└─────────────────────────────────────────────────────────┘
```

### LLM Fallback Chain
```
Gemini 2.5 Flash (primary)
    ↓ (if quota exceeded)
Groq llama-3.3-70b-versatile
    ↓ (if rate limited)
Groq llama-3.1-8b-instant
    ↓ (if all fail)
Template fallback (live yfinance data, no LLM needed)
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 14, TypeScript, TailwindCSS |
| **Backend** | FastAPI, Uvicorn, WebSockets |
| **AI Models** | Gemini 2.5 Flash, Groq Llama 3.3/3.1 |
| **Data** | yfinance, FRED API, SEC EDGAR, Serper |
| **Charts** | Matplotlib (Agg backend) |
| **Markdown** | react-markdown, remark-gfm |

---

## Project Structure

```
Bricks_by_Bricks/
└── Finsight/
    ├── api/                    # FastAPI app + WebSocket endpoints
    ├── agents/                 # Data collection, deep search, perspective agents
    ├── pipeline/               # Enhanced orchestrator (main pipeline)
    ├── tools/                  # LLM client, data collectors, search
    ├── writing/                # Report writer with multi-model fallback
    ├── visualization/          # Chart generator (6 mandatory charts)
    ├── config/                 # Settings loader (.env)
    ├── frontend/               # Next.js app
    │   ├── app/                # Single-page app (page.tsx)
    │   └── components/         # ReportViewer, ProgressTracker
    └── outputs/                # Generated reports & charts (gitignored)
        ├── reports/
        └── charts/
```

---

## Setup & Installation

### Prerequisites
- Python 3.10+
- Node.js 18+
- Git

### 1. Clone the repo
```bash
git clone https://github.com/Samir-477/Finsight.git
cd Finsight/Bricks_by_Bricks
```

### 2. Create your `.env` file
```bash
cp Finsight/.env.example Finsight/.env
```

Edit `Finsight/.env` and fill in your API keys:
```env
# LLM (Groq — free tier)
DS_API_KEY="your_groq_key"
WRITER_API_KEY="your_groq_key"

# VLM (Google Gemini)
VLM_API_KEY="your_gemini_key"

# Web Search (Serper)
SERPER_API_KEY="your_serper_key"

# Macro Data (FRED — free)
FRED_API_KEY="your_fred_key"

# SEC Filings (just your email)
SEC_USER_AGENT="your@email.com"
```

**Get free API keys:**
- [Groq](https://console.groq.com) — No credit card needed
- [Google AI Studio](https://aistudio.google.com) — Gemini free tier
- [Serper](https://serper.dev) — 2,500 free searches
- [FRED](https://fred.stlouisfed.org/docs/api/api_key.html) — Completely free

### 3. Install Python dependencies
```bash
pip install -r Finsight/requirements.txt
```

### 4. Install frontend dependencies
```bash
cd Finsight/frontend
npm install
cd ../..
```

---

## Running Locally

Open **two terminals** from `Bricks_by_Bricks/`:

**Terminal 1 — Backend:**
```bash
uvicorn Finsight.api.main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd Finsight/frontend
npm run dev
```

Then open **[http://localhost:3000](http://localhost:3000)**

---

## How to Use

1. **Enter a ticker** — e.g. `NVDA`, `AAPL`, `MSFT`
2. **Click "Run Deep Research"** — the pipeline starts and streams progress in real-time
3. **View the report** — structured investment report with 6 embedded charts
4. **Download as PDF** — click "Download PDF" to export via browser print
5. **History** — all past reports saved in the sidebar via localStorage

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/research/start` | Start a new research job |
| `GET` | `/api/research/{id}` | Get job status |
| `GET` | `/api/research/{id}/report` | Fetch completed report |
| `WS` | `/ws/{id}` | Real-time progress updates |
| `GET` | `/charts/{filename}` | Serve chart images |

---

## Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `DS_API_KEY` | Groq API key (main LLM) | ✅ |
| `WRITER_API_KEY` | Groq API key (report writer) | ✅ |
| `VLM_API_KEY` | Google Gemini API key | ✅ |
| `SERPER_API_KEY` | Serper web search key | ✅ |
| `FRED_API_KEY` | FRED economic data key | ✅ |
| `SEC_USER_AGENT` | Your email (SEC EDGAR) | ✅ |
| `OUTPUT_DIR` | Output directory path | Optional |
| `PORT` | Backend port (default: 8000) | Optional |

---

## Known Limitations

- **Free tier rate limits**: Groq has per-minute limits; the pipeline uses automatic fallback to template generation when limits are hit
- **Gemini daily quota**: Google's free tier has a daily RPD limit; resets at midnight Pacific time
- **Report persistence**: Job history is in-memory on the backend; saved reports persist via localStorage on the frontend

---

## Contributing

Pull requests welcome. Please open an issue first to discuss what you'd like to change.

---

## License

MIT © 2026 Samir
