"""
read_policy.py
Reads the Accessibility and Inclusiveness Policy from the Elevate Google Drive folder.
Returns the plain text content.
"""

import os
import zipfile
import re

# Path to the policy file — relative to the repo root (policy-bot/)
# The file must be at policy-bot/policies/baseline/Accessibility and Inclusiveness Policy.docx
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_POLICY_PATH = os.path.join(
    REPO_ROOT, "policies", "baseline", "Accessibility and Inclusiveness Policy.docx"
)


def read_docx_text(filepath: str) -> str:
    """Extract plain text from a .docx file."""
    with open(filepath, "rb") as f:
        buffer = f.read()

    import io
    with zipfile.ZipFile(io.BytesIO(buffer)) as z:
        with z.open("word/document.xml") as xml_file:
            xml_content = xml_file.read().decode("utf-8")
            text = re.sub(r"<[^>]+>", " ", xml_content)
            text = re.sub(r" +", " ", text).strip()
    return text


def read_accessibility_policy() -> str:
    """Read the Accessibility policy from the local file."""
    path = os.path.normpath(LOCAL_POLICY_PATH)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Policy file not found at: {path}")
    text = read_docx_text(path)
    print(f"Policy loaded from local file — {len(text)} characters")
    return text


if __name__ == "__main__":
    text = read_accessibility_policy()
    print("\n--- POLICY TEXT PREVIEW ---\n")
    print(text[:1000])
