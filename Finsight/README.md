# FinSight Implementation

This folder contains a full implementation of the **FinSight** architecture described in the paper *"FinSight: Towards Real-World Financial Deep Research"* (Jin et al., 2025). The system implements the Code Agent with Variable Memory (CAVM) design with:

- Multi-source data collection (akshare, yfinance, FRED, SEC EDGAR)
- Deep search with Serper API
- Code-first analysis with Chain-of-Analysis (CoA)
- Iterative visualization refinement with VLM critique (Gemini Flash)
- Two-stage report writing with generative retrieval
- Modern Next.js 14 frontend with real-time WebSocket progress

## Architecture

```
Finsight/
├── agents/                # Data collection, deep search, analysis, report generation
├── analysis/              # Chain-of-analysis structures and executor
├── api/                   # FastAPI server with REST + WebSocket endpoints
├── config/                # Environment configuration loader (.env based)
├── evaluation/            # Automated metric functions
├── frontend/              # Next.js 14 frontend with shadcn/ui
│   ├── app/               # Next.js app router pages
│   ├── components/        # React components (ResearchForm, ProgressTracker, ReportViewer)
│   └── lib/               # API client and WebSocket hook
├── interfaces/            # Base classes for agents/tools
├── mechanisms/            # Iterative VLM critique, generative retrieval
├── memory/                # Enhanced VariableSpace with Φ() function from paper
├── pipeline/              # High-level FinSightPipeline orchestrator
├── runtime/               # CAVM runtime: variable space, orchestrator, code executor
├── tests/                 # Smoke tests
├── tools/                 # Unified LLM client, financial API wrappers, search
├── visualization/         # Iterative visualization refinement loop (Plotly)
├── writing/               # Two-stage writing (chain compiler + report writer)
├── requirements.txt       # Python dependencies
└── .env                   # API keys (already configured)
```

## Model Configuration

**Free Stack (keys already in .env):**
- **LLM**: llama-3.3-70b-versatile via Groq
- **Writer**: deepseek-r1-distill-llama-70b via Groq
- **VLM**: gemini-2.5-flash via Google API
- **Embeddings**: sentence-transformers all-MiniLM-L6-v2 (local, no API)
- **Web Search**: SERPER_API_KEY
- **Macro Data**: FRED_API_KEY via fredapi
- **SEC Filings**: SEC_USER_AGENT via sec-edgar-downloader
- **Financial Data**: akshare (A-shares/HK) + yfinance (US stocks)

## Setup

### Backend

```bash
cd Finsight
pip install -r requirements.txt
```

### Frontend

```bash
cd Finsight/frontend
npm install
```

## Running the System

### Terminal 1 - Start FastAPI Backend

```bash
cd Finsight
uvicorn api.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

### Terminal 2 - Start Next.js Frontend

```bash
cd Finsight/frontend
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Usage

1. Open `http://localhost:3000` in your browser
2. Enter a company name and ticker (e.g., "NVIDIA", "NVDA")
3. Select the target type (Public Company, Industry, Macro, General)
4. Click "Start FinSight Research"
5. Watch real-time progress through the 3-stage pipeline:
   - Data Collection
   - Data Analysis
   - Report Generation
6. View the final publication-ready report with citations

## API Endpoints

- `POST /api/research/start` - Start a new research job
- `GET /api/research/{job_id}` - Get job status
- `GET /api/research/{job_id}/report` - Get the final markdown report
- `GET /api/history` - Get all past research jobs
- `WS /ws/{job_id}` - WebSocket for real-time progress updates

## Key Features

### CAVM Variable Space
- Implements the Φ() function from paper equation (1)
- Unified storage for data, tools, and agent variables
- Checkpointing for resumable runs
- Delta computation for efficient state tracking

### Iterative Visualization
- VLM critique loop (3 iterations per paper Appendix C)
- Professional chart quality assessment
- Automatic refinement based on visual feedback

### Two-Stage Writing
- Stage 1: Parallel CoA generation from multiple perspectives
- Stage 2: Structured writing with embedding-based retrieval
- Citation system with [Ref: UID] identifiers
- Self-reflective optimization

### Real-Time Progress
- WebSocket streaming of pipeline stages
- Sub-step progress updates
- Agent reasoning traces (CoA debug view)

## Testing

```bash
pytest Finsight/tests/
```

## References

- Paper: *"FinSight: Towards Real-World Financial Deep Research"* (Jin et al., arXiv:2510.16844v1, Oct 2025)
- Official Implementation: https://github.com/RUC-NLPIR/FinSight
