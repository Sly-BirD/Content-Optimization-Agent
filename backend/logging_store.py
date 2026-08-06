"""In-memory call log + admin auth. Dev/debug visibility, gated behind
ADMIN_TOKEN since this is a live backend, not just a local demo."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Header, HTTPException

from config import ADMIN_TOKEN, MAX_LOG_ENTRIES

_call_logs: List[Dict[str, Any]] = []


def log_call(entry: Dict[str, Any]) -> None:
    entry["id"] = str(uuid.uuid4())[:8]
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    _call_logs.append(entry)
    if len(_call_logs) > MAX_LOG_ENTRIES:
        del _call_logs[: len(_call_logs) - MAX_LOG_ENTRIES]


def get_logs(limit: int = 50) -> List[Dict[str, Any]]:
    return list(reversed(_call_logs[-limit:]))


def get_stats() -> Dict[str, Any]:
    from config import LLM_PROVIDER  # local import avoids a circular import at module load

    ok_logs = [l for l in _call_logs if l.get("status") == "ok"]
    error_logs = [l for l in _call_logs if l.get("status") == "error"]
    cache_hits = sum(1 for l in _call_logs if l.get("apify_cache_hit"))
    apify_calls = sum(1 for l in _call_logs if l.get("apify_cache_hit") is False)
    by_category: Dict[str, int] = {}
    for l in _call_logs:
        cat = l.get("category", "unknown")
        by_category[cat] = by_category.get(cat, 0) + 1
    avg_latency = round(sum(l.get("latency_ms", 0) for l in _call_logs) / len(_call_logs)) if _call_logs else 0

    return {
        "total_calls": len(_call_logs),
        "ok_calls": len(ok_logs),
        "error_calls": len(error_logs),
        "total_prompt_tokens": sum(l.get("prompt_tokens", 0) for l in ok_logs),
        "total_completion_tokens": sum(l.get("completion_tokens", 0) for l in ok_logs),
        "total_tokens": sum(l.get("total_tokens", 0) for l in ok_logs),
        "apify_actor_runs": apify_calls,
        "apify_cache_hits": cache_hits,
        "calls_by_category": by_category,
        "avg_latency_ms": avg_latency,
        "llm_provider": LLM_PROVIDER,
    }


def require_admin(x_admin_token: Optional[str] = Header(default=None)) -> None:
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="Admin endpoints disabled — set ADMIN_TOKEN to enable.")
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Admin-Token header.")