"""Gemini API client wrapper for FinSight tools and agents."""
from __future__ import annotations

import time
from typing import Any, Dict, Sequence

from Finsight.tools.unified_llm_client import UnifiedLLMClient, _is_error_response


class GeminiClient:
    """
    High-level client used by EnhancedReportWriter and agents.

    Text generation strategy:
        generate()          → Gemini 2.5 Flash (primary, no daily token limit)
                              → Groq llama-3.3-70b-versatile (fallback 1)
                              → Groq llama-3.1-8b-instant (fallback 2)
                              → Groq gemma2-9b-it (fallback 3)
        generate_multimodal() → Gemini VLM (OpenAI-compatible endpoint)
    """

    def __init__(self, model_name: str = "vlm") -> None:
        self._vlm = UnifiedLLMClient(model_type="vlm")      # Gemini (for multimodal)
        self._writer = UnifiedLLMClient(model_type="writer") # Groq (for structured JSON)
        self.model_name = model_name

        # Groq fallback models in priority order (all currently active on Groq)
        self._groq_fallbacks = [
            "llama-3.3-70b-versatile", # Groq production — 100k tokens/day
            "llama-3.1-8b-instant",    # Groq production — 500k tokens/day
            "gemma2-9b-it",            # Groq Google model — backup
        ]

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        Text-only generation.
        PRIMARY: Gemini 2.5 Flash (no token-per-day cap)
        FALLBACK 1: Groq llama-3.3-70b-versatile
        FALLBACK 2: Groq llama-3.1-8b-instant
        FALLBACK 3: Groq gemma2-9b-it
        """
        # 1. Try Gemini Flash
        try:
            result = self._vlm.generate(prompt, **kwargs)
            if result and not _is_error_response(result) and len(result.split()) > 20:
                return result
        except Exception:
            pass

        # 2. Try Groq fallbacks
        for model in self._groq_fallbacks:
            result = self._vlm._call_model(prompt, model, max_tokens=kwargs.get("max_tokens", 4096))
            if result and not _is_error_response(result) and len(result.split()) > 20:
                return result

        # 3. Last resort — empty (caller handles)
        return ""

    def generate_structured(self, prompt: str, mime_type: str = "application/json", **kwargs: Any) -> Dict[str, Any]:
        """Structured JSON generation — try Gemini, fall back to Groq."""
        # Try Gemini via write_section (JSON instruction appended)
        json_prompt = prompt + "\n\nRespond with valid JSON only. No markdown code blocks."
        try:
            result = self._vlm.generate(json_prompt, **kwargs)
            if result and not _is_error_response(result):
                import json
                try:
                    # Strip markdown fences if present
                    text = result.strip()
                    if text.startswith("```"):
                        text = text.split("```")[1]
                        if text.startswith("json"):
                            text = text[4:]
                    return json.loads(text.strip())
                except Exception:
                    pass
        except Exception:
            pass

        # Groq writer fallback
        try:
            return self._writer.generate_structured(prompt, **kwargs)
        except Exception:
            return {}

    def function_call(self, prompt: str, tools: Sequence[Dict[str, Any]]) -> Any:
        return self.generate(prompt)

    def generate_multimodal(self, parts: Sequence[Any], **kwargs: Any) -> str:
        """Multimodal (image + text) via Gemini VLM with rate-limit retry."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = self._vlm.generate_multimodal(parts, **kwargs)
                if result and not _is_error_response(result):
                    return result
            except Exception as e:
                err = str(e)
                if any(kw in err for kw in ("ResourceExhausted", "429", "RESOURCE_EXHAUSTED", "rate")):
                    wait = min(35 * (attempt + 1), 5)  # cap at 5 seconds
                    time.sleep(wait)
                else:
                    # Non-rate-limit error → text fallback
                    break

        # Final text-only fallback
        text_parts = [p for p in parts if isinstance(p, str)]
        return self.generate(" ".join(text_parts))
