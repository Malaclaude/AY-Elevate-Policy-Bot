"""
send_review.py
Sends a formatted review packet email via Gmail API.
Includes before/after text and an approve link.
"""

import os
import base64
import json
import uuid
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

# Where approval clicks will go — replace with your Railway URL once deployed
# For local testing this uses a placeholder
APPROVE_BASE_URL = os.getenv("APPROVE_BASE_URL", "http://localhost:5000/approve")

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


def build_email_html(correction: dict, review_id: str) -> str:
    """Build a clean, professional HTML email showing the before/after and action buttons."""
    approve_url = f"{APPROVE_BASE_URL}?id={review_id}"
    date_str = datetime.utcnow().strftime('%d %B %Y')

    return f"""
    <html>
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0; padding:0; background-color:#f4f4f7; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">

      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f7; padding: 40px 20px;">
        <tr>
          <td align="center">
            <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff; border-radius:8px; overflow:hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">

              <!-- Header -->
              <tr>
                <td style="background:#1a1a2e; padding: 32px 40px;">
                  <p style="margin:0; color:#ffffff; font-size:13px; letter-spacing:2px; text-transform:uppercase; font-weight:600;">Adding You</p>
                  <h1 style="margin:8px 0 0; color:#ffffff; font-size:22px; font-weight:600; letter-spacing:-0.3px;">Policy Compliance Review</h1>
                </td>
              </tr>

              <!-- Status bar -->
              <tr>
                <td style="background:#f0f4ff; padding: 14px 40px; border-bottom: 1px solid #e8ecf4;">
                  <table cellpadding="0" cellspacing="0" width="100%">
                    <tr>
                      <td style="font-size:13px; color:#555;">
                        <strong style="color:#1a1a2e;">Client:</strong> Elevate Performance Academy
                      </td>
                      <td align="right" style="font-size:13px; color:#555;">
                        <strong style="color:#1a1a2e;">Date:</strong> {date_str}
                      </td>
                    </tr>
                    <tr>
                      <td style="font-size:13px; color:#555; padding-top:4px;">
                        <strong style="color:#1a1a2e;">Policy:</strong> Accessibility and Inclusiveness Policy
                      </td>
                      <td align="right" style="font-size:13px; color:#555; padding-top:4px;">
                        <span style="background:#fff0f0; color:#c0392b; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600;">Action Required</span>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding: 36px 40px;">

                  <p style="margin:0 0 20px; font-size:15px; color:#333; line-height:1.6;">
                    Our compliance monitoring system has identified an issue in Elevate's Accessibility and Inclusiveness Policy that requires your review and approval before it can be corrected.
                  </p>

                  <!-- Issue box -->
                  <table cellpadding="0" cellspacing="0" width="100%" style="margin-bottom:28px;">
                    <tr>
                      <td style="background:#fffbf0; border:1px solid #f0d080; border-radius:6px; padding:20px 24px;">
                        <p style="margin:0 0 6px; font-size:12px; font-weight:700; letter-spacing:1px; text-transform:uppercase; color:#b8860b;">Issue Identified</p>
                        <p style="margin:0; font-size:14px; color:#333; line-height:1.6;">{correction['description']}</p>
                      </td>
                    </tr>
                  </table>

                  <!-- Current text -->
                  <p style="margin:0 0 8px; font-size:13px; font-weight:700; color:#888; letter-spacing:0.5px; text-transform:uppercase;">Current Policy Text</p>
                  <table cellpadding="0" cellspacing="0" width="100%" style="margin-bottom:24px;">
                    <tr>
                      <td style="background:#fff5f5; border-left:3px solid #e74c3c; border-radius:0 4px 4px 0; padding:16px 20px;">
                        <p style="margin:0; font-size:14px; color:#555; line-height:1.7; font-style:italic;">{correction['original_excerpt']}</p>
                      </td>
                    </tr>
                  </table>

                  <!-- Suggested correction -->
                  <p style="margin:0 0 8px; font-size:13px; font-weight:700; color:#888; letter-spacing:0.5px; text-transform:uppercase;">Suggested Correction</p>
                  <table cellpadding="0" cellspacing="0" width="100%" style="margin-bottom:12px;">
                    <tr>
                      <td style="background:#f0faf4; border-left:3px solid #27ae60; border-radius:0 4px 4px 0; padding:16px 20px;">
                        <p style="margin:0; font-size:14px; color:#333; line-height:1.7;">{correction['corrected_excerpt']}</p>
                      </td>
                    </tr>
                  </table>

                  <p style="margin:0 0 32px; font-size:12px; color:#999;">
                    Source: <a href="https://www.legislation.gov.uk/ukpga/2010/15/contents" style="color:#4a90d9; text-decoration:none;">Equality Act 2010, legislation.gov.uk</a>
                  </p>

                  <!-- Divider -->
                  <table cellpadding="0" cellspacing="0" width="100%" style="margin-bottom:28px;">
                    <tr><td style="border-top:1px solid #eee;"></td></tr>
                  </table>

                  <p style="margin:0 0 20px; font-size:15px; color:#333; font-weight:600;">Do you approve this correction?</p>

                  <!-- Buttons -->
                  <table cellpadding="0" cellspacing="0">
                    <tr>
                      <td style="padding-right:12px;">
                        <a href="{approve_url}&action=approve"
                           style="display:inline-block; background:#27ae60; color:#ffffff; font-size:14px; font-weight:600; padding:14px 28px; border-radius:6px; text-decoration:none; letter-spacing:0.3px;">
                          Approve Correction
                        </a>
                      </td>
                      <td>
                        <a href="{approve_url}&action=reject"
                           style="display:inline-block; background:#ffffff; color:#555; font-size:14px; font-weight:600; padding:13px 28px; border-radius:6px; text-decoration:none; letter-spacing:0.3px; border:1px solid #ddd;">
                          Decline
                        </a>
                      </td>
                    </tr>
                  </table>

                  <p style="margin:28px 0 0; font-size:13px; color:#999; line-height:1.6;">
                    Approving will publish the corrected text to the Elevate policy folder. No changes are made without your explicit approval.
                  </p>

                </td>
              </tr>

              <!-- Footer -->
              <tr>
                <td style="background:#f8f9fb; border-top:1px solid #eee; padding:24px 40px;">
                  <table cellpadding="0" cellspacing="0" width="100%">
                    <tr>
                      <td style="font-size:12px; color:#aaa; line-height:1.6;">
                        Adding You Ltd. | addingyou.com<br>
                        This is an automated compliance alert. Reference: {review_id}
                      </td>
                      <td align="right" style="font-size:12px; color:#aaa;">
                        Elevate Policy Bot
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>

            </table>
          </td>
        </tr>
      </table>

    </body>
    </html>
    """


def send_review_email(correction: dict) -> str:
    """
    Main function: saves the review, builds the email, sends it via Gmail.
    Returns the review_id.
    """
    review_id = generate_review_id()
    save_pending_review(review_id, correction)

    service = get_gmail_service()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Action Required: Policy Correction Review - Elevate Performance Academy"
    msg["From"] = SENDER_EMAIL
    msg["To"] = REVIEWER_EMAIL

    html_content = build_email_html(correction, review_id)
    msg.attach(MIMEText(html_content, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()

    print(f"Review email sent to {REVIEWER_EMAIL} (Review ID: {review_id})")
    return review_id


if __name__ == "__main__":
    # Test with sample correction data
    sample_correction = {
        "original_excerpt": "In accordance with the Americans with Disabilities Act, we ensure all facilities are accessible.",
        "corrected_excerpt": "In accordance with the Equality Act 2010 and the Public Sector Equality Duty (Section 149), we ensure all facilities are accessible to participants with protected characteristics.",
        "wrong_reference": "Americans with Disabilities Act",
        "correct_reference": "Equality Act 2010",
        "severity": "High",
        "description": "Policy references US law (Americans with Disabilities Act) instead of the UK Equality Act 2010.",
    }
    send_review_email(sample_correction)
