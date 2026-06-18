"""
detect_gap.py
Scans the Accessibility policy text for the confirmed ADA jurisdiction error.
Returns the offending passage if found.
"""


# The wrong reference we're looking for
WRONG_REFERENCES = [
    "Americans with Disabilities Act",
    "ADA",
    "Americans With Disabilities",
]

# What it should say
CORRECT_REFERENCE = "Equality Act 2010"


def detect_ada_error(policy_text: str) -> dict:
    """
    Scan policy text for US ADA references.
    Returns a result dict with found=True/False and the offending excerpt.
    """
    policy_lower = policy_text.lower()

    for wrong_ref in WRONG_REFERENCES:
        if wrong_ref.lower() in policy_lower:
            # Find the surrounding context (200 chars either side)
            idx = policy_lower.find(wrong_ref.lower())
            start = max(0, idx - 200)
            end = min(len(policy_text), idx + len(wrong_ref) + 200)
            excerpt = policy_text[start:end].strip()

            return {
                "found": True,
                "wrong_reference": wrong_ref,
                "correct_reference": CORRECT_REFERENCE,
                "excerpt": excerpt,
                "gap_type": "wrong_jurisdiction",
                "severity": "High",
                "description": (
                    f"Policy references '{wrong_ref}' — a US law. "
                    f"Elevate operates in England. The correct legislation is the {CORRECT_REFERENCE}. "
                    "This would be flagged immediately by any school or Ofsted inspector."
                ),
            }

    return {
        "found": False,
        "description": "No ADA jurisdiction error detected in this policy.",
    }


def detect_gap(policy_text: str) -> dict:
    """Alias for detect_ada_error — main entry point."""
    return detect_ada_error(policy_text)


if __name__ == "__main__":
    # Quick test with sample text
    sample = """
    Elevate Performance Academy is committed to accessibility for all participants.
    In accordance with the Americans with Disabilities Act, we ensure that all
    facilities are accessible to individuals with disabilities.
    """
    result = detect_gap(sample)
    print(result)
