"""
send_review.py
Sends a formatted policy audit email via Gmail API.
Formal, monochrome layout that reads cleanly in both light and dark Gmail.
Each finding has its OWN approve control, so the reviewer approves policy by
policy. An "approve all remaining" option is offered as a convenience.
Approve opens in a new tab so the reviewer's inbox is never disturbed.
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
REVIEWER_EMAIL = os.getenv(
    "REVIEWER_EMAIL",
    "chad@elevate-performance.uk,louis@elevate-performance.uk,malachi@addingyou.com",
)
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
    zlib at level 9 keeps even the all-findings payload short for Safe Links."""
    payload = json.dumps(findings, separators=(",", ":"))
    compressed = zlib.compress(payload.encode("utf-8"), level=9)
    return base64.urlsafe_b64encode(compressed).decode()


def _action_url(payload_findings, review_id: str, action: str, test_mode: bool) -> str:
    enc = encode_findings(payload_findings)
    test_param = "&test=1" if test_mode else ""
    return f"{APPROVE_BASE_URL}?id={review_id}&d={enc}{test_param}&action={action}"


# ── Monochrome card rendering ────────────────────────────────────────────────

def _severity_label(severity: str) -> str:
    word = "High priority" if severity == "High" else "Medium priority"
    return (
        f'<span style="font-size:11px;font-weight:700;letter-spacing:0.6px;'
        f'text-transform:uppercase;color:#8a8a8a;">{word}</span>'
    )


def _finding_card(finding: dict, index: int, review_id: str, test_mode: bool) -> str:
    """One finding, monochrome, with its own approve / skip controls."""
    severity = finding["severity"]
    source_name = finding["source"]["name"]
    source_url = finding["source"]["url"]
    policy_name = finding["policy_name"]
    description = finding["description"]
    gap_type = finding.get("gap_type", "")

    type_labels = {
        "wrong_reference": "Wrong reference",
        "outdated_reference": "Outdated reference",
        "missing_coverage": "Missing coverage",
        "expired_document": "Expired document",
    }
    type_label = type_labels.get(gap_type, gap_type.replace("_", " ").title())

    detail = ""
    if gap_type in ("wrong_reference", "outdated_reference"):
        wrong = finding.get("wrong_reference", "")
        correct = finding.get("correct_reference", "")
        if wrong and correct:
            detail = f"""
              <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-top:18px;border-top:1px solid #ececec;">
                <tr>
                  <td style="padding:14px 0 4px;" valign="top">
                    <p style="margin:0 0 3px;font-size:11px;font-weight:700;letter-spacing:0.6px;text-transform:uppercase;color:#a0a0a0;">Currently</p>
                    <p style="margin:0;font-size:14px;color:#8a8a8a;text-decoration:line-through;line-height:1.6;">{wrong}</p>
                  </td>
                </tr>
                <tr>
                  <td style="padding:10px 0 0;" valign="top">
                    <p style="margin:0 0 3px;font-size:11px;font-weight:700;letter-spacing:0.6px;text-transform:uppercase;color:#a0a0a0;">Corrected to</p>
                    <p style="margin:0;font-size:14px;color:#1a1a1a;font-weight:700;line-height:1.6;">{correct}</p>
                  </td>
                </tr>
              </table>"""
    elif gap_type in ("missing_coverage", "expired_document"):
        action = finding.get("recommended_action", "")
        if action:
            detail = f"""
              <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-top:18px;border-top:1px solid #ececec;">
                <tr>
                  <td style="padding:14px 0 0;">
                    <p style="margin:0 0 3px;font-size:11px;font-weight:700;letter-spacing:0.6px;text-transform:uppercase;color:#a0a0a0;">Action required</p>
                    <p style="margin:0;font-size:14px;color:#3a3a3a;line-height:1.65;">{action}</p>
                  </td>
                </tr>
              </table>"""

    approve_url = _action_url([finding], review_id, "approve", test_mode)
    skip_url = _action_url([finding], review_id, "reject", test_mode)

    return f"""
          <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom:16px;background:#ffffff;border:1px solid #e6e6e6;border-radius:14px;">
            <tr>
              <td style="padding:24px 26px 26px;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom:10px;">
                  <tr>
                    <td valign="middle">
                      <span style="font-size:11px;font-weight:700;letter-spacing:0.6px;text-transform:uppercase;color:#1a1a1a;">{index + 1}. {type_label}</span>
                    </td>
                    <td align="right" valign="middle" style="white-space:nowrap;padding-left:12px;">{_severity_label(severity)}</td>
                  </tr>
                </table>
                <p style="margin:0 0 8px;font-size:17px;font-weight:700;color:#1a1a1a;letter-spacing:-0.2px;">{policy_name}</p>
                <p style="margin:0;font-size:14px;color:#5a5a5a;line-height:1.7;">{description}</p>
                {detail}
                <p style="margin:16px 0 0;font-size:12px;color:#9a9a9a;">Checked against <a href="{source_url}" style="color:#5a5a5a;text-decoration:underline;">{source_name}</a></p>
                <table cellpadding="0" cellspacing="0" border="0" style="margin-top:20px;">
                  <tr>
                    <td>
                      <a href="{approve_url}" target="_blank" style="display:inline-block;background:#1a1a1a;color:#ffffff;font-size:13px;font-weight:700;padding:12px 26px;border-radius:8px;text-decoration:none;letter-spacing:0.2px;">Approve this correction</a>
                    </td>
                    <td style="padding-left:18px;">
                      <a href="{skip_url}" target="_blank" style="font-size:13px;font-weight:600;color:#9a9a9a;text-decoration:none;">Skip</a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
          </table>"""


