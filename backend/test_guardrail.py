"""Automated tests for the zero-trust grounding guardrail.

Run with:  python -m pytest test_guardrail.py -v
       or: python test_guardrail.py            (standalone, no pytest needed)

Tests cover the exact scenarios from the task spec plus extra edge cases:
  - Fake certification ("Playstation")
  - Fake cert code ("ICO 1562")
  - Fabricated MOQ (120 units when source has no MOQ)
  - Fabricated lead time (10 Days when source has none)
  - Valid certification passes through
  - Valid MOQ passes through
  - Contradictory missing_specs
  - Nonsense certification ("Rainbow Sparkle Level 5")
  - Multiple fabrications in one output
  - Clean output with no fabrications
"""

import sys

from guardrail import find_unverified_claims


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

# A realistic gaming-console listing with NO certifications, NO MOQ,
# NO lead time mentioned anywhere.
GAMING_SOURCE = (
    "Latest Generation Gaming Console - Immersive Entertainment System. "
    "Experience next-level gaming with our powerful gaming console. Features "
    "ultra-fast SSD storage, ray tracing graphics, 4K HDR output, and "
    "wireless controller included. Compatible with thousands of games. "
    "Available in Midnight Black and Cosmic White. Free shipping on bulk "
    "orders. Contact us for wholesale pricing."
)

