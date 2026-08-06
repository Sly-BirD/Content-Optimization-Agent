"""Zero-trust grounding guardrail — model-agnostic fabrication detection and sanitization.

Verifies every concrete claim the LLM makes against the raw source text that
the supplier actually provided.

  1. Active removal of unverified key_specs:
     Any key_specs entry whose value does not appear verbatim (case-insensitive)
     in source text or structured specs is dropped from key_specs entirely, and its
     label is added to missing_specs.

  2. Secondary prose scanning:
     Scans rewritten_title, description_intro, rewritten_description, and
     call_to_action for fabricated numeric claims or certification tokens
     (including bare certification-word claims with no digits, e.g. "Playstation")
     not present in source text.

Exports:
  sanitize_result(result, original_listing, structured, required_specs)
  find_unverified_claims(...)
"""

import copy
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple

_FUZZY_THRESHOLD = 0.75

_KNOWN_CERT_PREFIXES: Set[str] = {
    "iso", "ce", "fcc", "ul", "rohs", "reach", "bis", "astm", "ansi",
    "iec", "en", "din", "jis", "sgs", "tuv", "bsi", "nsf", "gmp",
    "haccp", "halal", "kosher", "oeko", "gots", "fda", "epa", "emc",
    "saa", "csa", "kc", "pse", "ccc", "bsci", "sedex", "wrap", "sa",
    "ohsas", "iatf", "as", "nadcap", "mil", "nist", "ieee", "etl",
    "intertek", "weee", "epeat", "energy star", "ip", "atex", "nfpa",
    "api", "asme", "aws", "aisi", "sae",
}

_CERT_CODE_PATTERN = re.compile(
    r"\b[A-Z]{2,6}[\s\-]?\d{3,6}(?:[:\-]\d{2,4})?\b"
)

_NUMERIC_SPEC_PATTERN = re.compile(
    r"\bMOQ[:\s]*\d+[\w]*"
    r"|\b\d+(?:[\-–]\d+)?\s?(?:working\s+|business\s+)?"
    r"(?:%|days?|weeks?|months?|units?|pcs?"
    r"|pieces?|kg|g|gsm|v|volts?|amps?|watts?|hrs?|hours?)\b"
    r"|\bwithin\s+\d+\s+(?:days?|weeks?|months?|hours?)\b",
    re.IGNORECASE,
)

_CERT_PHRASE_PATTERN = re.compile(
    r"(?:certif(?:ied|ication|icate)s?\s*[:\-–]?\s*)"
    r"([A-Za-z0-9\s,/\-]+?)"
    r"(?=[.;()!\n]|\s{2,}|$)",
    re.IGNORECASE,
)

