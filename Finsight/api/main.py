"""FastAPI server for FinSight."""
from __future__ import annotations

import asyncio
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, WebSocket, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from Finsight.config.settings import get_settings
from Finsight.pipeline.enhanced_orchestrator import EnhancedFinSightPipeline

settings = get_settings()

# ── Output directory layout ──────────────────────────────────────────────────
_OUTPUT_DIR = Path(settings.output_dir).resolve()
_REPORTS_DIR = _OUTPUT_DIR / "reports"
_CHARTS_DIR = _OUTPUT_DIR / "charts"
_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
_CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# Thread pool for blocking pipeline work
_EXECUTOR = ThreadPoolExecutor(max_workers=4)

app = FastAPI(title="FinSight API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve chart images statically at /charts/<filename>
if _CHARTS_DIR.exists():
    app.mount("/charts", StaticFiles(directory=str(_CHARTS_DIR)), name="charts")


class ResearchRequest(BaseModel):
    target_name: str
    stock_code: str
    target_type: str = "financial_company"
    language: str = "en"
    custom_tasks: list[str] = []


class ResearchJob(BaseModel):
    job_id: str
    status: str
    stage: str = ""
    progress: int = 0
    report_path: str = ""
    error: str = ""


# In-memory job store (use Redis in production)
jobs: Dict[str, ResearchJob] = {}
progress_queues: Dict[str, asyncio.Queue] = {}


@app.post("/api/research/start", response_model=ResearchJob)
async def start_research(request: ResearchRequest, background_tasks: BackgroundTasks):
    """Start a new research job."""
    job_id = str(uuid.uuid4())
    job = ResearchJob(job_id=job_id, status="queued")
    jobs[job_id] = job
    progress_queues[job_id] = asyncio.Queue()
    background_tasks.add_task(run_pipeline, job_id, request)
    return job


@app.get("/api/research/{job_id}", response_model=ResearchJob)
async def get_job_status(job_id: str):
    """Get the status of a research job."""
    return jobs.get(job_id, ResearchJob(job_id=job_id, status="not_found"))


@app.get("/api/research/{job_id}/report")
async def get_report(job_id: str):
    """Get the full markdown report for a completed job."""
    job = jobs.get(job_id)
    if not job or job.status != "done":
        return {"error": "Report not ready"}
    try:
        with open(job.report_path, encoding="utf-8") as f:
            content = f.read()
        # Rewrite relative chart paths to absolute API URLs so frontend can render them
        content = content.replace(
            "](charts/",
            "](http://localhost:8000/charts/",
        )
        return {"markdown": content, "job": job}
    except FileNotFoundError:
        return {"error": f"Report file not found at {job.report_path}"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/history")
async def get_history():
    """Get list of all past research jobs."""
    return list(jobs.values())


@app.websocket("/ws/{job_id}")
async def websocket_progress(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time progress streaming."""
    await websocket.accept()
    queue = progress_queues.get(job_id)
    if not queue:
        await websocket.close(code=4004)
        return
    try:
        while True:
            message = await queue.get()
            await websocket.send_json(message)
            if message.get("type") in ("complete", "error"):
                break
    except Exception:
        pass
    finally:
        await websocket.close()


def _run_pipeline_sync(request: ResearchRequest) -> dict:
    """Synchronous pipeline execution — runs inside ThreadPoolExecutor."""
    pipeline = EnhancedFinSightPipeline(output_dir=_OUTPUT_DIR)
    return pipeline.run(
        company_name=request.target_name,
        ticker=request.stock_code,
        analysis_goal=f"Comprehensive analysis of {request.target_name}",
        fred_series_ids={"gdp": "GDP"},
    )


async def run_pipeline(job_id: str, request: ResearchRequest):
    """Background task: runs the enhanced FinSight pipeline in a thread executor.
    
    The pipeline is CPU/IO heavy and fully synchronous. Running it directly
    inside an async function would block the FastAPI event loop, freezing
    ALL other requests (including the WebSocket heartbeat). 
    We offload it to a ThreadPoolExecutor so the event loop stays free.
    """
    job = jobs[job_id]
    queue = progress_queues[job_id]

    async def emit(type_: str, **kwargs):
        await queue.put({"type": type_, "job_id": job_id, **kwargs})

    try:
        job.status = "running"

        # ── Stage 1: Initialising ──────────────────────────────────────────
        job.stage = "data_collection"
        await emit("stage_start", stage="data_collection",
                   message="Initialising pipeline and collecting financial data...")
        await emit("progress", progress=5,
                   message="Pipeline initialised — starting data collection")

        # ── Run full pipeline in background thread ─────────────────────────
        # Each stage inside the pipeline emits its own logs; we stream
        # progress milestones as the thread reports back via the queue.
        loop = asyncio.get_event_loop()

        # Kick off the blocking work in the executor
        future = loop.run_in_executor(_EXECUTOR, _run_pipeline_sync, request)

        # Emit fake-but-honest progress ticks while we wait
        progress_steps = [
            (10, "data_collection",       "Fetching market data, SEC filings, macro data..."),
            (25, "data_collection",       "Deep search & news collection complete"),
            (35, "parallel_perspectives", "Running 6 parallel analysis perspectives..."),
            (50, "parallel_perspectives", "Perspectives: financial, risk, competitive, macro..."),
            (65, "chart_generation",      "Generating 6 professional charts..."),
            (75, "chart_generation",      "Charts: price/volume, revenue, margins, peers, macro..."),
            (80, "report_generation",     "Writing comprehensive investment report..."),
            (90, "report_generation",     "Expanding sections to 15,000+ words..."),
        ]

        check_interval = 12  # seconds between progress ticks
        step_idx = 0
        while not future.done():
            await asyncio.sleep(check_interval)
            if future.done():
                break
            if step_idx < len(progress_steps):
                pct, stage, msg = progress_steps[step_idx]
                job.stage = stage
                await emit("stage_start", stage=stage, message=msg)
                await emit("progress", progress=pct, stage=stage)
                step_idx += 1

        # Retrieve result (re-raises any exception from the thread)
        artifacts = await future

        # ── Extract report markdown ────────────────────────────────────────
        report_markdown: str = artifacts.get("markdown", "")
        word_count: int = artifacts.get("word_count", 0)

        # Fallback: reconstruct from variable space
        if not report_markdown:
            pipeline_obj = None  # pipeline is in thread scope; use artifact uid
            report_uid = artifacts.get("report_uid")
            if report_uid:
                # Best effort — may not have the pipeline reference here
                pass

        # ── Save report to dedicated reports/ folder ───────────────────────
        ticker = request.stock_code.upper()
        report_filename = f"{job_id}_{ticker}_report.md"
        report_path = _REPORTS_DIR / report_filename

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_markdown or "# Report generation completed but no content was returned.\n")

        # Last-resort fallback: if markdown is still empty, read from file
        if not report_markdown:
            try:
                report_markdown = report_path.read_text(encoding="utf-8")
                word_count = len(report_markdown.split())
            except Exception:
                pass

        job.report_path = str(report_path)
        job.status = "done"
        job.progress = 100

        await emit("stage_done", stage="report_generation", progress=100)
        await emit("complete", progress=100,
                   report_path=str(report_path),
                   word_count=word_count,
                   message=f"Report ready — {word_count:,} words")

    except Exception as e:
        import traceback
        job.status = "failed"
        job.error = str(e)
        await emit("error", error=str(e), detail=traceback.format_exc()[-500:])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
