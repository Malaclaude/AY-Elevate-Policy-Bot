"""
draft_correction.py
Calls the Claude API to draft a corrected version of the flagged policy passage.
"""

import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def draft_correction(gap: dict, full_policy_text: str) -> dict:
    """
    Takes a detected gap and the full policy text.
    Returns a before/after correction drafted by Claude.
    """

    prompt = f"""You are a UK compliance specialist helping a youth sports academy (Elevate Performance Academy)
correct an error in their policy documentation.

CONTEXT:
Elevate operates in England, delivering youth sport and education programmes in schools.
They are subject to the Equality Act 2010, not US legislation.

THE PROBLEM:
The following passage from their Accessibility and Inclusiveness Policy contains a critical error.
It references the Americans with Disabilities Act (a US law) instead of the correct UK legislation.

OFFENDING PASSAGE:
{gap['excerpt']}

YOUR TASK:
1. Rewrite the offending passage to reference the correct UK legislation: the Equality Act 2010.
2. Where relevant, also reference the Public Sector Equality Duty (Section 149 of the Equality Act 2010),
   which applies because Elevate delivers in schools.
3. Keep the tone and length similar to the original. Do not over-engineer it.
4. Output only the corrected passage — no preamble, no explanation.

CORRECTED PASSAGE:"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    corrected_text = message.content[0].text.strip()

    return {
        "original_excerpt": gap["excerpt"],
        "corrected_excerpt": corrected_text,
        "wrong_reference": gap["wrong_reference"],
        "correct_reference": gap["correct_reference"],
        "severity": gap["severity"],
        "description": gap["description"],
        "model_used": "claude-sonnet-4-6",
    }


if __name__ == "__main__":
    # Test with a sample gap
    sample_gap = {
        "found": True,
        "wrong_reference": "Americans with Disabilities Act",
        "correct_reference": "Equality Act 2010",
        "excerpt": "In accordance with the Americans with Disabilities Act, we ensure all facilities are accessible.",
        "gap_type": "wrong_jurisdiction",
        "severity": "High",
        "description": "Policy references US law instead of UK Equality Act 2010.",
    }

    result = draft_correction(sample_gap, "")
    print("ORIGINAL:\n", result["original_excerpt"])
    print("\nCORRECTED:\n", result["corrected_excerpt"])
