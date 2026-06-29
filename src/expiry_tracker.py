"""
expiry_tracker.py
Compliance expiry calendar. Tracks dated documents (insurance, DBS, first aid,
Ofsted registration, etc.), and flags anything expired or due within a renewal
window (default 60 days). Seeded from compliance_tracker.json.

This is the always-on "compliance diary" layer that sits beside the wording audit:
the policy bot caught a lapsed insurance certificate, this makes sure nothing
dated ever lapses silently again.
"""

import os
import json
from datetime import date, datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKER_PATH = os.path.join(REPO_ROOT, "compliance_tracker.json")
DEFAULT_WINDOW = 60


def _today() -> date:
    return date.today()


def load_tracker(path: str = TRACKER_PATH) -> dict:
    with open(path) as f:
        return json.load(f)


def _parse(d):
    return datetime.strptime(d, "%Y-%m-%d").date() if d else None


def evaluate(tracker: dict, today: date = None) -> list:
    """Annotate each item with _status (expired|due_soon|ok|undated) and _days."""
    today = today or _today()
    window = tracker.get("renewal_window_days", DEFAULT_WINDOW)
    out = []
    for it in tracker.get("items", []):
        exp = _parse(it.get("expires"))
        w = it.get("renewal_window_days", window)
        if exp is None:
            status, days = "undated", None
        else:
            days = (exp - today).days
            status = "expired" if days < 0 else ("due_soon" if days <= w else "ok")
        out.append({**it, "_status": status, "_days": days, "_window": w})
    # Order: expired, due_soon, undated, ok; soonest first within dated groups
    rank = {"expired": 0, "due_soon": 1, "undated": 2, "ok": 3}
    return sorted(out, key=lambda e: (rank[e["_status"]], e["_days"] if e["_days"] is not None else 9999))


def alerts(evaluated: list) -> list:
    """Items that need attention now: expired or inside the renewal window."""
    return [e for e in evaluated if e["_status"] in ("expired", "due_soon")]


# ── Rendering (monochrome, works as a web page and inside an email) ──────────

_PALETTE = {
    "expired":  ("#b91c1c", "Expired"),
    "due_soon": ("#b45309", "Due soon"),
    "undated":  ("#6a6a6a", "No date on file"),
    "ok":       ("#16a34a", "In date"),
}


def _row(e: dict) -> str:
    colour, label = _PALETTE[e["_status"]]
    if e["_status"] == "expired":
        when = f"Expired {abs(e['_days'])} days ago"
    elif e["_status"] == "due_soon":
        when = f"Renews in {e['_days']} days"
    elif e["_status"] == "ok":
        when = f"In date, {e['_days']} days left"
    else:
        when = "Add a renewal date"
    exp_txt = e.get("expires") or "not set"
    ref = e.get("reference", "")
    return f"""
      <tr>
        <td style="padding:14px 12px;border-bottom:1px solid #ececec;vertical-align:top;">
          <div style="font-size:14px;font-weight:700;color:#1a1a1a;">{e.get('name','')}</div>
          <div style="font-size:12px;color:#8a8a8a;margin-top:2px;">{e.get('category','')} &middot; {ref}</div>
        </td>
        <td style="padding:14px 12px;border-bottom:1px solid #ececec;vertical-align:top;white-space:nowrap;font-size:13px;color:#5a5a5a;">{exp_txt}</td>
        <td style="padding:14px 12px;border-bottom:1px solid #ececec;vertical-align:top;white-space:nowrap;">
          <span style="font-size:11px;font-weight:700;letter-spacing:0.4px;text-transform:uppercase;color:{colour};">{label}</span>
          <div style="font-size:12px;color:#8a8a8a;margin-top:2px;">{when}</div>
        </td>
      </tr>"""


def render_calendar_html(evaluated: list, client: str = "Elevate Performance Academy",
                         window: int = DEFAULT_WINDOW, as_page: bool = True) -> str:
    flagged = [e for e in evaluated if e["_status"] in ("expired", "due_soon")]
    rows = "".join(_row(e) for e in evaluated)
    headline = (f"{len(flagged)} item(s) need attention" if flagged
                else "Everything tracked is in date")
    inner = f"""
      <table width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:640px;margin:0 auto;background:#fff;border:1px solid #e6e6e6;border-radius:18px;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
        <tr><td style="padding:30px 28px 8px;">
          <p style="margin:0 0 6px;font-size:12px;font-weight:800;letter-spacing:3px;text-transform:uppercase;color:#8a8a8a;">Adding You &middot; Compliance Calendar</p>
          <h1 style="margin:0 0 4px;font-size:24px;font-weight:800;color:#1a1a1a;letter-spacing:-0.4px;">{headline}</h1>
          <p style="margin:0;font-size:13px;color:#8a8a8a;">{client} &middot; alerting {window} days before any renewal</p>
        </td></tr>
        <tr><td style="padding:18px 28px 28px;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <th align="left" style="font-size:11px;text-transform:uppercase;letter-spacing:0.5px;color:#a0a0a0;padding:0 12px 8px;">Document</th>
              <th align="left" style="font-size:11px;text-transform:uppercase;letter-spacing:0.5px;color:#a0a0a0;padding:0 12px 8px;">Expires</th>
              <th align="left" style="font-size:11px;text-transform:uppercase;letter-spacing:0.5px;color:#a0a0a0;padding:0 12px 8px;">Status</th>
            </tr>
            {rows}
          </table>
        </td></tr>
      </table>"""
    if not as_page:
        return inner
    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="color-scheme" content="light"><title>Compliance calendar</title></head>
<body style="margin:0;background:#f4f4f5;padding:34px 14px;">{inner}</body></html>"""


# ── Alert email ──────────────────────────────────────────────────────────────

def build_alert_email_html(evaluated: list, client: str, window: int) -> str:
    return render_calendar_html(evaluated, client=client, window=window, as_page=True)


def send_expiry_alert(test_mode: bool = False) -> int:
    """Email the compliance calendar to the reviewers if anything is expired or
    due within the window (or always, in test mode). Returns count of flagged items."""
    import base64
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from send_review import get_gmail_service, SENDER_EMAIL, REVIEWER_EMAIL

    tracker = load_tracker()
    evaluated = evaluate(tracker)
    flagged = alerts(evaluated)

    if not flagged and not test_mode:
        print("Compliance calendar: nothing expired or due. No alert sent.")
        return 0

    client = tracker.get("client", "")
    window = tracker.get("renewal_window_days", DEFAULT_WINDOW)
    html = build_alert_email_html(evaluated, client, window)

    subject_prefix = "[TEST] " if test_mode else ""
    n = len(flagged)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{subject_prefix}Compliance calendar, {n} item(s) need attention, {client}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = REVIEWER_EMAIL
    msg.attach(MIMEText(html, "html"))

    service = get_gmail_service()
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    print(f"Compliance alert sent to {REVIEWER_EMAIL} ({n} flagged, {'test' if test_mode else 'live'}).")
    return n


def check_and_alert():
    """Scheduler entry point: send an alert only if something needs attention."""
    return send_expiry_alert(test_mode=False)


if __name__ == "__main__":
    import sys
    for e in evaluate(load_tracker()):
        print(f"  [{e['_status']:9}] {e.get('name')} (expires {e.get('expires')})")
    if "--send" in sys.argv:
        send_expiry_alert(test_mode="--test" in sys.argv)
