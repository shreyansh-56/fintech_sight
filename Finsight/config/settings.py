"""Centralized configuration loader for FinSight."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)


@dataclass
class Settings:
    # LLM (Groq)
    ds_model_name: str
    ds_api_key: str
    ds_base_url: str
    
    # Writer (Groq)
    writer_model_name: str
    writer_api_key: str
    writer_base_url: str
    
    # VLM (Gemini)
    vlm_model_name: str
    vlm_api_key: str
    vlm_base_url: str
    
    # Embeddings (local)
    embedding_model_name: str
    
    # Web Search (Serper)
    serper_api_key: str
    
    # SEC Filings
    sec_user_agent: str
    
    # Macro Data (FRED)
    fred_api_key: str
    
    # Server
    port: int
    cors_origins: str
    output_dir: str
    checkpoint_dir: str


def get_settings() -> Settings:
    ds_model_name = os.getenv("DS_MODEL_NAME", "llama-3.3-70b-versatile")
    ds_api_key = os.getenv("DS_API_KEY")
    ds_base_url = os.getenv("DS_BASE_URL", "https://api.groq.com/openai/v1")
    
    writer_model_name = os.getenv("WRITER_MODEL_NAME", "llama-3.3-70b-versatile")
    writer_api_key = os.getenv("WRITER_API_KEY")
    writer_base_url = os.getenv("WRITER_BASE_URL", "https://api.groq.com/openai/v1")
    
    vlm_model_name = os.getenv("VLM_MODEL_NAME", "gemini-2.5-flash")
    vlm_api_key = os.getenv("VLM_API_KEY")
    vlm_base_url = os.getenv("VLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai")
    
    embedding_model_name = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
    
    serper_api_key = os.getenv("SERPER_API_KEY")
    sec_user_agent = os.getenv("SEC_USER_AGENT")
    fred_api_key = os.getenv("FRED_API_KEY")
    
    port = int(os.getenv("PORT", "8000"))
    cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    output_dir = os.getenv("OUTPUT_DIR", "./outputs")
    checkpoint_dir = os.getenv("CHECKPOINT_DIR", "./checkpoints")

    missing = [
        key
        for key, value in (
            ("DS_API_KEY", ds_api_key),
            ("WRITER_API_KEY", writer_api_key),
            ("VLM_API_KEY", vlm_api_key),
            ("SERPER_API_KEY", serper_api_key),
            ("SEC_USER_AGENT", sec_user_agent),
            ("FRED_API_KEY", fred_api_key),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Missing required environment variables for FinSight: " + ", ".join(missing)
        )

    return Settings(
        ds_model_name=ds_model_name,
        ds_api_key=ds_api_key,
        ds_base_url=ds_base_url,
        writer_model_name=writer_model_name,
        writer_api_key=writer_api_key,
        writer_base_url=writer_base_url,
        vlm_model_name=vlm_model_name,
        vlm_api_key=vlm_api_key,
        vlm_base_url=vlm_base_url,
        embedding_model_name=embedding_model_name,
        serper_api_key=serper_api_key,
        sec_user_agent=sec_user_agent,
        fred_api_key=fred_api_key,
        port=port,
        cors_origins=cors_origins,
        output_dir=output_dir,
        checkpoint_dir=checkpoint_dir,
    )