def build_email_html(findings: list, review_id: str, test_mode: bool = False) -> str:
    date_str = datetime.utcnow().strftime("%d %B %Y")
    count = len(findings)
    issue_word = "issue" if count == 1 else "issues"
    high_count = sum(1 for f in findings if f.get("severity") == "High")
    med_count = count - high_count
    finding_cards_html = "".join(
        _finding_card(f, i, review_id, test_mode) for i, f in enumerate(findings)
    )
    approve_all_url = _action_url(findings, review_id, "approve", test_mode)
    decline_all_url = _action_url(findings, review_id, "reject", test_mode)

    test_banner = (
        '<tr><td style="padding:0 40px 8px;"><table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td style="background:#f3f3f3;border:1px solid #dcdcdc;border-radius:10px;padding:11px 18px;text-align:center;">'
        '<p style="margin:0;font-size:12px;font-weight:700;color:#555;">TEST MODE. Buttons are live but nothing is written to Drive.</p>'
        '</td></tr></table></td></tr>'
    ) if test_mode else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <meta name="color-scheme" content="light dark">
  <meta name="supported-color-schemes" content="light dark">
  <title>Policy audit, {count} {issue_word} found</title>
  <style>
    @media (prefers-color-scheme: dark) {{
      .bg {{ background:#0f0f10 !important; }}
      .card {{ background:#1a1a1b !important; border-color:#2c2c2e !important; }}
      .ink {{ color:#f2f2f2 !important; }}
      .ink-soft {{ color:#bdbdbd !important; }}
      .muted {{ color:#8a8a8a !important; }}
      .rule {{ border-color:#2c2c2e !important; }}
      .chip {{ background:#161617 !important; border-color:#2c2c2e !important; }}
    }}
  </style>
</head>
<body class="bg" style="margin:0;padding:0;background:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">

  <table width="100%" cellpadding="0" cellspacing="0" border="0" class="bg" style="background:#f4f4f5;padding:34px 14px 50px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" border="0" class="card" style="max-width:600px;background:#ffffff;border:1px solid #e6e6e6;border-radius:22px;overflow:hidden;">

          <!-- Hero (kept, refined) -->
          <tr>
            <td bgcolor="#ece7fb" style="background:#ece7fb;background:linear-gradient(160deg,#e7defb 0%,#f3e3f4 50%,#fbfbfd 100%);padding:46px 40px 40px;text-align:center;">
              <p style="margin:0 0 24px;font-size:12px;font-weight:800;letter-spacing:3.5px;text-transform:uppercase;color:#4b3f63;">Adding You</p>
              <h1 style="margin:0 0 14px;font-size:31px;font-weight:800;color:#1d1730;letter-spacing:-0.7px;line-height:1.16;">Your policies,<br>checked and current.</h1>
              <p style="margin:0 auto;max-width:430px;font-size:15px;color:#4a4458;line-height:1.7;">This month's compliance audit for Elevate Performance Academy found {count} {issue_word} to review. Approve each correction below, or all at once.</p>
            </td>
          </tr>

          {test_banner}

          <!-- Summary line -->
          <tr>
            <td style="padding:30px 40px 6px;">
              <p class="muted" style="margin:0;font-size:13px;color:#8a8a8a;font-weight:600;">
                {count} {issue_word} &nbsp;|&nbsp; {high_count} high, {med_count} medium &nbsp;|&nbsp; {date_str}
              </p>
              <p class="ink" style="margin:10px 0 0;font-size:15px;color:#2a2a2a;line-height:1.7;">
                Each correction is checked against its official UK source. Nothing is changed in your documents until you approve it.
              </p>
            </td>
          </tr>

          <!-- Findings -->
          <tr>
            <td style="padding:22px 40px 8px;">
              {finding_cards_html}
            </td>
          </tr>

          <!-- Approve all (convenience) -->
          <tr>
            <td style="padding:14px 40px 40px;">
              <table cellpadding="0" cellspacing="0" border="0" width="100%" class="chip" style="background:#fafafa;border:1px solid #ececec;border-radius:14px;">
                <tr>
                  <td style="padding:24px 28px;text-align:center;">
                    <p class="ink" style="margin:0 0 16px;font-size:15px;color:#2a2a2a;font-weight:600;">Happy with everything?</p>
                    <a href="{approve_all_url}" target="_blank" style="display:inline-block;background:#1a1a1a;color:#ffffff;font-size:14px;font-weight:700;padding:14px 34px;border-radius:9px;text-decoration:none;letter-spacing:0.2px;">Approve all corrections</a>
                    <p style="margin:16px 0 0;font-size:12px;">
                      <a href="{decline_all_url}" target="_blank" class="muted" style="color:#9a9a9a;text-decoration:underline;">Decline all and log for review</a>
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td class="chip rule" style="background:#fafafa;border-top:1px solid #ececec;padding:20px 40px;text-align:center;">
              <p class="muted" style="margin:0;font-size:12px;color:#9a9a9a;line-height:1.7;">
                <a href="https://addingyou.com" style="color:#6a6a6a;text-decoration:none;font-weight:700;">addingyou.com</a>
                &nbsp;|&nbsp; Automated compliance audit
                &nbsp;|&nbsp; Ref: {review_id}
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
    msg["Subject"] = f"{subject_prefix}Policy audit, {count} issue{'s' if count != 1 else ''} found, Elevate Performance Academy"
    msg["From"] = SENDER_EMAIL
    msg["To"] = REVIEWER_EMAIL

    html_content = build_email_html(findings, review_id, test_mode=test_mode)
    msg.attach(MIMEText(html_content, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()

    mode_label = "TEST MODE, no Drive changes" if test_mode else "live"
    print(f"Review email sent to {REVIEWER_EMAIL} (Review ID: {review_id}, {count} finding(s), {mode_label})")
    return review_id
