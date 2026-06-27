"""
publish_draft.py
On approval, directly edits the existing policy documents in Google Drive in-place.

Strategy:
- .docx files  →  download bytes, replace text in the XML, re-upload to overwrite the
                   original file (same file ID, same location, no duplicates)
- Google Docs  →  replaceAllText via the Docs API (instant, no download needed)
- missing_coverage / expired_document  →  Drive comment on the relevant doc

No new documents are ever created unless every policy doc lookup fails (fallback only).
"""

import io
import os
import re
import zipfile
from datetime import datetime

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/gmail.send",
]

GDOC_MIME = "application/vnd.google-apps.document"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# ── Direct file ID registry (bypasses Drive search entirely) ────────────────
# These are the confirmed file IDs for Elevate's live policy docs.
# Using direct IDs avoids any search/indexing failures on Railway.
KNOWN_FILE_IDS = {
    "Accessibility and Inclusiveness Policy": (
        "1HYXCO9UgJ_Jzd_RXVfLOoY_frUvFgoD4",
        DOCX_MIME,
        "https://drive.google.com/file/d/1HYXCO9UgJ_Jzd_RXVfLOoY_frUvFgoD4/view",
    ),
    "Safeguarding Policy": (
        "1kZDRHmz4b-liBx_w8Nnwvxuz56GLtJow",
        DOCX_MIME,
        "https://drive.google.com/file/d/1kZDRHmz4b-liBx_w8Nnwvxuz56GLtJow/view",
    ),
    "Full Policy Set (all policies)": (
        "1kZDRHmz4b-liBx_w8Nnwvxuz56GLtJow",
        DOCX_MIME,
        "https://drive.google.com/file/d/1kZDRHmz4b-liBx_w8Nnwvxuz56GLtJow/view",
    ),
}

