"""Apify client — pulls comparable IndiaMART listings for competitive
context, cached per category to stretch a limited free-tier credit across
real traffic instead of re-scraping on every single request."""

import time
from typing import Any, Dict, List, Tuple

import httpx

from config import APIFY_ACTOR, APIFY_RESULTS_PER_QUERY, APIFY_TOKEN, CACHE_TTL_SECONDS, INDIAMART_CATEGORY_MAP

# In-memory cache: {category: {"data": [...], "fetched_at": float}}.
# Resets on restart, doesn't share across multiple server instances — swap
# for Redis if you outgrow a single instance.
_comparable_listings_cache: Dict[str, Dict[str, Any]] = {}


async def _run_indiamart_actor(category: str) -> List[Dict[str, str]]:
    """One real Apify call — only invoked on a cache miss."""
    search_query = f"{category} supplier"
    indiamart_category = INDIAMART_CATEGORY_MAP.get(category, "all")

    run_url = (
        f"https://api.apify.com/v2/actors/{APIFY_ACTOR}"
        f"/run-sync-get-dataset-items?token={APIFY_TOKEN}"
    )

    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            run_url,
            json={
                "queries": [search_query],
                "category": indiamart_category,
                "maxResultsPerQuery": APIFY_RESULTS_PER_QUERY,
            },
        )

    if response.status_code >= 400:
        raise RuntimeError(f"Apify request failed ({response.status_code}): {response.text[:300]}")

    rows = response.json()

    results: List[Dict[str, str]] = []
    for row in rows:
        company = row.get("company_name") or ""
        product = row.get("product_name") or ""
        if not company and not product:
            continue
        title = f"{company} — {product}" if company and product else (company or product)

        parts = []
        if row.get("price"):
            parts.append(f"price {row['price']}")
        if row.get("moq"):
            parts.append(f"MOQ {row['moq']}")
        if row.get("location"):
            parts.append(f"located in {row['location']}")
        if row.get("gst_number"):
            parts.append("GST-verified")
        if row.get("supplier_rating"):
            rc = row.get("rating_count")
            parts.append(f"rated {row['supplier_rating']}" + (f" ({rc} reviews)" if rc else ""))
        snippet = ", ".join(parts) if parts else "No further public details listed."

        results.append({"title": title, "snippet": snippet, "url": row.get("product_url", "")})

    seen = set()
    deduped: List[Dict[str, str]] = []
    for r in results:
        if r["title"] in seen:
            continue
        seen.add(r["title"])
        deduped.append(r)
        if len(deduped) >= 5:
            break
    return deduped


async def fetch_comparable_listings(category: str) -> Tuple[List[Dict[str, str]], bool]:
    """Returns (comparable_listings, was_cache_hit). Cached per category —
    "Garments" is scraped once and reused for every supplier analyzing a
    Garments listing, for CACHE_TTL_SECONDS."""
    cached = _comparable_listings_cache.get(category)
    if cached and (time.time() - cached["fetched_at"]) < CACHE_TTL_SECONDS:
        return cached["data"], True

    data = await _run_indiamart_actor(category)
    _comparable_listings_cache[category] = {"data": data, "fetched_at": time.time()}
    return data, False


def get_cache_snapshot() -> Dict[str, Dict[str, Any]]:
    now = time.time()
    return {
        category: {
            "item_count": len(entry["data"]),
            "age_seconds": round(now - entry["fetched_at"]),
            "expires_in_seconds": max(0, round(CACHE_TTL_SECONDS - (now - entry["fetched_at"]))),
        }
        for category, entry in _comparable_listings_cache.items()
    }


def clear_all() -> int:
    count = len(_comparable_listings_cache)
    _comparable_listings_cache.clear()
    return count


def clear_category(category: str) -> bool:
    existed = category in _comparable_listings_cache
    _comparable_listings_cache.pop(category, None)
    return existed


def cached_categories() -> List[str]:
    return list(_comparable_listings_cache.keys())