# A garment listing that DOES mention real specs.
GARMENT_SOURCE = (
    "Premium Cotton T-Shirt - 180 GSM Combed Cotton, ISO 9001 Certified "
    "Manufacturing. Available in S/M/L/XL. Minimum order quantity 500 pieces. "
    "Lead time 15-20 working days. OEKO-TEX Standard 100 compliant fabric."
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _has_flag(flags, field=None, value=None):
    """Check if any flag matches the given field and/or value (case-insensitive)."""
    for f in flags:
        field_match = field is None or f["field"].lower() == field.lower()
        value_match = value is None or value.lower() in f["claimed_value"].lower()
        if field_match and value_match:
            return True
    return False


def _flag_count(flags):
    return len(flags)


# ---------------------------------------------------------------------------
# Test 1: Fake certification "Playstation" is flagged
# ---------------------------------------------------------------------------

def test_fake_certification_playstation():
    """When the LLM invents 'Playstation' as a certification for a gaming
    console listing that mentions NO certifications, it must be flagged."""
    llm_result = {
        "rewritten_title": "Premium Gaming Console - Immersive Entertainment",
        "rewritten_description": (
            "Experience next-level gaming. Certifications: Playstation. "
            "Ultra-fast SSD, 4K HDR, wireless controller included."
        ),
        "extracted_specs": {
            "moq": None,
            "lead_time": None,
            "certifications": "Playstation",
            "quality_claims": None,
        },
        "missing_specs": ["MOQ", "Lead time"],
    }

    flags = find_unverified_claims(
        rewritten_title=llm_result["rewritten_title"],
        rewritten_description=llm_result["rewritten_description"],
        original_listing=GAMING_SOURCE,
        structured={},
        required_specs=["MOQ", "Lead time", "Certifications"],
        llm_result=llm_result,
    )

    assert _has_flag(flags, field="Certifications", value="Playstation"), (
        f"Expected 'Playstation' to be flagged as unverified. Got: {flags}"
    )
    print("PASS: test_fake_certification_playstation")


# ---------------------------------------------------------------------------
# Test 2: Fake cert code "ICO 1562" is flagged
# ---------------------------------------------------------------------------

def test_fake_cert_code_ico_1562():
    """A made-up certification code 'ICO 1562' (not ISO, not any real prefix)
    must be flagged when the source text has no certifications."""
    llm_result = {
        "rewritten_title": "Gaming Console Pro",
        "rewritten_description": (
            "High-performance gaming system. ICO 1562 Certified. "
            "Features 4K graphics and SSD storage."
        ),
        "extracted_specs": {
            "moq": None,
            "lead_time": None,
            "certifications": "ICO 1562",
            "quality_claims": None,
        },
        "missing_specs": ["MOQ", "Lead time"],
    }

    flags = find_unverified_claims(
        rewritten_title=llm_result["rewritten_title"],
        rewritten_description=llm_result["rewritten_description"],
        original_listing=GAMING_SOURCE,
        structured={},
        required_specs=["MOQ", "Lead time", "Certifications"],
        llm_result=llm_result,
    )

    assert _has_flag(flags, value="ICO 1562") or _has_flag(flags, value="ICO"), (
        f"Expected 'ICO 1562' to be flagged. Got: {flags}"
    )
    print("PASS: test_fake_cert_code_ico_1562")


# ---------------------------------------------------------------------------
# Test 3: Fabricated MOQ (120 units) is flagged
# ---------------------------------------------------------------------------

def test_fabricated_moq():
    """When the source text says nothing about MOQ and the LLM invents
    'MOQ: 120 units', it must be flagged."""
    llm_result = {
        "rewritten_title": "Gaming Console - Premium Entertainment System",
        "rewritten_description": (
            "Next-gen gaming console with 4K HDR. MOQ: 120 units. "
            "Wireless controller included. Contact for pricing."
        ),
        "extracted_specs": {
            "moq": "120 units",
            "lead_time": None,
            "certifications": None,
            "quality_claims": None,
        },
        "missing_specs": ["Lead time", "Certifications"],
    }

    flags = find_unverified_claims(
        rewritten_title=llm_result["rewritten_title"],
        rewritten_description=llm_result["rewritten_description"],
        original_listing=GAMING_SOURCE,
        structured={},
        required_specs=["MOQ", "Lead time", "Certifications"],
        llm_result=llm_result,
    )

    assert _has_flag(flags, field="MOQ", value="120"), (
        f"Expected 'MOQ: 120 units' to be flagged. Got: {flags}"
    )
    print("PASS: test_fabricated_moq")


# ---------------------------------------------------------------------------
# Test 4: Fabricated lead time is flagged
# ---------------------------------------------------------------------------

def test_fabricated_lead_time():
    """A fabricated 'Lead Time: 10 Days' when the source has no lead time
    mentioned must be caught."""
    llm_result = {
        "rewritten_title": "Gaming Console Bundle",
        "rewritten_description": (
            "Premium gaming system. Lead Time: 10 Days. "
            "4K HDR graphics, SSD storage."
        ),
        "extracted_specs": {
            "moq": None,
            "lead_time": "10 Days",
            "certifications": None,
            "quality_claims": None,
        },
        "missing_specs": ["MOQ", "Certifications"],
    }

    flags = find_unverified_claims(
        rewritten_title=llm_result["rewritten_title"],
        rewritten_description=llm_result["rewritten_description"],
        original_listing=GAMING_SOURCE,
        structured={},
        required_specs=["MOQ", "Lead time", "Certifications"],
        llm_result=llm_result,
    )

    assert _has_flag(flags, field="Lead Time", value="10"), (
        f"Expected 'Lead Time: 10 Days' to be flagged. Got: {flags}"
    )
    print("PASS: test_fabricated_lead_time")


# ---------------------------------------------------------------------------
# Test 5: Valid certification passes through (no false positive)
# ---------------------------------------------------------------------------

def test_valid_certification_passes():
    """When the source text DOES mention 'ISO 9001' and the LLM outputs it,
    it should NOT be flagged."""
    llm_result = {
        "rewritten_title": "Premium Cotton T-Shirt - ISO 9001 Certified",
        "rewritten_description": (
            "High-quality 180 GSM combed cotton t-shirt. ISO 9001 Certified "
            "manufacturing. OEKO-TEX Standard 100 compliant. Available in "
            "S/M/L/XL. MOQ 500 pieces."
        ),
        "extracted_specs": {
            "moq": "500 pieces",
            "lead_time": "15-20 working days",
            "certifications": "ISO 9001, OEKO-TEX Standard 100",
            "quality_claims": None,
        },
        "missing_specs": [],
    }

    flags = find_unverified_claims(
        rewritten_title=llm_result["rewritten_title"],
        rewritten_description=llm_result["rewritten_description"],
        original_listing=GARMENT_SOURCE,
        structured={},
        required_specs=["MOQ", "Lead time", "Certifications"],
        llm_result=llm_result,
    )

    # ISO 9001 and OEKO-TEX should NOT be flagged — they're in the source
    assert not _has_flag(flags, field="Certifications", value="ISO 9001"), (
        f"ISO 9001 should NOT be flagged — it's in the source. Got: {flags}"
    )
    print("PASS: test_valid_certification_passes")


# ---------------------------------------------------------------------------
# Test 6: Valid MOQ passes through (no false positive)
# ---------------------------------------------------------------------------

def test_valid_moq_passes():
    """When the source mentions 'Minimum order quantity 500 pieces' and the
    LLM outputs 'MOQ 500 pieces', it should NOT be flagged."""
    llm_result = {
        "rewritten_title": "Premium Cotton T-Shirt",
        "rewritten_description": (
            "180 GSM combed cotton. MOQ 500 pieces. "
            "Lead time 15-20 working days."
        ),
        "extracted_specs": {
            "moq": "500 pieces",
            "lead_time": "15-20 working days",
            "certifications": "ISO 9001",
            "quality_claims": None,
        },
        "missing_specs": [],
    }

    flags = find_unverified_claims(
        rewritten_title=llm_result["rewritten_title"],
        rewritten_description=llm_result["rewritten_description"],
        original_listing=GARMENT_SOURCE,
        structured={},
        required_specs=["MOQ", "Lead time", "Certifications"],
        llm_result=llm_result,
    )

    assert not _has_flag(flags, field="MOQ", value="500"), (
        f"MOQ 500 should NOT be flagged — '500' is in the source. Got: {flags}"
    )
    print("PASS: test_valid_moq_passes")


# ---------------------------------------------------------------------------
# Test 7: Contradictory missing_specs flagged
# ---------------------------------------------------------------------------

def test_contradictory_missing_specs():
    """If the LLM declares MOQ as 'missing' but the rewrite contains
    'MOQ 100', that contradiction must be flagged."""
    llm_result = {
        "rewritten_title": "Gaming Console",
        "rewritten_description": (
            "Premium gaming system. MOQ 100 units. "
            "4K HDR, SSD storage, wireless controller."
        ),
        "extracted_specs": {
            "moq": "100 units",
            "lead_time": None,
            "certifications": None,
            "quality_claims": None,
        },
        "missing_specs": ["MOQ", "Lead time", "Certifications"],
    }

    flags = find_unverified_claims(
        rewritten_title=llm_result["rewritten_title"],
        rewritten_description=llm_result["rewritten_description"],
        original_listing=GAMING_SOURCE,
        structured={},
        required_specs=["MOQ", "Lead time", "Certifications"],
        llm_result=llm_result,
    )

    # Should be flagged both as a fabricated MOQ (100 not in source) AND
    # as a contradictory missing_spec.
    assert _has_flag(flags, field="MOQ"), (
        f"Expected MOQ to be flagged (contradictory + fabricated). Got: {flags}"
    )
    print("PASS: test_contradictory_missing_specs")


# ---------------------------------------------------------------------------
# Test 8: Nonsense certification flagged
# ---------------------------------------------------------------------------

def test_nonsense_certification():
    """A completely nonsensical certification like 'Rainbow Sparkle Level 5'
    must be flagged."""
    llm_result = {
        "rewritten_title": "Gaming Console - Certified Quality",
        "rewritten_description": (
            "Next-gen gaming. Certifications: Rainbow Sparkle Level 5. "
            "4K HDR output, ultra-fast SSD."
        ),
        "extracted_specs": {
            "moq": None,
            "lead_time": None,
            "certifications": "Rainbow Sparkle Level 5",
            "quality_claims": None,
        },
        "missing_specs": ["MOQ", "Lead time"],
    }

    flags = find_unverified_claims(
        rewritten_title=llm_result["rewritten_title"],
        rewritten_description=llm_result["rewritten_description"],
        original_listing=GAMING_SOURCE,
        structured={},
        required_specs=["MOQ", "Lead time", "Certifications"],
        llm_result=llm_result,
    )

    assert _has_flag(flags, field="Certifications", value="Rainbow Sparkle Level 5"), (
        f"Expected 'Rainbow Sparkle Level 5' to be flagged. Got: {flags}"
    )
    print("PASS: test_nonsense_certification")


# ---------------------------------------------------------------------------
# Test 9: Multiple fabrications in one output
# ---------------------------------------------------------------------------

def test_multiple_fabrications():
    """When the LLM fabricates several specs at once (cert + MOQ + lead time),
    all of them must be caught."""
    llm_result = {
        "rewritten_title": "Premium Gaming Console - ISO 9942 Certified",
        "rewritten_description": (
            "High-performance gaming system. ISO 9942 Certified. "
            "MOQ: 250 units. Lead time: 7 days. "
            "4K HDR graphics, wireless controller."
        ),
        "extracted_specs": {
            "moq": "250 units",
            "lead_time": "7 days",
            "certifications": "ISO 9942",
            "quality_claims": None,
        },
        "missing_specs": [],
    }

    flags = find_unverified_claims(
        rewritten_title=llm_result["rewritten_title"],
        rewritten_description=llm_result["rewritten_description"],
        original_listing=GAMING_SOURCE,
        structured={},
        required_specs=["MOQ", "Lead time", "Certifications"],
        llm_result=llm_result,
    )

    # All three should be flagged
    assert _has_flag(flags, field="MOQ"), f"Expected MOQ to be flagged. Got: {flags}"
    assert _has_flag(flags, field="Lead Time"), f"Expected Lead Time to be flagged. Got: {flags}"
    assert _has_flag(flags, field="Certifications"), f"Expected Certifications to be flagged. Got: {flags}"
    assert _flag_count(flags) >= 3, f"Expected at least 3 flags. Got {_flag_count(flags)}: {flags}"
    print("PASS: test_multiple_fabrications")


# ---------------------------------------------------------------------------
# Test 10: Clean output — no fabrications, no false positives
# ---------------------------------------------------------------------------

def test_clean_output_no_false_positives():
    """When the LLM correctly uses only source-grounded values and marks
    missing specs as null, NOTHING should be flagged."""
    llm_result = {
        "rewritten_title": "Gaming Console - Immersive Entertainment System",
        "rewritten_description": (
            "Experience next-level gaming with ultra-fast SSD storage, "
            "ray tracing graphics, 4K HDR output. Wireless controller "
            "included. Available in Midnight Black and Cosmic White. "
            "Contact us for MOQ and lead time details."
        ),
        "extracted_specs": {
            "moq": None,
            "lead_time": None,
            "certifications": None,
            "quality_claims": None,
        },
        "missing_specs": ["MOQ", "Lead time", "Certifications"],
    }

    flags = find_unverified_claims(
        rewritten_title=llm_result["rewritten_title"],
        rewritten_description=llm_result["rewritten_description"],
        original_listing=GAMING_SOURCE,
        structured={},
        required_specs=["MOQ", "Lead time", "Certifications"],
        llm_result=llm_result,
    )

    assert _flag_count(flags) == 0, (
        f"Expected zero flags for clean output. Got {_flag_count(flags)}: {flags}"
    )
    print("PASS: test_clean_output_no_false_positives")


# ---------------------------------------------------------------------------
# Runner (works with and without pytest)
# ---------------------------------------------------------------------------

ALL_TESTS = [
    test_fake_certification_playstation,
    test_fake_cert_code_ico_1562,
    test_fabricated_moq,
    test_fabricated_lead_time,
    test_valid_certification_passes,
    test_valid_moq_passes,
    test_contradictory_missing_specs,
    test_nonsense_certification,
    test_multiple_fabrications,
    test_clean_output_no_false_positives,
]


def main():
    passed = 0
    failed = 0
    for test_fn in ALL_TESTS:
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test_fn.__name__} — {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test_fn.__name__} — {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    if failed:
        sys.exit(1)
    else:
        print("All tests passed!")


if __name__ == "__main__":
    main()