# Maps policy_name values (from findings) to Drive search terms (fallback only).
POLICY_SEARCH_TERMS = {
    "Accessibility and Inclusiveness Policy": "Accessibility and Inclusiveness Policy",
    "Safeguarding Policy": "Safeguarding Policy",
    "Full Policy Set (all policies)": "Safeguarding Policy",
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
    """
    Find a policy document in Drive by name.
    Returns (file_id, mime_type, doc_url) or (None, None, None).
    Prefers native Google Docs; falls back to .docx.
    """
    results = drive_service.files().list(
        q=(
            f"name contains '{search_term}' "
            f"and (mimeType='{GDOC_MIME}' or mimeType='{DOCX_MIME}') "
            f"and trashed=false"
        ),
        spaces="drive",
        fields="files(id, name, mimeType)",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
    ).execute()
    files = results.get("files", [])

    if not files:
        print(f"Policy doc not found for search term: '{search_term}'")
        return None, None, None

    # Prefer native Google Doc if one exists
    gdocs = [f for f in files if f["mimeType"] == GDOC_MIME]
    chosen = gdocs[0] if gdocs else files[0]

    mime = chosen["mimeType"]
    file_id = chosen["id"]
    doc_url = (
        f"https://docs.google.com/document/d/{file_id}/edit"
        if mime == GDOC_MIME
        else f"https://drive.google.com/file/d/{file_id}/view"
    )
    print(f"Found: '{chosen['name']}' ({mime.split('.')[-1]}) — {file_id}")
    return file_id, mime, doc_url


# ── .docx in-place editing ──────────────────────────────────────────────────

def _download_bytes(drive_service, file_id: str) -> bytes:
    request = drive_service.files().get_media(
        fileId=file_id, supportsAllDrives=True
    )
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# Only the text-bearing parts of the package are touched. Everything else
# (logos, images, headers' media, styles, fonts, relationships) is copied
# byte-for-byte so embedded graphics are never disturbed.
_EDITABLE_PART = re.compile(r"^word/(document|header\d*|footer\d*)\.xml$")


def _replace_in_docx_bytes(docx_bytes: bytes, old_text: str, new_text: str) -> tuple:
    """
    Surgical .docx text replacement that preserves the rest of the package.

    Rewrites ONLY the visible text inside the body/header/footer XML and copies
    every other zip entry unchanged. A full python-docx re-save can drop or
    reposition embedded logos and shapes (and roughly halves the file); this
    method cannot, because it never re-serialises images or relationships.

    Returns (updated_bytes, count).

    Limitation: matches text that is contiguous within a run. Word normally
    keeps a pasted phrase in one run; if a phrase is split mid-word across runs
    it is reported as 0 and left untouched (safer than corrupting layout).
    """
    pattern = re.compile(re.escape(_xml_escape(old_text)), re.IGNORECASE)
    replacement = _xml_escape(new_text)
    count = 0

    src = zipfile.ZipFile(io.BytesIO(docx_bytes), "r")
    out_buf = io.BytesIO()
    with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if _EDITABLE_PART.search(item.filename):
                text = data.decode("utf-8")
                text, n = pattern.subn(replacement, text)
                count += n
                data = text.encode("utf-8")
            # preserve original compression type per entry
            dst.writestr(item, data)
    src.close()
    return out_buf.getvalue(), count


def _upload_bytes(drive_service, file_id: str, file_bytes: bytes):
    """Overwrite an existing Drive file's content in-place."""
    media = MediaIoBaseUpload(
        io.BytesIO(file_bytes), mimetype=DOCX_MIME, resumable=False
    )
    drive_service.files().update(
        fileId=file_id,
        media_body=media,
        supportsAllDrives=True,
    ).execute()
    print(f"File {file_id} updated in-place.")


def edit_docx_in_place(drive_service, file_id: str, old_text: str, new_text: str) -> int:
    """Download, replace text, re-upload. Returns number of replacements made."""
    docx_bytes = _download_bytes(drive_service, file_id)
    updated_bytes, count = _replace_in_docx_bytes(docx_bytes, old_text, new_text)
    if count > 0:
        _upload_bytes(drive_service, file_id, updated_bytes)
        print(f"Replaced '{old_text}' → '{new_text}' ({count} occurrence(s)) in {file_id}")
    else:
        print(f"No match for '{old_text}' in {file_id} — text may already be correct.")
    return count


def _insert_paragraph_bytes(docx_bytes: bytes, text: str) -> bytes:
    """Append a paragraph at the end of the body, preserving everything else
    (images, headers, styles) byte-for-byte. Inserts before the document-level
    sectPr so the new text sits at the end of the document content."""
    para = f'<w:p><w:r><w:t xml:space="preserve">{_xml_escape(text)}</w:t></w:r></w:p>'
    src = zipfile.ZipFile(io.BytesIO(docx_bytes), "r")
    out_buf = io.BytesIO()
    with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "word/document.xml":
                xml = data.decode("utf-8")
                idx = xml.rfind("<w:sectPr")
                if idx != -1:
                    xml = xml[:idx] + para + xml[idx:]
                else:
                    xml = xml.replace("</w:body>", para + "</w:body>", 1)
                data = xml.encode("utf-8")
            dst.writestr(item, data)
    src.close()
    return out_buf.getvalue()


def insert_paragraph_in_docx(drive_service, file_id: str, text: str):
    """Download, append a paragraph, re-upload. Used for approved 'add a section' fixes."""
    docx_bytes = _download_bytes(drive_service, file_id)
    new_bytes = _insert_paragraph_bytes(docx_bytes, text)
    _upload_bytes(drive_service, file_id, new_bytes)
    print(f"Inserted paragraph into {file_id}")


# ── Google Docs API editing ─────────────────────────────────────────────────

def edit_gdoc_in_place(docs_service, file_id: str, old_text: str, new_text: str) -> int:
    """replaceAllText in a native Google Doc. Returns number of replacements."""
    response = docs_service.documents().batchUpdate(
        documentId=file_id,
        body={"requests": [{"replaceAllText": {
            "containsText": {"text": old_text, "matchCase": False},
            "replaceText": new_text,
        }}]},
    ).execute()
    replies = response.get("replies", [{}])
    count = replies[0].get("replaceAllText", {}).get("occurrencesChanged", 0) if replies else 0
    print(f"replaceAllText: '{old_text}' → '{new_text}' ({count} occurrence(s)) in {file_id}")
    return count


# ── Drive comments ──────────────────────────────────────────────────────────

def add_drive_comment(drive_service, file_id: str, comment_text: str):
    try:
        drive_service.comments().create(
            fileId=file_id,
            body={"content": comment_text},
            fields="id",
        ).execute()
        print(f"Comment added to {file_id}")
    except Exception as e:
        print(f"Warning: could not add comment to {file_id}: {e}")


# ── Main entry point ────────────────────────────────────────────────────────

def publish_approved_correction(findings_or_correction, review_id: str) -> str:
    """
    For each finding:
      - wrong_reference / outdated_reference  →  edit the policy file in-place
        (.docx: download → replace XML → re-upload | Google Doc: replaceAllText)
      - missing_coverage / expired_document   →  Drive comment (action required)

    Returns the URL of the first updated file (for the confirmation page button).
    """
    drive_service, docs_service = get_services()

    if isinstance(findings_or_correction, dict):
        findings = [findings_or_correction]
    else:
        findings = findings_or_correction

    date_str = datetime.utcnow().strftime("%d %B %Y at %H:%M UTC")
    updated_docs = {}
    skipped = []

    for finding in findings:
        policy_name = finding.get("policy_name", "")
        gap_type = finding.get("gap_type", "")
        gap_id = finding.get("gap_id", "")

        # Insurance is not a policy doc — pin to Safeguarding for the comment
        lookup_key = "Safeguarding Policy" if gap_id == "insurance_expired" else policy_name

        # Use direct file ID registry first — bypasses Drive search entirely
        if lookup_key in KNOWN_FILE_IDS:
            file_id, mime, doc_url = KNOWN_FILE_IDS[lookup_key]
            print(f"Using known file ID for '{lookup_key}': {file_id}")
        else:
            # Fallback: search Drive
            search_term = POLICY_SEARCH_TERMS.get(lookup_key, lookup_key)
            file_id, mime, doc_url = find_policy_doc(drive_service, search_term)

        if not file_id:
            skipped.append(policy_name)
            continue

        source = finding.get("source", {})
        source_name = source.get("name", "") if isinstance(source, dict) else ""
        source_url = source.get("url", "") if isinstance(source, dict) else ""

        if gap_type in ("wrong_reference", "outdated_reference"):
            search_phrase = finding.get("search_text") or finding.get("wrong_reference", "")
            replacement = finding.get("correct_reference", "")

            if not search_phrase or not replacement:
                print(f"Missing search_phrase or replacement for '{gap_id}' — skipping.")
                skipped.append(policy_name)
                continue

            if mime == DOCX_MIME:
                count = edit_docx_in_place(drive_service, file_id, search_phrase, replacement)
            else:
                count = edit_gdoc_in_place(docs_service, file_id, search_phrase, replacement)

            if count > 0:
                add_drive_comment(drive_service, file_id, (
                    f"[AY Policy Bot, {date_str}] Automated correction applied (Ref: {review_id})\n"
                    f"Changed: \"{search_phrase}\" → \"{replacement}\"\n"
                    f"Source: {source_name}, {source_url}"
                ))
                updated_docs[policy_name] = doc_url
            else:
                skipped.append(policy_name)

        elif gap_type == "missing_coverage":
            # Chad's multiple-choice answer (if any) is injected as _insert_text.
            insert_text = finding.get("_insert_text")
            if insert_text:
                insert_paragraph_in_docx(drive_service, file_id, insert_text)
                add_drive_comment(drive_service, file_id, (
                    f"[AY Policy Bot, {date_str}] Section added on approval (Ref: {review_id})\n"
                    f"Source: {source_name}, {source_url}"
                ))
            else:
                # No answer chosen, or "handle later": leave a note, no edit.
                action = finding.get("recommended_action") or finding.get("description", "")
                add_drive_comment(drive_service, file_id, (
                    f"[AY Policy Bot, {date_str}] ACTION REQUIRED (Ref: {review_id})\n"
                    f"{action}\n"
                    f"Source: {source_name}, {source_url}"
                ))
            updated_docs[policy_name] = doc_url

        elif gap_type == "expired_document":
            # Awareness only. The bot must never fake a valid document (e.g. insurance).
            action = finding.get("recommended_action") or finding.get("description", "")
            add_drive_comment(drive_service, file_id, (
                f"[AY Policy Bot, {date_str}] FOR AWARENESS, document out of date (Ref: {review_id})\n"
                f"{action}\n"
                f"Source: {source_name}, {source_url}"
            ))
            updated_docs[policy_name] = doc_url

        else:
            print(f"Unknown gap_type '{gap_type}' for '{gap_id}' — skipping.")
            skipped.append(policy_name)

    if skipped:
        print(f"Skipped {len(skipped)} finding(s): {skipped}")

    if not updated_docs:
        # Nothing was edited or commented. Do NOT pretend this succeeded by
        # silently creating a throwaway summary doc — that masks the real failure
        # (e.g. the bot's Google account lacks write access to the policy files,
        # or the search phrase did not match). Raise so /confirm surfaces the error.
        raise RuntimeError(
            "No policy documents were updated. "
            f"Skipped {len(skipped)} finding(s): {skipped}. "
            "Most likely cause: the authenticated Google account does not have "
            "editor access to the policy files in the Shared Drive, or the "
            "search phrase did not match the document text."
        )

    first_url = next(iter(updated_docs.values()))
    print(f"Done — {len(updated_docs)} document(s) updated.")
    return first_url


def _fallback_summary(drive_service, docs_service, findings, review_id: str) -> str:
    """Creates a summary doc only when no policy files could be found or edited."""
    date_str = datetime.utcnow().strftime("%d %B %Y")
    title = f"Elevate Policy Bot — Manual Action Required {date_str} [{review_id}]"
    lines = [title, "", f"Review ID: {review_id}", f"Date: {date_str}", "",
             "The bot could not locate or edit the policy documents.", ""]
    for i, f in enumerate(findings, 1):
        lines.append(f"FINDING {i}: {f.get('policy_name', '')}")
        lines.append(f.get("description", ""))
        if f.get("search_text") or f.get("wrong_reference"):
            lines.append(
                f"Change: '{f.get('search_text') or f.get('wrong_reference')}'"
                f" → '{f.get('correct_reference', '')}'"
            )
        elif f.get("recommended_action"):
            lines.append(f"Action: {f['recommended_action']}")
        lines.append("")

    doc = drive_service.files().create(
        body={"name": title, "mimeType": GDOC_MIME},
        supportsAllDrives=True,
    ).execute()
    doc_id = doc["id"]
    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"insertText": {"location": {"index": 1}, "text": "\n".join(lines)}}]},
    ).execute()
    url = f"https://docs.google.com/document/d/{doc_id}/edit"
    print(f"Fallback summary: {url}")
    return url
