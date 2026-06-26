"""
publish_draft.py
On approval, directly edits the existing policy documents in Google Drive.

- wrong_reference / outdated_reference  →  replaceAllText in the policy Google Doc
- missing_coverage / expired_document   →  Drive comment on the relevant doc (action required)

No new documents are created unless the policy doc cannot be found at all (fallback only).
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

# Maps policy_name values (from findings) to Drive search terms.
# "Full Policy Set" findings are pinned to the Safeguarding policy as the best home.
POLICY_SEARCH_TERMS = {
    "Accessibility and Inclusiveness Policy": "Accessibility and Inclusiveness Policy",
    "Safeguarding Policy": "Safeguarding",
    "Full Policy Set (all policies)": "Safeguarding",
}


def get_services():
    """Authenticate and return Drive + Docs API services."""
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


def find_policy_doc(drive_service, search_term: str):
    """Find a Google Doc in Drive by name. Returns (doc_id, doc_url) or (None, None)."""
    results = drive_service.files().list(
        q=(
            f"name contains '{search_term}' "
            f"and mimeType='application/vnd.google-apps.document' "
            f"and trashed=false"
        ),
        spaces="drive",
        fields="files(id, name)",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
    ).execute()
    files = results.get("files", [])
    if not files:
        print(f"Policy doc not found for search term: '{search_term}'")
        return None, None
    doc_id = files[0]["id"]
    doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
    print(f"Found policy doc: '{files[0]['name']}' ({doc_id})")
    return doc_id, doc_url


def apply_text_replacement(docs_service, doc_id: str, old_text: str, new_text: str) -> int:
    """
    Replace all occurrences of old_text with new_text in a Google Doc.
    Case-insensitive. Returns the number of replacements made.
    """
    response = docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [
            {"replaceAllText": {
                "containsText": {"text": old_text, "matchCase": False},
                "replaceText": new_text,
            }}
        ]},
    ).execute()
    replies = response.get("replies", [{}])
    count = (
        replies[0].get("replaceAllText", {}).get("occurrencesChanged", 0)
        if replies else 0
    )
    print(f"replaceAllText: '{old_text}' → '{new_text}' — {count} replacement(s) in {doc_id}")
    return count


def add_drive_comment(drive_service, doc_id: str, comment_text: str):
    """Add a comment to a Google Drive file."""
    drive_service.comments().create(
        fileId=doc_id,
        body={"content": comment_text},
        fields="id",
    ).execute()
    print(f"Comment added to doc {doc_id}")


def publish_approved_correction(findings_or_correction, review_id: str) -> str:
    """
    Main entry point called by the approve webhook.
    Accepts a list of findings (new flow) or a single correction dict (legacy).

    For each finding:
      - wrong_reference / outdated_reference  →  edits the policy doc in-place
      - missing_coverage / expired_document   →  adds a Drive comment (action required)

    Returns the URL of the first updated document (shown on the confirmation page).
    Falls back to creating a summary doc if no policy docs could be located.
    """
    drive_service, docs_service = get_services()

    if isinstance(findings_or_correction, dict):
        findings = [findings_or_correction]
    else:
        findings = findings_or_correction

    date_str = datetime.utcnow().strftime("%d %B %Y at %H:%M UTC")
    updated_docs = {}   # policy_name → doc_url
    skipped = []

    for finding in findings:
        policy_name = finding.get("policy_name", "")
        gap_type = finding.get("gap_type", "")
        gap_id = finding.get("gap_id", "")

        # Special case: insurance certificate is not a Google Doc — Drive comment only
        # We pin it to the Safeguarding policy as the closest relevant document
        if gap_id == "insurance_expired":
            search_term = POLICY_SEARCH_TERMS.get("Safeguarding Policy", "Safeguarding")
        else:
            search_term = POLICY_SEARCH_TERMS.get(policy_name, policy_name)

        doc_id, doc_url = find_policy_doc(drive_service, search_term)

        if not doc_id:
            skipped.append(policy_name)
            continue

        if gap_type in ("wrong_reference", "outdated_reference"):
            # Use search_text if provided (exact phrase in doc), fall back to wrong_reference
            search_phrase = finding.get("search_text") or finding.get("wrong_reference", "")
            replacement = finding.get("correct_reference", "")

            if search_phrase and replacement:
                count = apply_text_replacement(docs_service, doc_id, search_phrase, replacement)

                if count > 0:
                    source = finding.get("source", {})
                    comment = (
                        f"[AY Policy Bot — {date_str}] Automated correction applied (Ref: {review_id})\n"
                        f"Changed: \"{search_phrase}\" → \"{replacement}\"\n"
                        f"Source: {source.get('name', '')} — {source.get('url', '')}"
                    )
                    try:
                        add_drive_comment(drive_service, doc_id, comment)
                    except Exception as e:
                        print(f"Warning: could not add comment to {doc_id}: {e}")
                    updated_docs[policy_name] = doc_url
                else:
                    print(
                        f"No match for '{search_phrase}' in '{policy_name}' "
                        f"— text may already be correct or the doc is a .docx not a Google Doc."
                    )
                    skipped.append(policy_name)
            else:
                print(f"Missing search_phrase or replacement for finding '{gap_id}' — skipping.")
                skipped.append(policy_name)

        elif gap_type in ("missing_coverage", "expired_document"):
            # Can't auto-insert prose — flag with a Drive comment for manual action
            action = finding.get("recommended_action") or finding.get("description", "")
            source = finding.get("source", {})
            comment = (
                f"[AY Policy Bot — {date_str}] ACTION REQUIRED (Ref: {review_id})\n"
                f"{action}\n"
                f"Source: {source.get('name', '')} — {source.get('url', '')}"
            )
            try:
                add_drive_comment(drive_service, doc_id, comment)
                updated_docs[policy_name] = doc_url
            except Exception as e:
                print(f"Warning: could not add comment to {doc_id}: {e}")
                skipped.append(policy_name)

        else:
            print(f"Unknown gap_type '{gap_type}' for finding '{gap_id}' — skipping.")
            skipped.append(policy_name)

    if skipped:
        print(f"Skipped {len(skipped)} finding(s) (doc not found or no text match): {skipped}")

    if not updated_docs:
        print("No documents were updated. Creating fallback summary doc.")
        return _create_fallback_summary(drive_service, docs_service, findings, review_id)

    first_url = next(iter(updated_docs.values()))
    print(f"Done — {len(updated_docs)} document(s) updated: {list(updated_docs.values())}")
    return first_url


def _create_fallback_summary(drive_service, docs_service, findings, review_id: str) -> str:
    """
    Creates a summary doc only if no policy documents could be located in Drive.
    This prevents a silent failure — there's always something to link to on the
    confirmation page.
    """
    date_str = datetime.utcnow().strftime("%d %B %Y")
    doc_title = f"Elevate Policy Bot — Manual Action Required {date_str} [{review_id}]"

    lines = [
        doc_title, "",
        f"Review ID:  {review_id}",
        f"Date:       {date_str}", "",
        "The bot could not locate the policy documents in Google Drive.",
        "The corrections below require manual application:", "",
    ]
    for i, f in enumerate(findings, 1):
        lines.append(f"FINDING {i}: {f.get('policy_name', '')}")
        lines.append(f.get("description", ""))
        if f.get("wrong_reference"):
            lines.append(
                f"Change: '{f.get('search_text') or f['wrong_reference']}'"
                f" → '{f.get('correct_reference', '')}'"
            )
        elif f.get("recommended_action"):
            lines.append(f"Action: {f['recommended_action']}")
        lines.append("")

    doc = drive_service.files().create(
        body={"name": doc_title, "mimeType": "application/vnd.google-apps.document"},
        supportsAllDrives=True,
    ).execute()
    doc_id = doc["id"]
    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [
            {"insertText": {"location": {"index": 1}, "text": "\n".join(lines)}}
        ]},
    ).execute()
    url = f"https://docs.google.com/document/d/{doc_id}/edit"
    print(f"Fallback summary created: {url}")
    return url


if __name__ == "__main__":
    # Quick smoke test — runs against real Drive
    sample = {
        "gap_id": "ada_jurisdiction",
        "gap_type": "wrong_reference",
        "policy_name": "Accessibility and Inclusiveness Policy",
        "severity": "High",
        "source": {
            "name": "Equality Act 2010",
            "url": "https://www.gov.uk/guidance/equality-act-2010-guidance",
        },
        "wrong_reference": "Americans with Disabilities Act (ADA)",
        "search_text": "Americans with Disabilities Act",
        "correct_reference": "Equality Act 2010",
        "description": "Policy cites US law instead of UK Equality Act 2010.",
    }
    url = publish_approved_correction(sample, "test-001")
    print(f"Result: {url}")
