"""
diagnose_drive.py — non-destructive Drive access check.

Answers the single open question: does the Google account behind token.json /
GOOGLE_TOKEN_JSON actually have WRITE access to Elevate's policy files in the
Shared Drive? Writes nothing. Just authenticates and reports.

Run:  python diagnose_drive.py
"""

import os
import json as _json

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

KNOWN_FILE_IDS = {
    "Accessibility and Inclusiveness Policy": "1HYXCO9UgJ_Jzd_RXVfLOoY_frUvFgoD4",
    "Safeguarding Policy": "1kZDRHmz4b-liBx_w8Nnwvxuz56GLtJow",
    "Company Policies folder": "1UEPmB6aW3n66PulFPFxNFS4I68pLveYh",
}


def load_creds():
    token_env = os.getenv("GOOGLE_TOKEN_JSON")
    if token_env:
        creds = Credentials.from_authorized_user_info(_json.loads(token_env), SCOPES)
        src = "GOOGLE_TOKEN_JSON env var"
    elif os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        src = "token.json file"
    else:
        raise SystemExit("No GOOGLE_TOKEN_JSON env var and no token.json file found.")

    if creds and creds.expired and creds.refresh_token:
        print("Token expired — attempting refresh...")
        creds.refresh(Request())
        print("Refresh OK.")
    if not creds.valid:
        raise SystemExit("Credentials invalid and could not be refreshed. Re-run get_token.py.")
    return creds, src


def main():
    creds, src = load_creds()
    print(f"Credential source: {src}\n")

    drive = build("drive", "v3", credentials=creds)

    about = drive.about().get(fields="user(emailAddress,displayName)").execute()
    user = about.get("user", {})
    bot_email = user.get("emailAddress", "?")
    print("=" * 60)
    print(f"BOT AUTHENTICATED AS: {bot_email}  ({user.get('displayName','')})")
    print("=" * 60)
    print("Policy files are shared with: malachi@addingyou.com, info@addingyou.com,")
    print("chad@elevate-performance.uk, louis@elevate-performance.uk")
    print("If the account above is NOT in that list, that IS the bug.\n")

    for name, fid in KNOWN_FILE_IDS.items():
        try:
            meta = drive.files().get(
                fileId=fid,
                fields="name,modifiedTime,capabilities(canEdit,canModifyContent),driveId",
                supportsAllDrives=True,
            ).execute()
            caps = meta.get("capabilities", {})
            can_edit = caps.get("canEdit") and caps.get("canModifyContent")
            verdict = "CAN WRITE" if can_edit else "READ-ONLY / NO ACCESS"
            shared = "Shared Drive" if meta.get("driveId") else "My Drive"
            print(f"[{verdict:22}] {name}")
            print(f"    modifiedTime: {meta.get('modifiedTime')}  ({shared})")
        except Exception as e:
            print(f"[ERROR / NO ACCESS    ] {name}")
            print(f"    {type(e).__name__}: {e}")
        print()

    print("If any policy shows READ-ONLY or ERROR, fix = share the 'Company Policies'")
    print("folder with the bot account above as Content manager (editor), OR regenerate")
    print("token.json from malachi@addingyou.com / info@addingyou.com via get_token.py.")


if __name__ == "__main__":
    main()
