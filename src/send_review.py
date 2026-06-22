"""
send_review.py
Sends a formatted review packet email via Gmail API.
Includes before/after text and approve/decline links.
"""

import os
import base64
import json
import uuid
import requests as http_requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
]

APPROVE_BASE_URL = os.getenv("APPROVE_BASE_URL", "https://ay-elevate-policy-bot-production.up.railway.app/approve")
RAILWAY_REGISTER_URL = os.getenv("RAILWAY_REGISTER_URL", "https://ay-elevate-policy-bot-production.up.railway.app/register")
REVIEWER_EMAIL = os.getenv("REVIEWER_EMAIL", "malachiavstreih@gmail.com")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "joelleonmcfarlane@outlook.com")


def get_gmail_service():
    """Authenticate and return Gmail API service."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def generate_review_id():
    """Generate a unique ID for this review so we can track approval."""
    return str(uuid.uuid4())[:8]


def save_pending_review(review_id: str, correction: dict):
    """Save the correction to a local JSON file so the webhook can retrieve it on approval."""
    os.makedirs("data", exist_ok=True)
    pending_path = "data/pending_reviews.json"

    pending = {}
    if os.path.exists(pending_path):
        with open(pending_path) as f:
            pending = json.load(f)

    pending[review_id] = {
        "correction": correction,
        "created_at": datetime.utcnow().isoformat(),
        "status": "pending",
    }

    with open(pending_path, "w") as f:
        json.dump(pending, f, indent=2)

    print(f"Review saved with ID: {review_id}")

    # Push review to Railway so the approve webhook can find it
    try:
        resp = http_requests.post(RAILWAY_REGISTER_URL, json={
            "review_id": review_id,
            "correction": correction,
            "created_at": datetime.utcnow().isoformat(),
        }, timeout=10)
        if resp.status_code == 200:
            print(f"Review registered on Railway ({review_id})")
        else:
            print(f"Warning: Railway register returned {resp.status_code}")
    except Exception as e:
        print(f"Warning: Could not register review on Railway: {e}")


def encode_correction(correction: dict) -> str:
    """Base64-encode the correction so it can travel in the URL."""
    payload = json.dumps(correction, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode()


def build_email_html(correction: dict, review_id: str) -> str:
    """Build a premium, clean HTML review email."""
    encoded = encode_correction(correction)
    approve_url = f"{APPROVE_BASE_URL}?id={review_id}&d={encoded}"
    date_str = datetime.utcnow().strftime('%d %B %Y')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Policy Review Required</title>
</head>
<body style="margin:0; padding:0; background-color:#f1f5f9; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; -webkit-font-smoothing:antialiased;">

  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f1f5f9; padding:48px 16px;">
    <tr>
      <td align="center">

        <!-- Outer card -->
        <table width="560" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff; border-radius:16px; overflow:hidden; border:1px solid #e2e8f0;">

          <!-- Top colour bar -->
          <tr>
            <td style="background:#0f172a; height:5px; font-size:0; line-height:0;">&nbsp;</td>
          </tr>

          <!-- Header -->
          <tr>
            <td style="padding:36px 48px 24px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td>
                    <p style="margin:0 0 8px; font-size:11px; font-weight:700; letter-spacing:2.5px; text-transform:uppercase; color:#94a3b8;">Adding You</p>
                    <h1 style="margin:0; font-size:26px; font-weight:700; color:#0f172a; letter-spacing:-0.5px; line-height:1.2;">Policy review needed</h1>
                  </td>
                  <td align="right" valign="middle" style="padding-left:16px; white-space:nowrap;">
                    <span style="display:inline-block; background:#fef2f2; color:#b91c1c; font-size:11px; font-weight:700; letter-spacing:0.8px; text-transform:uppercase; padding:6px 14px; border-radius:100px; border:1px solid #fecaca;">Action needed</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Thin divider -->
          <tr>
            <td style="padding:0 48px;">
              <div style="height:1px; background:#f1f5f9; font-size:0;">&nbsp;</div>
            </td>
          </tr>

          <!-- Meta strip -->
          <tr>
            <td style="padding:18px 48px 28px;">
              <table cellpadding="0" cellspacing="8" border="0">
                <tr>
                  <td style="padding-right:28px;">
                    <p style="margin:0 0 3px; font-size:10px; font-weight:700; letter-spacing:1.2px; text-transform:uppercase; color:#94a3b8;">Client</p>
                    <p style="margin:0; font-size:13px; font-weight:600; color:#334155;">Elevate Performance Academy</p>
                  </td>
                  <td style="padding-right:28px;">
                    <p style="margin:0 0 3px; font-size:10px; font-weight:700; letter-spacing:1.2px; text-transform:uppercase; color:#94a3b8;">Policy</p>
                    <p style="margin:0; font-size:13px; font-weight:600; color:#334155;">Accessibility &amp; Inclusiveness</p>
                  </td>
                  <td>
                    <p style="margin:0 0 3px; font-size:10px; font-weight:700; letter-spacing:1.2px; text-transform:uppercase; color:#94a3b8;">Date</p>
                    <p style="margin:0; font-size:13px; font-weight:600; color:#334155;">{date_str}</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:0 48px 36px;">

              <p style="margin:0 0 24px; font-size:15px; color:#475569; line-height:1.7;">
                Our automated compliance system has identified an issue in the Accessibility and Inclusiveness Policy. A correction has been drafted below. No changes are made until you explicitly approve.
              </p>

              <!-- Issue callout -->
              <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom:28px;">
                <tr>
                  <td style="background:#fffbeb; border:1px solid #fde68a; border-radius:10px; padding:18px 22px;">
                    <p style="margin:0 0 5px; font-size:10px; font-weight:700; letter-spacing:1.2px; text-transform:uppercase; color:#92400e;">Issue identified</p>
                    <p style="margin:0; font-size:14px; color:#78350f; line-height:1.65;">{correction['description']}</p>
                  </td>
                </tr>
              </table>

              <!-- Before label -->
              <p style="margin:0 0 8px; font-size:10px; font-weight:700; letter-spacing:1.2px; text-transform:uppercase; color:#94a3b8;">Current text</p>
              <!-- Before block -->
              <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom:20px;">
                <tr>
                  <td style="background:#fff8f8; border:1px solid #fee2e2; border-left:4px solid #ef4444; border-radius:0 8px 8px 0; padding:16px 20px;">
                    <p style="margin:0; font-size:14px; color:#7f1d1d; line-height:1.75; font-style:italic;">{correction['original_excerpt']}</p>
                  </td>
                </tr>
              </table>

              <!-- After label -->
              <p style="margin:0 0 8px; font-size:10px; font-weight:700; letter-spacing:1.2px; text-transform:uppercase; color:#94a3b8;">Suggested correction</p>
              <!-- After block -->
              <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom:10px;">
                <tr>
                  <td style="background:#f0fdf4; border:1px solid #bbf7d0; border-left:4px solid #16a34a; border-radius:0 8px 8px 0; padding:16px 20px;">
                    <p style="margin:0; font-size:14px; color:#14532d; line-height:1.75;">{correction['corrected_excerpt']}</p>
                  </td>
                </tr>
              </table>

              <p style="margin:0 0 32px; font-size:12px; color:#94a3b8;">
                Source: <a href="https://www.legislation.gov.uk/ukpga/2010/15/contents" style="color:#3b82f6; text-decoration:none;">Equality Act 2010 &rarr;</a>
              </p>

              <!-- Divider -->
              <div style="height:1px; background:#f1f5f9; margin-bottom:28px; font-size:0;">&nbsp;</div>

              <p style="margin:0 0 6px; font-size:17px; font-weight:700; color:#0f172a;">Approve this correction?</p>
              <p style="margin:0 0 24px; font-size:14px; color:#64748b; line-height:1.6;">Clicking Approve publishes the corrected text to the Elevate Google Drive folder. Clicking Decline logs the decision with no changes made.</p>

              <!-- CTA buttons -->
              <table cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="padding-right:12px;">
                    <a href="{approve_url}&action=approve"
                       style="display:inline-block; background:#0f172a; color:#ffffff; font-size:14px; font-weight:600; padding:15px 32px; border-radius:10px; text-decoration:none; letter-spacing:0.1px;">
                      Approve correction
                    </a>
                  </td>
                  <td>
                    <a href="{approve_url}&action=reject"
                       style="display:inline-block; background:#ffffff; color:#64748b; font-size:14px; font-weight:500; padding:14px 24px; border-radius:10px; text-decoration:none; border:1px solid #cbd5e1;">
                      Decline
                    </a>
                  </td>
                </tr>
              </table>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#f8fafc; border-top:1px solid #f1f5f9; padding:20px 48px; border-radius:0 0 16px 16px;">
              <p style="margin:0; font-size:12px; color:#94a3b8; line-height:1.6;">
                <a href="https://addingyou.com" style="color:#94a3b8; text-decoration:none;">addingyou.com</a>
                &nbsp;&middot;&nbsp; Automated compliance alert
                &nbsp;&middot;&nbsp; Ref: {review_id}
              </p>
            </td>
          </tr>

        </table>
        <!-- End card -->

      </td>
    </tr>
  </table>

</body>
</html>"""


def send_review_email(correction: dict) -> str:
    """
    Main function: saves the review, builds the email, sends it via Gmail.
    Returns the review_id.
    """
    review_id = generate_review_id()
    save_pending_review(review_id, correction)

    service = get_gmail_service()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Policy Correction Review — Elevate Performance Academy"
    msg["From"] = SENDER_EMAIL
    msg["To"] = REVIEWER_EMAIL

    html_content = build_email_html(correction, review_id)
    msg.attach(MIMEText(html_content, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()

    print(f"Review email sent to {REVIEWER_EMAIL} (Review ID: {review_id})")
    return review_id


if __name__ == "__main__":
    sample_correction = {
        "original_excerpt": "In accordance with the Americans with Disabilities Act, we ensure all facilities are accessible.",
        "corrected_excerpt": "In accordance with the Equality Act 2010 and the Public Sector Equality Duty (Section 149), we ensure all facilities are accessible to participants with protected characteristics.",
        "wrong_reference": "Americans with Disabilities Act",
        "correct_reference": "Equality Act 2010",
        "severity": "High",
        "description": "Policy references US law (Americans with Disabilities Act) instead of the UK Equality Act 2010.",
    }
    send_review_email(sample_correction)
