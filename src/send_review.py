"""
send_review.py
Sends a formatted policy audit email via Gmail API.
Premium, airy layout: gradient hero, circular badges, reassurance block, pill CTAs.
One Approve / Decline pair covers the whole batch. Approve opens in a new tab so
the reviewer's inbox is never disturbed.
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
    zlib at level 9 cuts ~3000-char JSON down to ~900 chars — safe for Safe Links."""
    payload = json.dumps(findings, separators=(",", ":"))
    compressed = zlib.compress(payload.encode("utf-8"), level=9)
    return base64.urlsafe_b64encode(compressed).decode()


# ── Premium card rendering ───────────────────────────────────────────────────

def _badge_palette(severity: str, gap_type: str) -> tuple:
    """(circle_bg, circle_text, accent) for the finding's number badge."""
    if gap_type in ("missing_coverage", "expired_document"):
        return ("#fef3c7", "#b45309", "#f59e0b")  # amber — action item
    if severity == "High":
        return ("#fee2e2", "#dc2626", "#ef4444")   # red
    return ("#fef3c7", "#b45309", "#f59e0b")        # amber


def _severity_pill(severity: str) -> str:
    if severity == "High":
        return (
            '<span style="display:inline-block;background:#fef2f2;color:#b91c1c;'
            'font-size:10px;font-weight:700;letter-spacing:0.8px;text-transform:uppercase;'
            'padding:4px 11px;border-radius:100px;border:1px solid #fecaca;">High</span>'
        )
    return (
        '<span style="display:inline-block;background:#fffbeb;color:#92400e;'
        'font-size:10px;font-weight:700;letter-spacing:0.8px;text-transform:uppercase;'
        'padding:4px 11px;border-radius:100px;border:1px solid #fde68a;">Medium</span>'
    )


