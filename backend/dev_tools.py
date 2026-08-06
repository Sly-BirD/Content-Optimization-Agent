#!/usr/bin/env python3
"""
dev_tools.py — CLI for the Listing Optimizer V3 backend.

Talks to the /api/admin/* endpoints so you don't have to hand-craft curl
commands to check cache state, LLM token usage, or recent call logs.

Setup:
    pip install httpx
    export BACKEND_URL=http://localhost:8787   # or your deployed URL
    export ADMIN_TOKEN=whatever-you-set-in-.env

Usage:
    python dev_tools.py stats
    python dev_tools.py logs                  # last 20 calls
    python dev_tools.py logs --limit 50
    python dev_tools.py cache                 # what's currently cached
    python dev_tools.py cache --clear Garments
    python dev_tools.py cache --clear-all
"""

import argparse
import os
import sys

import httpx

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8787")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")


def _client() -> httpx.Client:
    if not ADMIN_TOKEN:
        print("ADMIN_TOKEN is not set — export it (must match the backend's .env) before running this.", file=sys.stderr)
        sys.exit(1)
    return httpx.Client(base_url=BACKEND_URL, headers={"X-Admin-Token": ADMIN_TOKEN}, timeout=30)


def _die_on_error(response: httpx.Response) -> None:
    if response.status_code >= 400:
        print(f"Error {response.status_code}: {response.text}", file=sys.stderr)
        sys.exit(1)


def cmd_stats(_args) -> None:
    with _client() as client:
        r = client.get("/api/admin/stats")
        _die_on_error(r)
        s = r.json()

    print(f"Backend:            {BACKEND_URL}")
    print(f"LLM provider:       {s['llm_provider']}")
    print(f"Total calls:        {s['total_calls']}  (ok: {s['ok_calls']}, errors: {s['error_calls']})")
    print(f"Avg latency:        {s['avg_latency_ms']} ms")
    print()
    print("Token usage (successful calls only):")
    print(f"  Prompt tokens:      {s['total_prompt_tokens']:,}")
    print(f"  Completion tokens:  {s['total_completion_tokens']:,}")
    print(f"  Total tokens:       {s['total_tokens']:,}")
    print()
    print("Apify:")
    print(f"  Actor runs (real):  {s['apify_actor_runs']}")
    print(f"  Cache hits:         {s['apify_cache_hits']}")
    if s["apify_actor_runs"] + s["apify_cache_hits"] > 0:
        hit_rate = s["apify_cache_hits"] / (s["apify_actor_runs"] + s["apify_cache_hits"]) * 100
        print(f"  Cache hit rate:     {hit_rate:.0f}%  (higher = more free-tier credit saved)")
    print()
    print("Calls by category:")
    for cat, count in sorted(s["calls_by_category"].items(), key=lambda kv: -kv[1]):
        print(f"  {cat:<20} {count}")


def cmd_logs(args) -> None:
    with _client() as client:
        r = client.get("/api/admin/logs", params={"limit": args.limit})
        _die_on_error(r)
        logs = r.json()

    if not logs:
        print("No calls logged yet.")
        return

    for entry in logs:
        ts = entry.get("timestamp", "")[11:19]  # just HH:MM:SS
        status = entry.get("status", "?")
        status_flag = "OK " if status == "ok" else "ERR"
        cat = entry.get("category", "?")
        tokens = entry.get("total_tokens", 0)
        latency = entry.get("latency_ms", 0)
        cache_flag = "cache-hit" if entry.get("apify_cache_hit") else "apify-run"
        line = f"[{ts}] {status_flag}  {cat:<14} tokens={tokens:<6} {cache_flag:<10} {latency}ms"
        if status == "error":
            line += f"  ERROR: {entry.get('error', '')}"
        if entry.get("apify_error"):
            line += f"  (apify: {entry['apify_error'][:60]})"
        print(line)


def cmd_cache(args) -> None:
    with _client() as client:
        if args.clear_all:
            r = client.delete("/api/admin/cache")
            _die_on_error(r)
            print(f"Cleared {r.json()['cleared']} cached categories.")
            return

        if args.clear:
            r = client.delete(f"/api/admin/cache/{args.clear}")
            _die_on_error(r)
            result = r.json()
            print(f"'{args.clear}' — {'cleared' if result['cleared'] else 'was not cached'}")
            return

        r = client.get("/api/admin/cache")
        _die_on_error(r)
        cache = r.json()

    if not cache:
        print("Cache is empty.")
        return

    for category, info in cache.items():
        print(f"{category:<20} {info['item_count']} listings  "
              f"age={info['age_seconds']}s  expires_in={info['expires_in_seconds']}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Dev CLI for the Listing Optimizer backend")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("stats", help="Token usage and call summary").set_defaults(func=cmd_stats)

    p_logs = sub.add_parser("logs", help="Recent call log")
    p_logs.add_argument("--limit", type=int, default=20)
    p_logs.set_defaults(func=cmd_logs)

    p_cache = sub.add_parser("cache", help="Inspect or clear the comparable-listings cache")
    p_cache.add_argument("--clear", metavar="CATEGORY", help="Clear one category")
    p_cache.add_argument("--clear-all", action="store_true", help="Clear the entire cache")
    p_cache.set_defaults(func=cmd_cache)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()