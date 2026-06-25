"""
publish_draft.py
On approval, writes the corrected policy text to a new Google Doc
in the Elevate shared drive folder.
"""

import os
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/gmail.send",
]

# The name of the folder in Google Drive to publish into
TARGET_FOLDER_NAME = "Elevate"


def get_services():
    """Authenticate and return Drive + Docs API services.
    Loads token from GOOGLE_TOKEN_JSON env var (Railway) or token.json (local).
    Falls back to interactive OAuth on first-time local setup.
    """
    import json as _json
    from google_auth_oauthlib.flow import InstalledAppFlow
    creds = None

    token_env = os.getenv("GOOGLE_TOKEN_JSON")
    if token_env:
        token_data = _json.loads(token_env)
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
    elif os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
            with open("token.json", "w") as f:
                f.write(creds.to_json())

    drive_service = build("drive", "v3", credentials=creds)
    docs_service = build("docs", "v1", credentials=creds)
    return drive_service, docs_service


def find_folder_id(drive_service, folder_name: str) -> str:
    """Find the Google Drive folder ID by name."""
    results = drive_service.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        spaces="drive",
        fields="files(id, name)",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
    ).execute()
    files = results.get("files", [])
    if not files:
        # Fall back to root if folder not found
        print(f"Folder '{folder_name}' not found — publishing to root Drive.")
        return None
    print(f"Publishing to folder: {files[0]['name']} (ID: {files[0]['id']})")
    return files[0]["id"]


def _build_doc_text(findings_or_correction, review_id: str, date_str: str) -> str:
    """Build the plain-text body for the correction doc."""
    header = (
        f"ELEVATE PERFORMANCE ACADEMY — POLICY COMPLIANCE AUDIT\n"
        f"{'=' * 60}\n\n"
        f"Review ID:   {review_id}\n"
        f"Approved:    {date_str}\n"
        f"Approved by: Malachi (via email approval link)\n"
        f"Bot version: AY Policy Bot v0.1\n\n"
        f"DISCLAIMER: This report was generated automatically by the AY Policy Bot "
        f"and approved by a human reviewer. It does not constitute legal advice. "
        f"Elevate should apply these corrections to their live policy documents.\n\n"
        f"{'=' * 60}\n\n"
    )

    # Normalise to list
    if isinstance(findings_or_correction, dict):
        findings = [findings_or_correction]
    else:
        findings = findings_or_correction

    body = ""
    for i, f in enumerate(findings):
        source = f.get("source", {})
        source_name = source.get("name", "") if isinstance(source, dict) else f.get("source_name", "")
        source_url = source.get("url", "") if isinstance(source, dict) else f.get("source_url", "")

        body += f"FINDING {i + 1} OF {len(findings)}\n"
        body += f"{'─' * 40}\n"
        body += f"Policy:   {f.get('policy_name', 'Unknown')}\n"
        body += f"Severity: {f.get('severity', 'Unknown')}\n"
        body += f"Source:   {source_name}\n"
        body += f"URL:      {source_url}\n\n"
        body += f"ISSUE\n{f.get('description', '')}\n\n"

        original = f.get("original_excerpt", "") or ""
        corrected = f.get("corrected_excerpt", "") or ""
        gap_type = f.get("gap_type", "")

        if original and gap_type in ("wrong_reference", "outdated_reference"):
            body += f"ORIGINAL TEXT (incorrect)\n{original}\n\n"
            body += f"CORRECTED TEXT (approved)\n{corrected}\n\n"
        elif corrected:
            body += f"RECOMMENDED ACTION\n{corrected}\n\n"

        body += "\n"

    return header + body


def create_correction_doc(drive_service, docs_service, findings_or_correction, review_id: str, folder_id: str) -> str:
    """
    Creates a new Google Doc with all findings and their source links.
    Returns the URL of the created document.
    """
    date_str = datetime.utcnow().strftime("%d %B %Y")
    count = len(findings_or_correction) if isinstance(findings_or_correction, list) else 1
    doc_title = f"Elevate Policy Audit — {count} finding{'s' if count != 1 else ''} approved {date_str} [{review_id}]"

    doc = drive_service.files().create(
        body={
            "name": doc_title,
            "mimeType": "application/vnd.google-apps.document",
            **({"parents": [folder_id]} if folder_id else {}),
        },
        supportsAllDrives=True,
    ).execute()

    doc_id = doc["id"]
    full_text = doc_title + "\n\n" + _build_doc_text(findings_or_correction, review_id, date_str)

    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [
            {"insertText": {"location": {"index": 1}, "text": full_text}}
        ]},
    ).execute()

    doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
    print(f"Document created: {doc_url}")
    return doc_url


def publish_approved_correction(findings_or_correction, review_id: str) -> str:
    """Main entry point called by the approve webhook. Accepts list of findings or legacy dict."""
    drive_service, docs_service = get_services()
    folder_id = find_folder_id(drive_service, TARGET_FOLDER_NAME)
    doc_url = create_correction_doc(drive_service, docs_service, findings_or_correction, review_id, folder_id)
    return doc_url


if __name__ == "__main__":
    sample_correction = {
        "original_excerpt": "In accordance with the Americans with Disabilities Act, we ensure all facilities are accessible.",
        "corrected_excerpt": "In accordance with the Equality Act 2010 and the Public Sector Equality Duty (Section 149), we ensure all facilities are accessible to participants with protected characteristics.",
        "wrong_reference": "Americans with Disabilities Act",
        "correct_reference": "Equality Act 2010",
        "severity": "High",
        "description": "Policy references US law instead of UK Equality Act 2010.",
    }
    url = publish_approved_correction(sample_correction, "test-001")
    print(f"Published to: {url}")