def _finding_card(finding: dict, index: int) -> str:
    """One finding as an airy card: numbered circular badge, title, body, change chips."""
    severity = finding["severity"]
    source_name = finding["source"]["name"]
    source_url = finding["source"]["url"]
    policy_name = finding["policy_name"]
    description = finding["description"]
    gap_type = finding.get("gap_type", "")
    circle_bg, circle_text, _accent = _badge_palette(severity, gap_type)

    type_labels = {
        "wrong_reference": "Wrong reference",
        "outdated_reference": "Outdated reference",
        "missing_coverage": "Missing coverage",
        "expired_document": "Expired document",
    }
    type_label = type_labels.get(gap_type, gap_type.replace("_", " ").title())

    action_block = ""
    if gap_type in ("wrong_reference", "outdated_reference"):
        wrong = finding.get("wrong_reference", "")
        correct = finding.get("correct_reference", "")
        if wrong and correct:
            action_block = f"""
              <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-top:18px;">
                <tr>
                  <td width="50%" style="padding-right:7px;" valign="top">
                    <p style="margin:0 0 6px;font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#a78bb5;">Currently</p>
                    <p style="margin:0;font-size:13px;color:#7f1d1d;background:#fdf2f8;border:1px solid #fbcfe8;border-radius:10px;padding:11px 14px;line-height:1.55;">{wrong}</p>
                  </td>
                  <td width="50%" style="padding-left:7px;" valign="top">
                    <p style="margin:0 0 6px;font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#a78bb5;">Corrected to</p>
                    <p style="margin:0;font-size:13px;color:#14532d;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:11px 14px;line-height:1.55;">{correct}</p>
                  </td>
                </tr>
              </table>"""
    elif gap_type in ("missing_coverage", "expired_document"):
        action = finding.get("recommended_action", "")
        if action:
            action_block = f"""
              <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-top:18px;">
                <tr>
                  <td style="background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:13px 16px;">
                    <p style="margin:0 0 4px;font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#92400e;">Action required</p>
                    <p style="margin:0;font-size:13px;color:#78350f;line-height:1.6;">{action}</p>
                  </td>
                </tr>
              </table>"""

    return f"""
          <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom:18px;background:#ffffff;border:1px solid #ede9f5;border-radius:18px;box-shadow:0 1px 3px rgba(76,29,149,0.04);">
            <tr>
              <td style="padding:24px 26px 26px;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%">
                  <tr>
                    <td width="46" valign="top" style="padding-right:16px;">
                      <table cellpadding="0" cellspacing="0" border="0"><tr>
                        <td width="46" height="46" align="center" valign="middle" style="background:{circle_bg};border-radius:50%;font-size:17px;font-weight:800;color:{circle_text};">{index + 1}</td>
                      </tr></table>
                    </td>
                    <td valign="top">
                      <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom:6px;">
                        <tr>
                          <td valign="middle"><p style="margin:0;font-size:10px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:#a78bb5;">{type_label}</p></td>
                          <td align="right" valign="middle" style="white-space:nowrap;padding-left:12px;">{_severity_pill(severity)}</td>
                        </tr>
                      </table>
                      <p style="margin:0 0 8px;font-size:16px;font-weight:700;color:#1e1b2e;letter-spacing:-0.2px;">{policy_name}</p>
                      <p style="margin:0;font-size:14px;color:#5b5670;line-height:1.7;">{description}</p>
                      <p style="margin:12px 0 0;font-size:12px;color:#a78bb5;">Checked against <a href="{source_url}" style="color:#7c3aed;text-decoration:none;font-weight:600;">{source_name} &rarr;</a></p>
                      {action_block}
                    </td>
                  </tr>
                </table>
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
    issue_word = "issue" if count == 1 else "issues"
    high_count = sum(1 for f in findings if f.get("severity") == "High")
    med_count = count - high_count
    finding_cards_html = "".join(_finding_card(f, i) for i, f in enumerate(findings))

    test_banner = (
        '<tr><td style="padding:0 40px 8px;"><table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td style="background:#fef9c3;border:1px solid #fde68a;border-radius:12px;padding:11px 18px;text-align:center;">'
        '<p style="margin:0;font-size:12px;font-weight:700;color:#92400e;">TEST MODE &mdash; buttons are live but nothing will be written to Drive.</p>'
        '</td></tr></table></td></tr>'
    ) if test_mode else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <meta name="color-scheme" content="light">
  <title>Policy audit &mdash; {count} {issue_word} found</title>
</head>
<body style="margin:0;padding:0;background:#f3f0fa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">

  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f0fa;padding:36px 14px 52px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;background:#ffffff;border-radius:26px;overflow:hidden;box-shadow:0 10px 40px rgba(76,29,149,0.10);">

          <!-- Gradient hero -->
          <tr>
            <td bgcolor="#ece7fb" style="background:#ece7fb;background:linear-gradient(160deg,#e7defb 0%,#f3e3f4 48%,#ffffff 100%);padding:48px 40px 40px;text-align:center;">
              <p style="margin:0 0 26px;font-size:12px;font-weight:800;letter-spacing:3.5px;text-transform:uppercase;color:#7c3aed;">Adding You</p>
              <h1 style="margin:0 0 14px;font-size:32px;font-weight:800;color:#1e1b2e;letter-spacing:-0.8px;line-height:1.15;">Your policies,<br>checked &amp; <span style="color:#7c3aed;">current.</span></h1>
              <p style="margin:0 auto 26px;max-width:420px;font-size:15px;color:#5b5670;line-height:1.7;">This month's compliance audit for Elevate Performance Academy found {count} {issue_word} to review. Every fix is linked to its official UK source.</p>
              <a href="{approve_url}" target="_blank"
                 style="display:inline-block;background:#1e1b2e;color:#ffffff;font-size:15px;font-weight:700;padding:16px 38px;border-radius:100px;text-decoration:none;letter-spacing:0.2px;box-shadow:0 6px 18px rgba(30,27,46,0.22);">
                Approve all corrections
              </a>
              <p style="margin:16px 0 0;font-size:13px;color:#8b86a0;">Applied straight to Google Drive &mdash; nothing changes until you tap.</p>
            </td>
          </tr>

          {test_banner}

          <!-- Stats strip -->
          <tr>
            <td style="padding:34px 40px 6px;">
              <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#faf8ff;border:1px solid #eee9fb;border-radius:16px;">
                <tr>
                  <td style="padding:16px 20px;text-align:center;border-right:1px solid #eee9fb;" width="33%">
                    <p style="margin:0 0 3px;font-size:22px;font-weight:800;color:#1e1b2e;">{count}</p>
                    <p style="margin:0;font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#a78bb5;">Findings</p>
                  </td>
                  <td style="padding:16px 20px;text-align:center;border-right:1px solid #eee9fb;" width="33%">
                    <p style="margin:0 0 3px;font-size:22px;font-weight:800;color:#dc2626;">{high_count}</p>
                    <p style="margin:0;font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#a78bb5;">High</p>
                  </td>
                  <td style="padding:16px 20px;text-align:center;" width="33%">
                    <p style="margin:0 0 3px;font-size:22px;font-weight:800;color:#d97706;">{med_count}</p>
                    <p style="margin:0;font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#a78bb5;">Medium</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Section header -->
          <tr>
            <td style="padding:34px 40px 18px;text-align:center;">
              <h2 style="margin:0 0 8px;font-size:23px;font-weight:800;color:#1e1b2e;letter-spacing:-0.4px;">What we found</h2>
              <p style="margin:0;font-size:14px;color:#8b86a0;">Run {date_str} &middot; Elevate Performance Academy</p>
            </td>
          </tr>

          <!-- Findings -->
          <tr>
            <td style="padding:0 40px 8px;">
              {finding_cards_html}
            </td>
          </tr>

          <!-- Reassurance quote -->
          <tr>
            <td style="padding:18px 40px 8px;">
              <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#f6f1ff;border-radius:18px;">
                <tr>
                  <td style="padding:26px 30px;">
                    <p style="margin:0 0 10px;font-size:42px;font-weight:800;color:#c4b5fd;line-height:0.6;font-family:Georgia,serif;">&ldquo;</p>
                    <p style="margin:0;font-size:16px;font-weight:600;color:#3b3357;line-height:1.6;">Not a single document changes until you approve. One tap applies every correction, with a full audit trail logged on each file.</p>
                    <p style="margin:14px 0 0;font-size:12px;font-weight:700;letter-spacing:0.6px;text-transform:uppercase;color:#a78bb5;">AY Policy Bot &middot; Automated compliance</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Final CTA -->
          <tr>
            <td style="padding:30px 40px 40px;text-align:center;">
              <h2 style="margin:0 0 8px;font-size:22px;font-weight:800;color:#1e1b2e;letter-spacing:-0.4px;">Ready when you are</h2>
              <p style="margin:0 0 22px;font-size:14px;color:#8b86a0;line-height:1.6;">Approving opens in a new tab, applies the fixes, and shows you a confirmation. Takes about two seconds.</p>
              <a href="{approve_url}" target="_blank"
                 style="display:inline-block;background:#7c3aed;color:#ffffff;font-size:15px;font-weight:700;padding:17px 44px;border-radius:100px;text-decoration:none;letter-spacing:0.2px;box-shadow:0 8px 22px rgba(124,58,237,0.30);">
                Approve all corrections &rarr;
              </a>
              <p style="margin:18px 0 0;font-size:13px;color:#a78bb5;">
                Not ready? <a href="{decline_url}" target="_blank" style="color:#7c3aed;text-decoration:underline;">Decline and log for review</a>
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#faf8ff;border-top:1px solid #eee9fb;padding:22px 40px;border-radius:0 0 26px 26px;text-align:center;">
              <p style="margin:0;font-size:12px;color:#a78bb5;line-height:1.7;">
                <a href="https://addingyou.com" style="color:#7c3aed;text-decoration:none;font-weight:700;">addingyou.com</a>
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
