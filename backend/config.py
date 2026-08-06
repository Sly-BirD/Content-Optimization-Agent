"""Config — every environment-driven setting lives here, so nothing else in
the codebase reads os.environ directly. Import from this module, don't
re-read env vars elsewhere."""

import os

from dotenv import load_dotenv

load_dotenv()

# --- LLM provider ---
# "groq" | "gemini" | "claude" | "openai" — pick whichever you have a key for.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "groq").lower()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

CURRENT_MODEL_NAME = {
    "groq": GROQ_MODEL,
    "gemini": GEMINI_MODEL,
    "claude": ANTHROPIC_MODEL,
    "openai": OPENAI_MODEL,
}.get(LLM_PROVIDER, GROQ_MODEL)

# --- Apify (IndiaMART) ---
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
APIFY_ACTOR = os.environ.get("APIFY_ACTOR", "thirdwatch~indiamart-supplier-scraper")
APIFY_RESULTS_PER_QUERY = int(os.environ.get("APIFY_RESULTS_PER_QUERY", "5"))

INDIAMART_CATEGORY_MAP = {
    "Garments": "apparel-textiles",
    "Chemicals": "chemicals-dyes",
    "Electronics": "electronics-electrical",
}

CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", str(24 * 60 * 60)))

# --- Admin / dev tools ---
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
MAX_LOG_ENTRIES = int(os.environ.get("MAX_LOG_ENTRIES", "500"))

if not APIFY_TOKEN:
    print("[warn] APIFY_TOKEN is not set — competitor scan will fail.")
_provider_keys = {"groq": GROQ_API_KEY, "gemini": GEMINI_API_KEY, "claude": ANTHROPIC_API_KEY, "openai": OPENAI_API_KEY}
if not _provider_keys.get(LLM_PROVIDER):
    print(f"[warn] LLM_PROVIDER is '{LLM_PROVIDER}' but its API key is not set — analysis will fail.")