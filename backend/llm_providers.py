"""LLM providers — one shared prompt/schema, four interchangeable backends.

LLM_PROVIDER in config picks which one call_llm() actually uses. All four
return the same (parsed_json_dict, token_usage_dict) shape, so nothing else
in the codebase needs to know or care which provider is active.
"""

import json
import re
from typing import Any, Dict, List, Tuple

import httpx

from config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
    LLM_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)

SYSTEM_PROMPT = """\
You are a B2B listing copywriter and auditor for an industrial supplier marketplace. Buyers search on concrete specs, not prose.

═══ YOUR TWO SOURCES OF TRUTH ═══
  A. "Current listing text" — the supplier's raw description.
  B. "Structured specs provided by supplier" — explicit key-value pairs.
You may rephrase, restructure, and improve readability, but you MUST NOT add any specification, number, certification, material detail, or factual claim that does not appear verbatim in A or B.

═══ COMPARABLE LISTINGS — READ-ONLY ═══
The "Comparable listings" section is for your competitive analysis ONLY.
• Use it to write competitive_notes (how the user's listing stacks up).
• NEVER copy, paraphrase, merge, or inject any data from comparable listings into the rewritten fields. Treat them as sealed reference documents.

═══ TASK ═══

1. SCORE the listing against six criteria (0-10 each). Each note ≤ 15 words:
   title_clarity, spec_completeness, keyword_coverage, trust_signals, scannability, call_to_action.
   spec_completeness should reflect how many required-spec checklist items are actually present.

2. EXTRACT structured specs into extracted_specs. Rules:
   • Only extract values LITERALLY present in source A or B. If absent → null.
   • Never fabricate. null is always correct when in doubt.

3. REWRITE the listing into four separate structured fields using ONLY facts from A and B, applying professional B2B copywriting principles:

   • rewritten_title: Front-load the highest-value B2B search keywords (material/product type + category) that a buyer would filter by. Keep it scannable.
     Example format: "[Primary Material/Product Keyword] — [Key Verified Specs or Differentiators]"

   • description_intro: Establish a compelling B2B value proposition in the first sentence (e.g. referencing verified source facts like years in business, size range, or custom capabilities). Avoid generic fluff or invented superlatives ("industry-leading", "world-class") unless explicitly stated in A/B.

   • key_specs: Array of objects {"label": "...", "value": "..."} for ONLY specs that exist verbatim in A or B.
     ORDER MATTERS: Prioritize primary B2B decision specs first (MOQ, Lead time, Certifications, Price tiers) before secondary or category-specific technical specs. Omit any spec absent from A/B.

   • call_to_action: Prompt a specific, high-converting B2B next step (e.g., "Request a quote for bulk pricing", "Inquire for custom volume orders and spec sheets") rather than a generic "Contact us."

   CRITICAL: If a spec is absent from A and B, do NOT write it into key_specs, do NOT guess, do NOT placeholder it. Omit it entirely from key_specs and list it in missing_specs.

4. COMPARE against comparable listings → produce 2-4 competitive_notes.
   Reference only things actually present in the comparables given.

5. SELF-AUDIT: List any claim in your output you are uncertain about in unverified_claims.

═══ COPYWRITING EXAMPLES (FACTS-GROUNDED B2B COPY) ═══

Example 1:
- Source A: "We make cotton t-shirts in all sizes. 10 years experience. MOQ 500 pcs. Contact for price."
- Weak Rewrite:
  Title: "T-Shirts for Sale"
  Intro: "We sell cotton t-shirts and have experience."
  CTA: "Contact us."
- Professional B2B Rewrite:
  Title: "Cotton T-Shirts (Bulk Supplier) — 10 Years Manufacturing, MOQ 500 Pcs"
  Intro: "Established 10-year manufacturer supplying custom cotton t-shirts across a full size range for commercial buyers."
  CTA: "Request a custom quote or sample run for bulk orders."

Example 2:
- Source A: "ISO 9001 factory producing industrial PVC pipes. Lead time 14 days."
- Professional B2B Rewrite:
  Title: "Industrial PVC Pipes — ISO 9001 Certified Factory, 14-Day Lead Time"
  Intro: "Direct factory supplier of industrial PVC piping backed by ISO 9001 certified manufacturing quality."
  CTA: "Submit an RFQ for volume pricing and technical datasheets."

═══ WHAT NOT TO DO ═══
• Source says nothing about MOQ → you add {"label": "MOQ", "value": "120 units"} → WRONG. Omit from key_specs, add to missing_specs.
• Source says nothing about certs → you add {"label": "Certifications", "value": "GYAAT 2322 Certified"} → WRONG. Omit certs, add to missing_specs.
• Comparable listing mentions "GST verified" → you add "GST verified" to rewrite → WRONG. That's competitor data, not source data.

═══ OUTPUT FORMAT ═══
Respond with STRICT JSON ONLY. No markdown fences, no commentary outside the JSON object.
{"criteria":[{"key":"title_clarity","label":"Title Clarity","score":0,"note":""},{"key":"spec_completeness","label":"Spec Completeness","score":0,"note":""},{"key":"keyword_coverage","label":"Keyword Coverage","score":0,"note":""},{"key":"trust_signals","label":"Trust Signals","score":0,"note":""},{"key":"scannability","label":"Scannability","score":0,"note":""},{"key":"call_to_action","label":"Call To Action","score":0,"note":""}],"extracted_specs":{"moq":null,"lead_time":null,"certifications":null,"quality_claims":null},"missing_specs":[""],"rewritten_title":"","description_intro":"","key_specs":[{"label":"","value":""}],"call_to_action":"","changelog":[""],"competitive_notes":[""],"unverified_claims":[]}"""


