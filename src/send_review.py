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
    """Build a clean HTML email showing the before/after and approve button."""
    approve_url = f"{APPROVE_BASE_URL}?id={review_id}"

    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 700px; margin: auto; padding: 20px;">

        <h2 style="color: #d9534f;">⚠️ Policy Review Required — Elevate Performance Academy</h2>
        <p><strong>Flagged by:</strong> AY Policy Bot</p>
        <p><strong>Date:</strong> {datetime.utcnow().strftime('%d %B %Y')}</p>
        <p><strong>Policy:</strong> Accessibility and Inclusiveness Policy</p>
        <p><strong>Severity:</strong> {correction['severity']}</p>

        <hr/>

        <h3>What the bot found</h3>
        <p>{correction['description']}</p>

        <h3>Original text</h3>
        <div style="background:#fff3f3; border-left:4px solid #d9534f; padding:12px; margin:10px 0;">
            <code>{correction['original_excerpt']}</code>
        </div>

        <h3>Suggested correction</h3>
        <div style="background:#f3fff3; border-left:4px solid #5cb85c; padding:12px; margin:10px 0;">
            <code>{correction['corrected_excerpt']}</code>
        </div>

        <p style="color:#888; font-size:12px;">
            Always read the original source before approving:
            <a href="https://www.legislation.gov.uk/ukpga/2010/15/contents">Equality Act 2010 — legislation.gov.uk</a>
        </p>

        <hr/>

        <h3>Your options</h3>
        <p>
            <a href="{approve_url}&action=approve"
               style="background:#5cb85c; color:white; padding:12px 24px; text-decoration:none; border-radius:4px; margin-right:10px;">
               ✅ Approve and publish
            </a>
            <a href="{approve_url}&action=reject"
               style="background:#d9534f; color:white; padding:12px 24px; text-decoration:none; border-radius:4px;">
               ❌ Reject / defer
            </a>
        </p>

        <p style="color:#888; font-size:11px; margin-top:30px;">
            This email was generated automatically by the AY Policy Bot.
            Review ID: {review_id}. Bot does not publish without your approval.
        </p>

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
    msg["Subject"] = f"[ACTION REQUIRED] Policy gap detected — Elevate Accessibility Policy"
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
