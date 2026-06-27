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
import zlib
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
    """Compress + base64-encode findings for URL embedding.
    zlib at level 9 cuts ~3000-char JSON down to ~900 chars — safe for Safe Links."""
    payload = json.dumps(findings, separators=(",", ":"))
    compressed = zlib.compress(payload.encode("utf-8"), level=9)
    return base64.urlsafe_b64encode(compressed).decode()


def _left_border_color(severity: str, gap_type: str) -> str:
    if gap_type in ("missing_coverage", "expired_document"):
        return "#f59e0b"  # amber for action items
    return "#ef4444" if severity == "High" else "#f59e0b"


def _severity_badge(severity: str) -> str:
    if severity == "High":
        return (
            '<span style="display:inline-block;background:#fef2f2;color:#b91c1c;'
            'font-size:10px;font-weight:700;letter-spacing:0.8px;text-transform:uppercase;'
            'padding:3px 10px;border-radius:100px;border:1px solid #fecaca;">High</span>'
        )
    return (
        '<span style="display:inline-block;background:#fffbeb;color:#92400e;'
        'font-size:10px;font-weight:700;letter-spacing:0.8px;text-transform:uppercase;'
        'padding:3px 10px;border-radius:100px;border:1px solid #fde68a;">Medium</span>'
    )


def _finding_card(finding: dict, index: int) -> str:
    """Render one finding as a premium feature-card with left accent border."""
    severity = finding["severity"]
    severity_badge = _severity_badge(severity)
    source_name = finding["source"]["name"]
    source_url = finding["source"]["url"]
    policy_name = finding["policy_name"]
    description = finding["description"]
    gap_type = finding.get("gap_type", "")
    border_color = _left_border_color(severity, gap_type)

    # Type label for the card header
    type_labels = {
        "wrong_reference": "Wrong reference",
        "outdated_reference": "Outdated reference",
        "missing_coverage": "Missing coverage",
        "expired_document": "Expired document",
    }
    type_label = type_labels.get(gap_type, gap_type.replace("_", " ").title())

    # Action / correction block
    action_block = ""
    if gap_type in ("wrong_reference", "outdated_reference"):
        wrong = finding.get("wrong_reference", "")
        correct = finding.get("correct_reference", "")
        if wrong and correct:
            action_block = f"""
              <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-top:16px;">
                <tr>
                  <td width="50%" style="padding-right:8px;" valign="top">
                    <p style="margin:0 0 5px;font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#94a3b8;">Remove</p>
                    <p style="margin:0;font-size:13px;color:#7f1d1d;background:#fff8f8;border:1px solid #fee2e2;border-radius:8px;padding:10px 14px;line-height:1.6;">{wrong}</p>
                  </td>
                  <td width="50%" style="padding-left:8px;" valign="top">
                    <p style="margin:0 0 5px;font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#94a3b8;">Replace with</p>
                    <p style="margin:0;font-size:13px;color:#14532d;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:10px 14px;line-height:1.6;">{correct}</p>
                  </td>
                </tr>
              </table>"""
    elif gap_type in ("missing_coverage", "expired_document"):
        action = finding.get("recommended_action", "")
        if action:
            action_block = f"""
              <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-top:16px;">
                <tr>
                  <td style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:12px 16px;">
                    <p style="margin:0 0 3px;font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#92400e;">Action required</p>
                    <p style="margin:0;font-size:13px;color:#78350f;line-height:1.65;">{action}</p>
                  </td>
                </tr>
              </table>"""

    return f"""
          <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom:14px;border-radius:12px;overflow:hidden;border:1px solid #e2e8f0;">
            <tr>
              <td width="4" style="background:{border_color};font-size:0;">&nbsp;</td>
              <td style="padding:20px 22px 22px;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom:8px;">
                  <tr>
                    <td valign="middle">
                      <p style="margin:0;font-size:10px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:#94a3b8;">{type_label} &nbsp;&middot;&nbsp; {policy_name}</p>
                    </td>
                    <td align="right" valign="middle" style="white-space:nowrap;padding-left:12px;">{severity_badge}</td>
                  </tr>
                </table>
                <p style="margin:0 0 12px;font-size:14px;color:#334155;line-height:1.7;">{description}</p>
                <p style="margin:0;font-size:12px;color:#94a3b8;">Source: <a href="{source_url}" style="color:#3b82f6;text-decoration:none;font-weight:500;">{source_name} &rarr;</a></p>
                {action_block}
              </td>
            </tr>
          </table>"""


