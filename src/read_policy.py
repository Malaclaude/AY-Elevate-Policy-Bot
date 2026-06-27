"""
read_policy.py
Reads the Accessibility and Inclusiveness Policy from the LIVE Elevate Google
Drive document, so detection reflects the real current state of the policy
(and never re-flags something that has already been corrected).
Falls back to a local baseline copy only if Drive cannot be reached.
"""

import os
import io
import zipfile
import re

# Live Drive documents (same files the bot corrects in place).
ACCESSIBILITY_FILE_ID = "1HYXCO9UgJ_Jzd_RXVfLOoY_frUvFgoD4"
SAFEGUARDING_FILE_ID = "1kZDRHmz4b-liBx_w8Nnwvxuz56GLtJow"

# Local fallback only, used if Drive is unreachable.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_POLICY_PATH = os.path.join(
    REPO_ROOT, "policies", "baseline", "Accessibility and Inclusiveness Policy.docx"
)


def _docx_text_from_bytes(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml_content = z.read("word/document.xml").decode("utf-8")
    text = re.sub(r"<[^>]+>", " ", xml_content)
    text = re.sub(r" +", " ", text).strip()
    return text


def read_docx_text(filepath: str) -> str:
    """Extract plain text from a local .docx file."""
    with open(filepath, "rb") as f:
        return _docx_text_from_bytes(f.read())


def read_accessibility_policy(doc_path: str = None) -> str:
    """
    Read the policy text.
    - doc_path given: read that local file (used for --doc testing).
    - otherwise: read the LIVE Accessibility doc from Drive, falling back to the
      local baseline only if Drive is unreachable.
    """
    if doc_path:
        path = os.path.normpath(doc_path if os.path.isabs(doc_path)
                                else os.path.join(REPO_ROOT, doc_path))
        if not os.path.exists(path):
            raise FileNotFoundError(f"Policy file not found at: {path}")
        text = read_docx_text(path)
        print(f"Policy loaded from local file: {os.path.basename(path)} — {len(text)} characters")
        return text

    # Default: live Drive read
    try:
        from publish_draft import get_services, _download_bytes
        drive_service, _ = get_services()
        data = _download_bytes(drive_service, ACCESSIBILITY_FILE_ID)
        text = _docx_text_from_bytes(data)
        print(f"Policy loaded from Drive (live) — {len(text)} characters")
        return text
    except Exception as e:
        print(f"Drive read failed ({e}); falling back to local baseline.")
        if not os.path.exists(LOCAL_POLICY_PATH):
            raise FileNotFoundError(
                f"Drive read failed and no local baseline at: {LOCAL_POLICY_PATH}"
            )
        text = read_docx_text(LOCAL_POLICY_PATH)
        print(f"Policy loaded from local baseline — {len(text)} characters")
        return text


def read_safeguarding_policy() -> str:
    """Read the LIVE Safeguarding doc text. Returns '' if Drive is unreachable
    (callers then fall back to the corpus-confirmed finding)."""
    try:
        from publish_draft import get_services, _download_bytes
        drive_service, _ = get_services()
        data = _download_bytes(drive_service, SAFEGUARDING_FILE_ID)
        text = _docx_text_from_bytes(data)
        print(f"Safeguarding loaded from Drive (live) — {len(text)} characters")
        return text
    except Exception as e:
        print(f"Safeguarding Drive read failed ({e}).")
        return ""


if __name__ == "__main__":
    text = read_accessibility_policy()
    print("\n--- POLICY TEXT PREVIEW ---\n")
    print(text[:1000])
