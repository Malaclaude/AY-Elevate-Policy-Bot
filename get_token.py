"""
get_token.py — generate a fresh token.json for the policy bot.

Requires credentials.json (OAuth 2.0 client secrets, "Desktop app" type) in this
folder, downloaded from the Google Cloud project that has the Gmail, Drive, and
Docs APIs enabled.

Run:  python get_token.py

A browser opens. LOG IN AS AN ACCOUNT WITH WRITE ACCESS TO THE POLICY FILES:
    malachi@addingyou.com   (or)   info@addingyou.com
NOT a personal Gmail — those have no access to Elevate's Shared Drive.

On success it writes token.json. That file is what Railway needs as GOOGLE_TOKEN_JSON.
"""

import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/gmail.send",
]


def main():
    if not os.path.exists("credentials.json"):
        raise SystemExit(
            "credentials.json not found.\n"
            "Download it from Google Cloud Console > APIs & Services > Credentials >\n"
            "OAuth 2.0 Client IDs (Desktop app), and drop it in this folder."
        )

    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")

    with open("token.json", "w") as f:
        f.write(creds.to_json())

    print("\ntoken.json written.")
    print("Next: python diagnose_drive.py  (confirms the account can write)")


if __name__ == "__main__":
    main()