def build_email_html(findings: list, review_id: str, test_mode: bool = False) -> str:
    encoded = encode_findings(findings)
    test_param = "&test=1" if test_mode else ""
    base_url = f"{APPROVE_BASE_URL}?id={review_id}&d={encoded}{test_param}"
    approve_url = f"{base_url}&action=approve"
    decline_url = f"{base_url}&action=reject"

    date_str = datetime.utcnow().strftime("%d %B %Y")
    count = len(findings)
    high_count = sum(1 for f in findings if f.get("severity") == "High")
    med_count = count - high_count
    finding_cards_html = "".join(_finding_card(f, i) for i, f in enumerate(findings))
    test_banner = (
        '<tr><td style="padding:0 48px 0;"><table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td style="background:#fef9c3;border:1px solid #fde68a;border-radius:10px;padding:10px 18px;margin-bottom:0;">'
        '<p style="margin:0;font-size:12px;font-weight:700;color:#92400e;">TEST MODE &mdash; buttons are live but no changes will be written to Drive.</p>'
        '</td></tr></table></td></tr>'
    ) if test_mode else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>Policy audit &mdash; {count} issue{'s' if count != 1 else ''} found</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">

  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f1f5f9;padding:40px 16px 56px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;background:#fff;border-radius:20px;overflow:hidden;border:1px solid #e2e8f0;box-shadow:0 2px 16px rgba(0,0,0,0.06);">

          <!-- Accent bar -->
          <tr><td style="background:#0f172a;height:6px;font-size:0;">&nbsp;</td></tr>

          <!-- Header -->
          <tr>
            <td style="padding:40px 48px 28px;">
              <p style="margin:0 0 10px;font-size:11px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#94a3b8;">Adding You &nbsp;&middot;&nbsp; Policy Bot</p>
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td valign="middle">
                    <h1 style="margin:0;font-size:28px;font-weight:800;color:#0f172a;letter-spacing:-0.5px;line-height:1.15;">Policy compliance<br>audit complete.</h1>
                  </td>
                  <td align="right" valign="top" style="padding-left:16px;white-space:nowrap;">
                    <span style="display:inline-block;background:#fef2f2;color:#b91c1c;font-size:11px;font-weight:700;letter-spacing:0.8px;text-transform:uppercase;padding:6px 14px;border-radius:100px;border:1px solid #fecaca;">{count} issue{'s' if count != 1 else ''}</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          {test_banner}

          <!-- Stats strip -->
          <tr>
            <td style="padding:0 48px 28px;">
              <table cellpadding="0" cellspacing="0" border="0" style="background:#f8fafc;border-radius:12px;width:100%;border:1px solid #f1f5f9;">
                <tr>
                  <td style="padding:18px 24px;border-right:1px solid #e2e8f0;" width="33%">
                    <p style="margin:0 0 3px;font-size:10px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:#94a3b8;">Client</p>
                    <p style="margin:0;font-size:13px;font-weight:600;color:#0f172a;">Elevate Performance Academy</p>
                  </td>
                  <td style="padding:18px 24px;border-right:1px solid #e2e8f0;" width="33%">
                    <p style="margin:0 0 3px;font-size:10px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:#94a3b8;">Findings</p>
                    <p style="margin:0;font-size:13px;font-weight:600;color:#0f172a;">{high_count} High &nbsp;&middot;&nbsp; {med_count} Medium</p>
                  </td>
                  <td style="padding:18px 24px;" width="33%">
                    <p style="margin:0 0 3px;font-size:10px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:#94a3b8;">Run date</p>
                    <p style="margin:0;font-size:13px;font-weight:600;color:#0f172a;">{date_str}</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Intro -->
          <tr>
            <td style="padding:0 48px 24px;">
              <p style="margin:0;font-size:15px;color:#475569;line-height:1.75;">
                The monthly compliance check found {count} issue{'s' if count != 1 else ''} across Elevate's policy set.
                Each finding is linked to the official UK source it was checked against.
                <strong style="color:#0f172a;">No changes are made until you approve.</strong>
              </p>
            </td>
          </tr>

          <!-- Findings -->
          <tr>
            <td style="padding:0 48px 32px;">
              {finding_cards_html}
            </td>
          </tr>

          <!-- CTA block -->
          <tr>
            <td style="padding:0 48px 40px;">
              <table cellpadding="0" cellspacing="0" border="0" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:16px;width:100%;">
                <tr>
                  <td style="padding:28px 32px;text-align:center;">
                    <p style="margin:0 0 6px;font-size:18px;font-weight:700;color:#0f172a;">Ready to apply these corrections?</p>
                    <p style="margin:0 0 24px;font-size:14px;color:#64748b;line-height:1.6;">One click applies all corrections directly to your policy documents in Google Drive.</p>
                    <a href="{approve_url}"
                       style="display:inline-block;background:#0f172a;color:#ffffff;font-size:15px;font-weight:700;padding:17px 40px;border-radius:12px;text-decoration:none;letter-spacing:0.1px;">
                      Approve all corrections &rarr;
                    </a>
                    <p style="margin:16px 0 0;font-size:12px;color:#94a3b8;">
                      Not ready? <a href="{decline_url}" style="color:#64748b;text-decoration:underline;">Decline and log for review</a>
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#f8fafc;border-top:1px solid #e2e8f0;padding:20px 48px;border-radius:0 0 20px 20px;">
              <p style="margin:0;font-size:12px;color:#94a3b8;line-height:1.7;">
                <a href="https://addingyou.com" style="color:#94a3b8;text-decoration:none;font-weight:600;">addingyou.com</a>
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


def send_review_email(findings_or_correction, test_mode: bool = False) -> str:
    """
    Main entry point.
    Accepts either a list of findings (new multi-finding flow)
    or a single correction dict (legacy flow from scheduler).
    test_mode=True: all buttons work but no changes are written to Drive.
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
    subject_prefix = "[TEST] " if test_mode else ""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{subject_prefix}Policy audit — {count} issue{'s' if count != 1 else ''} found — Elevate Performance Academy"
    msg["From"] = SENDER_EMAIL
    msg["To"] = REVIEWER_EMAIL

    html_content = build_email_html(findings, review_id, test_mode=test_mode)
    msg.attach(MIMEText(html_content, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()

    mode_label = "TEST MODE — no Drive changes" if test_mode else "live"
    print(f"Review email sent to {REVIEWER_EMAIL} (Review ID: {review_id}, {count} finding(s), {mode_label})")
    return review_id