_SPEC_KEYWORDS: Dict[str, List[str]] = {
    "MOQ": ["moq", "minimum order"],
    "Lead time": ["lead time", "delivery time", "dispatch time", "shipping time"],
    "Certifications": ["certif", "certified", "certification", "certificate"],
    "Price tiers": ["price tier", "/unit", "per unit"],
    "Fabric weight (GSM)": ["gsm"],
    "Fabric composition": ["composition"],
    "Available sizing runs": ["sizing run", "size range"],
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _extract_numbers(text: str) -> Set[str]:
    return set(re.findall(r"\b\d+(?:\.\d+)?\b", text))


def _verbatim_present(needle: str, haystack: str) -> bool:
    needle_n = _normalize(needle)
    haystack_n = _normalize(haystack)
    if not needle_n:
        return True
    return needle_n in haystack_n


def _fuzzy_present(needle: str, haystack: str) -> bool:
    needle_n = _normalize(needle)
    haystack_n = _normalize(haystack)
    if not needle_n:
        return True
    if needle_n in haystack_n:
        return True
    if len(needle_n) <= 3:
        return False
    best = 0.0
    window = len(needle_n)
    for i in range(max(1, len(haystack_n) - window + 1)):
        chunk = haystack_n[i : i + window]
        ratio = SequenceMatcher(None, needle_n, chunk).ratio()
        if ratio > best:
            best = ratio
        if best >= _FUZZY_THRESHOLD:
            return True
    return False


def _is_known_cert_prefix(value: str) -> bool:
    val = _normalize(value)
    return any(val.startswith(prefix) for prefix in _KNOWN_CERT_PREFIXES)


def _split_cert_values(raw: str) -> List[str]:
    parts = re.split(r"[,;/]+", raw)
    return [p.strip() for p in parts if p.strip()]


def sanitize_result(
    result: Dict[str, Any],
    original_listing: str,
    structured: Dict[str, str],
    required_specs: Optional[List[str]] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """Sanitizes the LLM result by stripping unverified content.

    1. Any key_specs entry whose value doesn't appear verbatim in source_text
       is dropped from key_specs entirely, and its label added to missing_specs.
    2. Scans rewritten_title, description_intro, rewritten_description, and
       call_to_action for unverified numbers/cert tokens (including bare cert words like 'Playstation')
       and strips them out.
    3. Returns (clean_result, unverified_claims_list) where unverified_claims_list
       contains short "Label: value" tag strings for display in UI.
    """
    clean_result = copy.deepcopy(result or {})

    # Build full source text
    source_parts = [original_listing or ""]
    for k, v in (structured or {}).items():
        if v and str(v).strip():
            source_parts.append(f"{k} {v}")
    source_text = " ".join(source_parts)

    unverified_claims: List[str] = []
    missing_specs: Set[str] = set(clean_result.get("missing_specs", []))

    # --- 1. Sanitize key_specs ---
    raw_key_specs = clean_result.get("key_specs", [])
    valid_key_specs = []

    if isinstance(raw_key_specs, list):
        for item in raw_key_specs:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "")).strip()
            val = str(item.get("value", "")).strip()

            if not val or val.lower() in ("null", "none", "n/a", "not specified"):
                if label:
                    missing_specs.add(label)
                continue

            if _verbatim_present(val, source_text):
                valid_key_specs.append({"label": label, "value": val})
            else:
                if label:
                    missing_specs.add(label)
                claim_tag = f"{label}: {val}" if label else val
                unverified_claims.append(claim_tag)

    clean_result["key_specs"] = valid_key_specs

    # --- 2. Sanitize extracted_specs ---
    if isinstance(clean_result.get("extracted_specs"), dict):
        ext_specs = clean_result["extracted_specs"]
        for k, v in list(ext_specs.items()):
            if v is not None and str(v).strip().lower() not in ("", "null", "none", "n/a"):
                val_str = str(v).strip()
                label = k.replace("_", " ").title()
                if k in ("certifications", "safety_certifications"):
                    for cert in _split_cert_values(val_str):
                        if not _verbatim_present(cert, source_text):
                            ext_specs[k] = None
                            unverified_claims.append(f"Certifications: {cert}")
                else:
                    if not _verbatim_present(val_str, source_text):
                        ext_specs[k] = None
                        unverified_claims.append(f"{label}: {val_str}")

    # --- 3. Sanitize prose fields ---
    prose_fields = ["rewritten_title", "description_intro", "rewritten_description", "call_to_action"]
    source_numbers = _extract_numbers(source_text)

    for field in prose_fields:
        val = clean_result.get(field)
        if not val or not isinstance(val, str):
            continue

        field_clean = val

        # Check numeric spec claims
        for m in _NUMERIC_SPEC_PATTERN.finditer(val):
            token = m.group(0).strip()
            claimed_nums = _extract_numbers(token)
            ungrounded = claimed_nums - source_numbers
            if ungrounded and not _fuzzy_present(token, source_text):
                label_name = field.replace('_', ' ').title()
                if "moq" in token.lower():
                    label_name = "MOQ"
                elif any(u in token.lower() for u in ["day", "week", "month"]):
                    label_name = "Lead Time"
                unverified_claims.append(f"{label_name}: {token}")
                field_clean = field_clean.replace(token, "").strip()

        # Check cert phrases & bare cert claims (e.g. "Certifications: Playstation")
        for m in _CERT_PHRASE_PATTERN.finditer(val):
            raw_certs = m.group(1).strip()
            if len(raw_certs) > 60:
                continue
            for cert in _split_cert_values(raw_certs):
                if cert and len(cert) >= 2:
                    if not _verbatim_present(cert, source_text) and not _is_known_cert_prefix(cert):
                        unverified_claims.append(f"Certifications: {cert}")
                        field_clean = field_clean.replace(cert, "").strip()

        # Check standalone cert code pattern (e.g. ICO 1562)
        for m in _CERT_CODE_PATTERN.finditer(val):
            token = m.group(0).strip()
            if not _verbatim_present(token, source_text):
                unverified_claims.append(f"Certifications: {token}")
                field_clean = field_clean.replace(token, "").strip()

        clean_result[field] = re.sub(r"\s+", " ", field_clean).strip()

    # --- 4. Missing-spec consistency check ---
    combined_output = " ".join([str(clean_result.get(f, "")) for f in prose_fields])
    output_lower = _normalize(combined_output)
    for spec in clean_result.get("missing_specs", []):
        keywords = _SPEC_KEYWORDS.get(spec, [spec.lower()])
        for kw in keywords:
            kw_clean = kw.strip()
            match = re.search(r"\b" + re.escape(kw_clean) + r"\b", output_lower)
            if match:
                idx = match.start()
                context_before = output_lower[max(0, idx - 60):idx]
                if not any(dp in context_before for dp in ("contact us for", "inquire about", "ask about", "not specified", "n/a")):
                    unverified_claims.append(f"{spec}: (present in rewrite despite missing)")

    # Deduplicate unverified claims while preserving tag strings
    seen_claims: Set[str] = set()
    deduped_claims: List[str] = []
    for claim in unverified_claims:
        norm = _normalize(claim)
        if norm and norm not in seen_claims:
            seen_claims.add(norm)
            deduped_claims.append(claim)

    clean_result["missing_specs"] = sorted(list(missing_specs))
    clean_result["unverified_claims"] = deduped_claims

    return clean_result, deduped_claims


def find_unverified_claims(*args: Any, **kwargs: Any) -> List[Dict[str, str]]:
    """Backward compatibility wrapper for legacy callers & unit tests."""
    llm_result = kwargs.get("llm_result") or (args[0] if args and isinstance(args[0], dict) else {})
    rewritten_title = kwargs.get("rewritten_title") or llm_result.get("rewritten_title", "")
    rewritten_description = kwargs.get("rewritten_description") or llm_result.get("rewritten_description", "")
    original_listing = kwargs.get("original_listing") or (args[1] if len(args) > 1 else "")
    structured = kwargs.get("structured") or (args[2] if len(args) > 2 else {})
    required_specs = kwargs.get("required_specs") or (args[3] if len(args) > 3 else None)

    temp_result = copy.deepcopy(llm_result)
    temp_result["rewritten_title"] = rewritten_title
    temp_result["rewritten_description"] = rewritten_description

    clean_res, claim_strings = sanitize_result(temp_result, original_listing, structured, required_specs)

    # Format output as dicts for test_guardrail.py
    structured_flags = []
    for claim in claim_strings:
        if ":" in claim:
            parts = claim.split(":", 1)
            structured_flags.append({"field": parts[0].strip(), "claimed_value": parts[1].strip(), "reason": "Unverified"})
        else:
            structured_flags.append({"field": "Claim", "claimed_value": claim.strip(), "reason": "Unverified"})
    return structured_flags
