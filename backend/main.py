"""V3 backend — Listing Optimizer.

main.py is intentionally thin: it wires together four focused modules and
exposes the routes. If you're looking for the actual logic:

  config.py          — every environment-driven setting
  llm_providers.py    — prompt, JSON parsing, and the 4 provider callers
  apify_client.py      — IndiaMART scraping + category-level cache
  guardrail.py         — fabrication detection & sanitization (zero-trust)
  logging_store.py     — call log + admin auth
"""

import time
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import apify_client
import logging_store
from config import APIFY_ACTOR, CACHE_TTL_SECONDS, CURRENT_MODEL_NAME, LLM_PROVIDER
from guardrail import sanitize_result
from llm_providers import build_user_message, call_llm

app = FastAPI(title="Listing Optimizer V3 Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://content-optimization-agent.vercel.app/"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    category: str
    listing: str
    structured: Dict[str, str] = Field(default_factory=dict)
    requiredSpecs: List[str] = Field(default_factory=list)
    includeCompetitive: bool = True


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    if not req.listing or not req.category:
        raise HTTPException(status_code=400, detail="category and listing are required")

    start = time.time()
    comparable_listings: List[Dict[str, str]] = []
    competitive_error: Optional[str] = None
    cache_hit = False

    if req.includeCompetitive:
        try:
            comparable_listings, cache_hit = await apify_client.fetch_comparable_listings(req.category)
        except Exception as err:
            competitive_error = str(err)

    user_message = build_user_message(
        req.category, req.listing, req.structured, req.requiredSpecs, comparable_listings
    )

    try:
        raw_result, token_usage = await call_llm(user_message)
    except Exception as err:
        logging_store.log_call({
            "category": req.category,
            "llm_provider": LLM_PROVIDER,
            "status": "error",
            "error": str(err),
            "apify_cache_hit": cache_hit,
            "apify_error": competitive_error,
            "latency_ms": round((time.time() - start) * 1000),
        })
        raise HTTPException(status_code=500, detail=f"LLM call failed: {err}")

    # --- Zero-trust guardrail sanitization ---
    sanitized_result, unverified_claims = sanitize_result(
        result=raw_result,
        original_listing=req.listing,
        structured=req.structured,
        required_specs=req.requiredSpecs,
    )

    # --- Logging ---
    logging_store.log_call({
        "category": req.category,
        "llm_provider": LLM_PROVIDER,
        "llm_model": CURRENT_MODEL_NAME,
        "status": "ok",
        "prompt_tokens": token_usage.get("prompt_tokens", 0),
        "completion_tokens": token_usage.get("completion_tokens", 0),
        "total_tokens": token_usage.get("total_tokens", 0),
        "apify_cache_hit": cache_hit,
        "apify_error": competitive_error,
        "comparable_count": len(comparable_listings),
        "unverified_claim_count": len(unverified_claims),
        "latency_ms": round((time.time() - start) * 1000),
    })

    # --- Attach competitive scan details to the SANITIZED result ---
    sanitized_result["comparable_listings"] = comparable_listings
    sanitized_result["competitive_error"] = competitive_error

    return sanitized_result


@app.get("/health")
async def health():
    return {
        "ok": True,
        "llm_provider": LLM_PROVIDER,
        "llm_model": CURRENT_MODEL_NAME,
        "apify_actor": APIFY_ACTOR,
        "cached_categories": apify_client.cached_categories(),
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
    }


# --- Admin / dev endpoints — gated behind X-Admin-Token ---

@app.get("/api/admin/logs")
async def admin_logs(limit: int = 50, admin: None = Depends(logging_store.require_admin)):
    return logging_store.get_logs(limit)


@app.get("/api/admin/stats")
async def admin_stats(admin: None = Depends(logging_store.require_admin)):
    return logging_store.get_stats()


@app.get("/api/admin/cache")
async def admin_get_cache(admin: None = Depends(logging_store.require_admin)):
    return apify_client.get_cache_snapshot()


@app.delete("/api/admin/cache")
async def admin_clear_all_cache(admin: None = Depends(logging_store.require_admin)):
    return {"cleared": apify_client.clear_all()}


@app.delete("/api/admin/cache/{category}")
async def admin_clear_category_cache(category: str, admin: None = Depends(logging_store.require_admin)):
    return {"cleared": apify_client.clear_category(category), "category": category}
