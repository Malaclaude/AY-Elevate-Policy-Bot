"""
draft_correction.py
For each finding from detect_gap.py, drafts a corrected version where applicable.
- wrong_reference / outdated_reference findings: Claude drafts the corrected passage
- missing_coverage / expired_document findings: uses recommended_action as the draft
"""

import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


POLICY_CONTEXT = """You are a UK compliance specialist helping Elevate Performance Academy,
a youth sports and education company operating in England delivering coaching in schools and
running holiday camps. They work with children and young people. They are subject to:
- Equality Act 2010 (not US legislation)
- Working Together to Safeguard Children 2023
- Keeping Children Safe in Education 2024
- UK GDPR / ICO guidance including the Children's Code
- HSE health and safety legislation
- DBS safeguarding requirements
- ACAS Code of Practice (disciplinary matters)"""


def draft_text_correction(finding: dict, full_policy_text: str) -> str:
    """
    Call Claude to draft a corrected version of the offending passage.
    Only called for findings that have an original_excerpt.
    """
    source_name = finding["source"]["name"]
    source_url = finding["source"]["url"]
    wrong_ref = finding.get("wrong_reference", "")
    correct_ref = finding.get("correct_reference", "")

    prompt = f"""{POLICY_CONTEXT}

THE PROBLEM:
The following passage from the {finding['policy_name']} contains an error.
It references "{wrong_ref}" when it should reference "{correct_ref}".

OFFENDING PASSAGE:
{finding['original_excerpt']}

YOUR TASK:
1. Rewrite the passage to reference the correct source: {correct_ref} ({source_url})
2. Keep the tone, structure, and approximate length of the original.
3. Do not add bullet points, headers, or commentary — output only the corrected passage.
4. If relevant, reference the specific section of the legislation (e.g. Section 149 of the Equality Act for the Public Sector Equality Duty).

CORRECTED PASSAGE:"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def draft_all_corrections(findings: list[dict], full_policy_text: str) -> list[dict]:
    """
    For each finding, produce a corrected_excerpt or recommended_action.
    Returns the enriched findings list, ready to be sent in the review email.
    """
    enriched = []
    for finding in findings:
        f = dict(finding)  # copy

        if f.get("original_excerpt") and f.get("wrong_reference"):
            # Claude drafts the corrected passage
            print(f"  Drafting correction for: {f['gap_id']} ...")
            f["corrected_excerpt"] = draft_text_correction(f, full_policy_text)
        else:
            # Gap findings: corrected_excerpt is the recommended action
            f["corrected_excerpt"] = f.get(
                "recommended_action",
                "Action required — see description above."
            )

        enriched.append(f)

    return enriched


# ─── Legacy single-finding interface (used by scheduler.py) ───────────────────

def draft_correction(gap: dict, full_policy_text: str) -> dict:
    """
    Legacy interface: takes a single gap dict, returns a single correction dict.
    Wraps draft_all_corrections for backward compatibility.
    """
    findings = draft_all_corrections([gap], full_policy_text)
    f = findings[0]

    # Return shape the old approve/publish flow expects
    return {
        "original_excerpt": f.get("original_excerpt", ""),
        "corrected_excerpt": f.get("corrected_excerpt", ""),
        "wrong_reference": f.get("wrong_reference", ""),
        "correct_reference": f.get("correct_reference", ""),
        "severity": f.get("severity", "High"),
        "description": f.get("description", ""),
        "source_name": f["source"]["name"],
        "source_url": f["source"]["url"],
        "model_used": "claude-sonnet-4-6",
    }


if __name__ == "__main__":
    from detect_gap import detect_all_gaps

    sample = """
    In accordance with the Americans with Disabilities Act, we ensure all
    facilities are accessible to individuals with disabilities.
    Our safeguarding policy follows Working Together to Safeguard Children 2018.
    """
    findings = detect_all_gaps(sample)
    enriched = draft_all_corrections(findings, sample)

    for f in enriched:
        print(f"\n[{f['severity']}] {f['gap_id']}")
        print(f"  Source: {f['source']['name']}")
        if f.get("original_excerpt"):
            print(f"  Original:  {f['original_excerpt'][:120]}...")
            print(f"  Corrected: {f['corrected_excerpt'][:120]}...")
        else:
            print(f"  Action: {f['corrected_excerpt'][:120]}...")
