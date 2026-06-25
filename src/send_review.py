"""
send_review.py
Sends a formatted policy audit email via Gmail API.
Shows ALL findings, each with its official source link beside it.
One Approve / Decline button pair covers the whole batch.
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

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

APPROVE_BASE_URL = os.getenv(
    "APPROVE_BASE_URL",
    "https://ay-elevate-policy-bot-production.up.railway.app/approve",
)
RAILWAY_REGISTER_URL = os.getenv(
    "RAILWAY_REGISTER_URL",
    "https://ay-elevate-policy-bot-production.up.railway.app/register",
)
REVIEWER_EMAIL = os.getenv("REVIEWER_EMAIL", "malachiavstreih@gmail.com")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "joelleonmcfarlane@outlook.com")


def get_gmail_service():
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
            with open("token.json", "w") as token:
                token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def generate_review_id() -> str:
    return str(uuid.uuid4())[:8]


def save_pending_review(review_id: str, findings: list):
    os.makedirs("data", exist_ok=True)
    pending_path = "data/pending_reviews.json"
    pending = {}
    if os.path.exists(pending_path):
        with open(pending_path) as f:
            pending = json.load(f)
    pending[review_id] = {
        "findings": findings,
        "created_at": datetime.utcnow().isoformat(),
        "status": "pending",
    }
    with open(pending_path, "w") as f:
        json.dump(pending, f, indent=2)
    print(f"Review saved with ID: {review_id}")

    # Push to Railway so the webhook can find it
    try:
        resp = http_requests.post(RAILWAY_REGISTER_URL, json={
            "review_id": review_id,
            "findings": findings,
            "created_at": datetime.utcnow().isoformat(),
        }, timeout=10)
        if resp.status_code == 200:
            print(f"Review registered on Railway ({review_id})")
        else:
            print(f"Warning: Railway register returned {resp.status_code}")
    except Exception as e:
        print(f"Warning: Could not register on Railway: {e}")


def encode_findings(findings: list) -> str:
    payload = json.dumps(findings, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _severity_badge(severity: str) -> str:
    if severity == "High":
        return (
            '<span style="display:inline-block; background:#fef2f2; color:#b91c1c; '
            'font-size:10px; font-weight:700; letter-spacing:0.8px; text-transform:uppercase; '
            'padding:4px 10px; border-radius:100px; border:1px solid #fecaca;">High</span>'
        )
    return (
        '<span style="display:inline-block; background:#fffbeb; color:#92400e; '
        'font-size:10px; font-weight:700; letter-spacing:0.8px; text-transform:uppercase; '
        'padding:4px 10px; border-radius:100px; border:1px solid #fde68a;">Medium</span>'
    )


def _finding_card(finding: dict, index: int) -> str:
    """Render one finding as an HTML card. Source link always present."""
    severity_badge = _severity_badge(finding["severity"])
    source_name = finding["source"]["name"]
    source_url = finding["source"]["url"]
    policy_name = finding["policy_name"]
    description = finding["description"]

    gap_type = finding.get("gap_type", "")
    original = finding.get("original_excerpt") or ""
    corrected = finding.get("corrected_excerpt") or ""

    # Before/after section for text-correction findings
    before_after = ""
    if original and corrected and gap_type in ("wrong_reference", "outdated_reference"):
        before_after = f"""
                <p style="margin:16px 0 6px; font-size:10px; font-weight:700; letter-spacing:1.2px; text-transform:uppercase; color:#94a3b8;">Current text</p>
                <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom:14px;">
                  <tr>
                    <td style="background:#fff8f8; border:1px solid #fee2e2; border-left:4px solid #ef4444; border-radius:0 8px 8px 0; padding:14px 18px;">
                      <p style="margin:0; font-size:13px; color:#7f1d1d; line-height:1.75; font-style:italic;">{original}</p>
                    </td>
                  </tr>
                </table>
                <p style="margin:0 0 6px; font-size:10px; font-weight:700; letter-spacing:1.2px; text-transform:uppercase; color:#94a3b8;">Suggested correction</p>
                <table cellpadding="0" cellspacing="0" border="0" width="100%">
                  <tr>
                    <td style="background:#f0fdf4; border:1px solid #bbf7d0; border-left:4px solid #16a34a; border-radius:0 8px 8px 0; padding:14px 18px;">
                      <p style="margin:0; font-size:13px; color:#14532d; line-height:1.75;">{corrected}</p>
                    </td>
                  </tr>
                </table>"""

    elif corrected and gap_type in ("missing_coverage", "expired_document"):
        before_after = f"""
                <p style="margin:16px 0 6px; font-size:10px; font-weight:700; letter-spacing:1.2px; text-transform:uppercase; color:#94a3b8;">Recommended action</p>
                <table cellpadding="0" cellspacing="0" border="0" width="100%">
                  <tr>
                    <td style="background:#f0f9ff; border:1px solid #bae6fd; border-left:4px solid #0284c7; border-radius:0 8px 8px 0; padding:14px 18px;">
                      <p style="margin:0; font-size:13px; color:#0c4a6e; line-height:1.75;">{corrected}</p>
                    </td>
                  </tr>
                </table>"""

    return f"""
          <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom:16px; border:1px solid #e2e8f0; border-radius:12px; overflow:hidden;">
            <tr>
              <td style="padding:20px 24px;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%">
                  <tr>
                    <td valign="middle">
                      <p style="margin:0; font-size:11px; font-weight:700; letter-spacing:1px; text-transform:uppercase; color:#94a3b8;">Finding {index + 1} &nbsp;&middot;&nbsp; {policy_name}</p>
                    </td>
                    <td align="right" valign="middle">{severity_badge}</td>
                  </tr>
                </table>
                <p style="margin:10px 0 8px; font-size:14px; color:#334155; line-height:1.65;">{description}</p>
                <p style="margin:0; font-size:12px;">
                  <span style="color:#94a3b8;">Source: </span>
                  <a href="{source_url}" style="color:#3b82f6; text-decoration:none; font-weight:500;">{source_name} &rarr;</a>
                </p>
                {before_after}
              </td>
            </tr>
          </table>"""


def build_email_html(findings: list, review_id: str) -> str:
    encoded = encode_findings(findings)
    approve_url = f"{APPROVE_BASE_URL}?id={review_id}&d={encoded}"
    date_str = datetime.utcnow().strftime("%d %B %Y")
    count = len(findings)
    high_count = sum(1 for f in findings if f.get("severity") == "High")
    med_count = count - high_count

    finding_cards_html = "".join(_finding_card(f, i) for i, f in enumerate(findings))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Policy audit — {count} issue{'s' if count != 1 else ''} found</title>
</head>
<body style="margin:0; padding:0; background-color:#f1f5f9; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; -webkit-font-smoothing:antialiased;">

  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f1f5f9; padding:48px 16px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff; border-radius:16px; overflow:hidden; border:1px solid #e2e8f0;">

          <!-- Top bar -->
          <tr><td style="background:#0f172a; height:5px; font-size:0; line-height:0;">&nbsp;</td></tr>

          <!-- Header -->
          <tr>
            <td style="padding:36px 48px 24px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td>
                    <p style="margin:0 0 8px; font-size:11px; font-weight:700; letter-spacing:2.5px; text-transform:uppercase; color:#94a3b8;">Adding You</p>
                    <h1 style="margin:0; font-size:26px; font-weight:700; color:#0f172a; letter-spacing:-0.5px; line-height:1.2;">Policy compliance audit</h1>
                  </td>
                  <td align="right" valign="middle" style="padding-left:16px; white-space:nowrap;">
                    <span style="display:inline-block; background:#fef2f2; color:#b91c1c; font-size:11px; font-weight:700; letter-spacing:0.8px; text-transform:uppercase; padding:6px 14px; border-radius:100px; border:1px solid #fecaca;">{count} issue{'s' if count != 1 else ''} found</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Divider -->
          <tr><td style="padding:0 48px;"><div style="height:1px; background:#f1f5f9; font-size:0;">&nbsp;</div></td></tr>

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
                    <p style="margin:0 0 3px; font-size:10px; font-weight:700; letter-spacing:1.2px; text-transform:uppercase; color:#94a3b8;">Issues</p>
                    <p style="margin:0; font-size:13px; font-weight:600; color:#334155;">{high_count} High &nbsp;&middot;&nbsp; {med_count} Medium</p>
                  </td>
                  <td>
                    <p style="margin:0 0 3px; font-size:10px; font-weight:700; letter-spacing:1.2px; text-transform:uppercase; color:#94a3b8;">Run date</p>
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
                Monthly compliance check complete. {count} issue{'s were' if count != 1 else ' was'} found across Elevate's policy set.
                Every finding below is linked to the official source it was checked against — click any source link to verify the reference directly.
                No changes are made until you approve.
              </p>

              {finding_cards_html}

              <!-- Divider -->
              <div style="height:1px; background:#f1f5f9; margin:28px 0; font-size:0;">&nbsp;</div>

              <p style="margin:0 0 6px; font-size:17px; font-weight:700; color:#0f172a;">Approve all corrections?</p>
              <p style="margin:0 0 24px; font-size:14px; color:#64748b; line-height:1.6;">
                Clicking Approve publishes a full correction report to the Elevate Google Drive folder and logs the decision.
                Clicking Decline logs the decision with no changes made.
              </p>

              <table cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="padding-right:12px;">
                    <a href="{approve_url}&action=approve"
                       style="display:inline-block; background:#0f172a; color:#ffffff; font-size:14px; font-weight:600; padding:15px 32px; border-radius:10px; text-decoration:none; letter-spacing:0.1px;">
                      Approve corrections
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
                &nbsp;&middot;&nbsp; Automated compliance audit
                &nbsp;&middot;&nbsp; Ref: {review_id}
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>"""


def send_review_email(findings_or_correction) -> str:
    """
    Main entry point.
    Accepts either a list of findings (new multi-finding flow)
    or a single correction dict (legacy flow from scheduler).
    Returns the review_id.
    """
    if isinstance(findings_or_correction, dict):
        findings = [findings_or_correction]
    else:
        findings = findings_or_correction

    review_id = generate_review_id()
    save_pending_review(review_id, findings)

    service = get_gmail_service()

    count = len(findings)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Policy audit — {count} issue{'s' if count != 1 else ''} found — Elevate Performance Academy"
    msg["From"] = SENDER_EMAIL
    msg["To"] = REVIEWER_EMAIL

    html_content = build_email_html(findings, review_id)
    msg.attach(MIMEText(html_content, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()

    print(f"Review email sent to {REVIEWER_EMAIL} (Review ID: {review_id}, {count} finding(s))")
    return review_id
