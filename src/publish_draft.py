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
    """Authenticate and return Drive + Docs API services."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
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


def create_correction_doc(drive_service, docs_service, correction: dict, review_id: str, folder_id: str) -> str:
    """
    Creates a new Google Doc with the correction details.
    Returns the URL of the created document.
    """
    date_str = datetime.utcnow().strftime("%d %B %Y")
    doc_title = f"Accessibility Policy — Correction Approved {date_str} [{review_id}]"

    # Create the document
    doc_metadata = {"title": doc_title}
    if folder_id:
        doc_metadata["parents"] = [folder_id]

    doc = drive_service.files().create(
        body={
            "name": doc_title,
            "mimeType": "application/vnd.google-apps.document",
            **({"parents": [folder_id]} if folder_id else {}),
        },
        supportsAllDrives=True,
    ).execute()

    doc_id = doc["id"]

    # Build the document content
    content = [
        # Title
        {"insertText": {"location": {"index": 1}, "text": f"{doc_title}\n\n"}},

        # Metadata block
        {"insertText": {"location": {"index": len(doc_title) + 3}, "text":
            f"Policy: Accessibility and Inclusiveness Policy\n"
            f"Review ID: {review_id}\n"
            f"Approved: {date_str}\n"
            f"Approved by: Malachi (via email approval link)\n"
            f"Bot version: AY Policy Bot v0.1 (demo slice)\n\n"
        }},
    ]

    # Calculate current index after metadata
    meta_text = (
        f"Policy: Accessibility and Inclusiveness Policy\n"
        f"Review ID: {review_id}\n"
        f"Approved: {date_str}\n"
        f"Approved by: Malachi (via email approval link)\n"
        f"Bot version: AY Policy Bot v0.1 (demo slice)\n\n"
    )
    idx = len(doc_title) + 3 + len(meta_text)

    # Gap description
    gap_section = f"ISSUE DETECTED\n\n{correction['description']}\n\n"
    content.append({"insertText": {"location": {"index": idx}, "text": gap_section}})
    idx += len(gap_section)

    # Before/after
    before_section = f"ORIGINAL TEXT (incorrect)\n\n{correction['original_excerpt']}\n\n"
    content.append({"insertText": {"location": {"index": idx}, "text": before_section}})
    idx += len(before_section)

    after_section = f"CORRECTED TEXT (approved)\n\n{correction['corrected_excerpt']}\n\n"
    content.append({"insertText": {"location": {"index": idx}, "text": after_section}})
    idx += len(after_section)

    # Regulatory reference
    ref_section = (
        f"REGULATORY REFERENCE\n\n"
        f"Equality Act 2010: https://www.legislation.gov.uk/ukpga/2010/15/contents\n"
        f"Public Sector Equality Duty (s.149): https://www.legislation.gov.uk/ukpga/2010/15/section/149\n\n"
        f"This document was generated automatically by the AY Policy Bot and approved by a human reviewer.\n"
        f"It does not constitute legal advice. Elevate should apply this correction to their live policy document.\n"
    )
    content.append({"insertText": {"location": {"index": idx}, "text": ref_section}})

    # Write all content in one batch
    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": content},
    ).execute()

    doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
    print(f"Document created: {doc_url}")
    return doc_url


def publish_approved_correction(correction: dict, review_id: str) -> str:
    """Main entry point called by the approve webhook."""
    drive_service, docs_service = get_services()
    folder_id = find_folder_id(drive_service, TARGET_FOLDER_NAME)
    doc_url = create_correction_doc(drive_service, docs_service, correction, review_id, folder_id)
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