def build_user_message(
    category: str,
    listing: str,
    structured: Dict[str, str],
    required_specs: List[str],
    comparable_listings: List[Dict[str, str]],
) -> str:
    structured_lines = "\n".join(f"- {k}: {v}" for k, v in structured.items() if v and v.strip())
    comparable_block = (
        "\n".join(f"{i+1}. {c['title']} — {c['snippet']}" for i, c in enumerate(comparable_listings))
        if comparable_listings
        else "(none available)"
    )
    return f"""Category: {category}

Required-spec checklist for this category: {", ".join(required_specs)}

Structured specs provided by supplier:
{structured_lines or "(none provided)"}

Current listing text:
{listing}

Comparable listings found on the web:
{comparable_block}"""


def extract_json(raw_text: str) -> Dict[str, Any]:
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```json", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^```", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as err:
        preview = cleaned[:200] + ("..." if len(cleaned) > 200 else "")
        raise ValueError(f"Model did not return valid JSON ({err}). Response started with: {preview!r}")


async def call_groq(user_message: str) -> Tuple[Dict[str, Any], Dict[str, int]]:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "max_tokens": 1200,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
            },
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Groq request failed ({response.status_code}): {response.text[:300]}")
    data = response.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    token_usage = {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }
    return extract_json(text), token_usage


async def call_gemini(user_message: str) -> Tuple[Dict[str, Any], Dict[str, int]]:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    generation_config: Dict[str, Any] = {
        "maxOutputTokens": 2048,
        "temperature": 0.4,
        "responseMimeType": "application/json",
    }
    if "2.5" in GEMINI_MODEL:
        generation_config["thinkingConfig"] = {"thinkingBudget": 0}

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            url,
            json={
                "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": [{"role": "user", "parts": [{"text": user_message}]}],
                "generationConfig": generation_config,
            },
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Gemini request failed ({response.status_code}): {response.text[:300]}")
    data = response.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        finish_reason = data.get("candidates", [{}])[0].get("finishReason", "unknown")
        raise RuntimeError(f"Gemini returned no text (finishReason={finish_reason}): {json.dumps(data)[:300]}")
    usage = data.get("usageMetadata", {})
    token_usage = {
        "prompt_tokens": usage.get("promptTokenCount", 0),
        "completion_tokens": usage.get("candidatesTokenCount", 0),
        "total_tokens": usage.get("totalTokenCount", 0),
    }
    return extract_json(text), token_usage


async def call_claude(user_message: str) -> Tuple[Dict[str, Any], Dict[str, int]]:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": ANTHROPIC_MODEL,
                "max_tokens": 1500,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_message}],
            },
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Claude request failed ({response.status_code}): {response.text[:300]}")
    data = response.json()
    text_block = next((b for b in data.get("content", []) if b.get("type") == "text"), None)
    if not text_block:
        raise RuntimeError("Claude returned no text content")
    usage = data.get("usage", {})
    token_usage = {
        "prompt_tokens": usage.get("input_tokens", 0),
        "completion_tokens": usage.get("output_tokens", 0),
        "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
    }
    return extract_json(text_block["text"]), token_usage


async def call_openai(user_message: str) -> Tuple[Dict[str, Any], Dict[str, int]]:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": OPENAI_MODEL,
                "max_tokens": 1500,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
            },
        )
    if response.status_code >= 400:
        raise RuntimeError(f"OpenAI request failed ({response.status_code}): {response.text[:300]}")
    data = response.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    token_usage = {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }
    return extract_json(text), token_usage


_PROVIDERS = {"groq": call_groq, "gemini": call_gemini, "claude": call_claude, "openai": call_openai}


async def call_llm(user_message: str) -> Tuple[Dict[str, Any], Dict[str, int]]:
    provider_fn = _PROVIDERS.get(LLM_PROVIDER, call_groq)
    return await provider_fn(user_message)
