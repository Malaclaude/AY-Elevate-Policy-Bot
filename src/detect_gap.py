"""
detect_gap.py
Scans Elevate's policy corpus for compliance gaps across all monitored sources.
Every finding is anchored to an official UK regulatory source URL.
"""

# ─────────────────────────────────────────────
# Official source registry — every finding must reference one of these
# ─────────────────────────────────────────────
SOURCES = {
    "equality_act_2010": {
        "name": "Equality Act 2010",
        "url": "https://www.gov.uk/guidance/equality-act-2010-guidance",
    },
    "working_together_2023": {
        "name": "Working Together to Safeguard Children 2023",
        "url": "https://www.gov.uk/government/publications/working-together-to-safeguard-children--2",
    },
    "kcsie_2024": {
        "name": "Keeping Children Safe in Education 2024",
        "url": "https://www.gov.uk/government/publications/keeping-children-safe-in-education--2",
    },
    "children_act": {
        "name": "Children Act 1989 and 2004",
        "url": "https://www.legislation.gov.uk/ukpga/2004/31/contents",
    },
    "hse": {
        "name": "HSE — Health and Safety at Work",
        "url": "https://www.hse.gov.uk/legislation/hswa.htm",
    },
    "ico_gdpr": {
        "name": "ICO / UK GDPR Guidance",
        "url": "https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/",
    },
    "ico_childrens_code": {
        "name": "ICO Children's Code (Age Appropriate Design Code)",
        "url": "https://ico.org.uk/for-organisations/childrens-code/",
    },
    "dbs": {
        "name": "DBS — Disclosure and Barring Service",
        "url": "https://www.gov.uk/government/organisations/disclosure-and-barring-service",
    },
    "nspcc_cpsu": {
        "name": "NSPCC Child Protection in Sport Unit",
        "url": "https://thecpsu.org.uk/",
    },
    "ofsted_exemptions": {
        "name": "Ofsted Childcare Registration Exemptions",
        "url": "https://www.gov.uk/guidance/registration-exemptions",
    },
    "acas": {
        "name": "ACAS Code of Practice on Disciplinary and Grievance",
        "url": "https://www.acas.org.uk/acas-code-of-practice-on-disciplinary-and-grievance-procedures",
    },
    "simply_business": {
        "name": "Simply Business — Certificate of Employers' Liability Insurance",
        "url": "https://www.simplybusiness.co.uk/",
    },
}


def _excerpt(text: str, keyword: str, window: int = 250) -> str:
    """Return text surrounding the first occurrence of keyword."""
    lower = text.lower()
    idx = lower.find(keyword.lower())
    if idx == -1:
        return ""
    start = max(0, idx - window)
    end = min(len(text), idx + len(keyword) + window)
    return text[start:end].strip()


# ─────────────────────────────────────────────
# Individual gap checks
# ─────────────────────────────────────────────

def check_ada_error(policy_text: str) -> dict | None:
    """
    Accessibility policy cites US ADA instead of UK Equality Act 2010.
    Detected by scanning the policy text.
    """
    wrong_refs = [
        "americans with disabilities act",
        "ada compliance",
        "americans with disabilities",
    ]
    policy_lower = policy_text.lower()
    for ref in wrong_refs:
        if ref in policy_lower:
            return {
                "gap_id": "ada_jurisdiction",
                "gap_type": "wrong_reference",
                "policy_name": "Accessibility and Inclusiveness Policy",
                "severity": "High",
                "source": SOURCES["equality_act_2010"],
                "wrong_reference": "Americans with Disabilities Act (ADA)",
                "correct_reference": "Equality Act 2010",
                "description": (
                    "Policy cites the Americans with Disabilities Act — a US federal law with no legal standing in England. "
                    "Elevate operates under the Equality Act 2010, which covers disability, age, race, sex, and other protected characteristics. "
                    "This would be flagged immediately by any Ofsted inspector, school safeguarding lead, or local authority."
                ),
                "original_excerpt": _excerpt(policy_text, ref),
                "detection_method": "text_scan",
            }
    return None


def check_working_together_version(policy_text: str) -> dict | None:
    """
    Safeguarding policy cites Working Together 2018 — the current statutory version is 2023.
    Detected by text scan; also included as corpus-confirmed if text is the Accessibility policy.
    """
    policy_lower = policy_text.lower()
    # Direct detection from safeguarding policy text
    if "working together" in policy_lower and "2018" in policy_lower:
        excerpt = _excerpt(policy_text, "working together")
        return {
            "gap_id": "working_together_outdated",
            "gap_type": "outdated_reference",
            "policy_name": "Safeguarding Policy",
            "severity": "High",
            "source": SOURCES["working_together_2023"],
            "wrong_reference": "Working Together to Safeguard Children 2018",
            "correct_reference": "Working Together to Safeguard Children 2023",
            "description": (
                "Policy references Working Together to Safeguard Children 2018. "
                "The 2023 edition is the current statutory safeguarding framework and supersedes all previous versions. "
                "Schools, LAs, and Ofsted check this citation — an outdated version undermines safeguarding credibility and could trigger a formal concern."
            ),
            "original_excerpt": excerpt,
            "detection_method": "text_scan",
        }

    # Corpus-confirmed: Malachi confirmed this error exists in the Safeguarding policy
    # from the manual review of Chad's corpus on 8 June 2026
    return {
        "gap_id": "working_together_outdated",
        "gap_type": "outdated_reference",
        "policy_name": "Safeguarding Policy",
        "severity": "High",
        "source": SOURCES["working_together_2023"],
        "wrong_reference": "Working Together to Safeguard Children 2018",
        "correct_reference": "Working Together to Safeguard Children 2023",
        "description": (
            "Policy references Working Together to Safeguard Children 2018. "
            "The 2023 edition is the current statutory safeguarding framework and supersedes all previous versions. "
            "Schools, LAs, and Ofsted check this citation — an outdated version undermines safeguarding credibility and could trigger a formal concern."
        ),
        "original_excerpt": (
            "This policy has been developed in accordance with the statutory guidance set out in "
            "Working Together to Safeguard Children 2018 (HM Government) and reflects current legislation "
            "and guidance relevant to the safeguarding and protection of children."
        ),
        "detection_method": "corpus_confirmed",
    }


def check_ofsted_camps_gap(policy_text: str) -> dict | None:
    """
    No reference to Ofsted childcare registration or exemptions for sports camps.
    If Elevate runs holiday camps for under-8s, Ofsted registration may be required.
    """
    policy_lower = policy_text.lower()
    has_ofsted = "ofsted" in policy_lower
    has_registration = (
        "childcare registration" in policy_lower
        or "registration exemption" in policy_lower
        or "childcare act" in policy_lower
    )
    if not (has_ofsted or has_registration):
        return {
            "gap_id": "ofsted_camps_gap",
            "gap_type": "missing_coverage",
            "policy_name": "Full Policy Set (all policies)",
            "severity": "Medium",
            "source": SOURCES["ofsted_exemptions"],
            "description": (
                "No policy in the set references Ofsted childcare registration requirements or exemptions for sports camps and holiday clubs. "
                "If Elevate runs camps for children under 8 for more than 2 hours/day, Ofsted registration is legally required. "
                "If exempt (e.g. activity-based exemption), the exemption must be documented. Currently neither is addressed."
            ),
            "original_excerpt": None,
            "recommended_action": (
                "Add a section to the Health & Safety or Safeguarding policy confirming Elevate's Ofsted registration status for camps "
                "and holiday clubs, or explicitly documenting the applicable exemption under the Childcare (Exemptions from Registration) Order 2008."
            ),
            "detection_method": "absence_check",
        }
    return None


def check_insurance_expiry() -> dict:
    """
    Insurance certificate CHBS4860808XB expired 18 February 2026.
    Corpus-confirmed: Chad's policy folder, reviewed 8 June 2026.
    """
    return {
        "gap_id": "insurance_expired",
        "gap_type": "expired_document",
        "policy_name": "Simply Business Insurance Certificate (CHBS4860808XB)",
        "severity": "High",
        "source": SOURCES["simply_business"],
        "description": (
            "The insurance certificate on file (Simply Business, policy ref CHBS4860808XB) expired on 18 February 2026. "
            "Cover ran 19 February 2025 to 18 February 2026. "
            "Operating in schools without valid employers' liability insurance is a legal breach and would void any incident claim. "
            "Renewed certificate from Chad is outstanding."
        ),
        "original_excerpt": None,
        "recommended_action": (
            "Obtain the renewed certificate from Chad immediately and replace the expired document in the shared policy drive. "
            "Confirm renewal dates and ensure the certificate is shared with any schools requiring proof of cover."
        ),
        "detection_method": "corpus_confirmed",
    }


# ─────────────────────────────────────────────
# Main entry points
# ─────────────────────────────────────────────

def detect_all_gaps(policy_text: str) -> list[dict]:
    """
    Run all checks against the policy text.
    Returns a list of findings, each anchored to an official source URL.
    Order: severity High first, then Medium.
    """
    findings = []

    # Text-based + corpus-confirmed checks
    ada = check_ada_error(policy_text)
    if ada:
        findings.append(ada)

    wt = check_working_together_version(policy_text)
    if wt:
        findings.append(wt)

    # Always include corpus-confirmed findings
    findings.append(check_insurance_expiry())

    # Absence checks (check across what we have — if no Ofsted ref found, flag it)
    ofsted = check_ofsted_camps_gap(policy_text)
    if ofsted:
        findings.append(ofsted)

    return findings


def detect_gap(policy_text: str) -> dict:
    """
    Legacy single-gap interface for backward compatibility with scheduler.py.
    Returns the first High finding, or found=False.
    Use detect_all_gaps() for full multi-finding support.
    """
    findings = detect_all_gaps(policy_text)
    if findings:
        f = findings[0]
        return {**f, "found": True}
    return {"found": False, "description": "No compliance gaps detected."}


if __name__ == "__main__":
    sample = """
    Elevate Performance Academy Accessibility and Inclusiveness Policy.
    In accordance with the Americans with Disabilities Act, we ensure all
    facilities are accessible to individuals with disabilities.
    Our safeguarding policy follows Working Together to Safeguard Children 2018.
    """
    findings = detect_all_gaps(sample)
    print(f"\n{len(findings)} finding(s) detected:\n")
    for f in findings:
        print(f"  [{f['severity']}] {f['gap_id']} — {f['policy_name']}")
        print(f"  Source: {f['source']['name']}")
        print(f"  URL: {f['source']['url']}")
        print()
