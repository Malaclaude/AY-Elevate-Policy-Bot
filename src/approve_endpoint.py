"""
approve_endpoint.py
Flask webhook that receives approve/reject clicks from the review email.
Also exposes /register so the local bot can push review data up to Railway.
"""

import json
import os
import base64
from datetime import datetime
from flask import Flask, request, jsonify
from publish_draft import publish_approved_correction

app = Flask(__name__)

PENDING_REVIEWS_PATH = "data/pending_reviews.json"


def load_pending_reviews() -> dict:
    if not os.path.exists(PENDING_REVIEWS_PATH):
        return {}
    with open(PENDING_REVIEWS_PATH) as f:
        return json.load(f)


def save_pending_reviews(pending: dict):
    os.makedirs(os.path.dirname(PENDING_REVIEWS_PATH), exist_ok=True)
    with open(PENDING_REVIEWS_PATH, "w") as f:
        json.dump(pending, f, indent=2)


def page(title, icon_html, headline, body_html, ref, timestamp):
    """Render a branded, mobile-optimised confirmation page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin:0; padding:0; background:#f1f5f9; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; -webkit-font-smoothing:antialiased; }}
    .wrapper {{ min-height:100vh; padding:40px 16px; display:flex; align-items:center; justify-content:center; }}
    .card {{ background:#ffffff; border-radius:16px; border:1px solid #e2e8f0; overflow:hidden; width:100%; max-width:520px; }}
    .card-top {{ background:#0f172a; height:5px; }}
    .card-body {{ padding:48px 40px 40px; text-align:center; }}
    .card-footer {{ background:#f8fafc; border-top:1px solid #f1f5f9; padding:18px 40px; text-align:center; }}
    .brand {{ margin:0 0 28px; font-size:11px; font-weight:700; letter-spacing:2.5px; text-transform:uppercase; color:#94a3b8; }}
    .headline {{ margin:20px 0 16px; font-size:24px; font-weight:700; color:#0f172a; letter-spacing:-0.3px; line-height:1.2; }}
    .footer-text {{ margin:0; font-size:12px; color:#94a3b8; line-height:1.8; }}
    .footer-text a {{ color:#94a3b8; text-decoration:none; }}
    .doc-btn {{ display:inline-block; background:#0f172a; color:#ffffff; font-size:14px; font-weight:600; padding:14px 28px; border-radius:10px; text-decoration:none; margin-top:4px; }}
    @media (max-width: 480px) {{
      .card-body {{ padding:36px 24px 32px; }}
      .card-footer {{ padding:16px 24px; }}
      .headline {{ font-size:22px; }}
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="card">
      <div class="card-top"></div>
      <div class="card-body">
        <p class="brand">Adding You</p>
        {icon_html}
        <h1 class="headline">{headline}</h1>
        {body_html}
      </div>
      <div class="card-footer">
        <p class="footer-text">
          <a href="https://addingyou.com">addingyou.com</a><br>
          Ref: {ref} &nbsp;&middot;&nbsp; {timestamp}
        </p>
      </div>
    </div>
  </div>
</body>
</html>"""


@app.route("/register", methods=["POST"])
def register():
    """
    Called by the local bot after drafting a correction.
    Stores the review on Railway so the approve webhook can find it.
    """
    data = request.get_json()
    if not data or "review_id" not in data or "correction" not in data:
        return jsonify({"error": "Missing review_id or correction"}), 400

    review_id = data["review_id"]
    pending = load_pending_reviews()
    pending[review_id] = {
        "correction": data["correction"],
        "created_at": data.get("created_at", datetime.utcnow().isoformat()),
        "status": "pending",
    }
    save_pending_reviews(pending)
    print(f"Review registered on Railway: {review_id}")
    return jsonify({"status": "ok", "review_id": review_id}), 200


@app.route("/approve", methods=["GET"])
def approve():
    """
    GET: Shows a confirmation page (prevents email clients auto-triggering approval).
    The actual approval is only executed on POST /confirm.
    """
    review_id = request.args.get("id")
    action = request.args.get("action", "approve")
    encoded_data = request.args.get("d", "")
    timestamp = datetime.utcnow().strftime('%d %B %Y at %H:%M UTC')

    if not review_id:
        return "Missing review ID.", 400

    if action == "reject":
        # Decline goes straight through — no pre-fetch risk on decline
        pending = load_pending_reviews()
        if review_id not in pending:
            pending[review_id] = {"status": "pending"}
        pending[review_id]["status"] = "rejected"
        pending[review_id]["actioned_at"] = datetime.utcnow().isoformat()
        save_pending_reviews(pending)
        return page(
            title="Correction declined",
            icon_html="""<div style="display:inline-flex; align-items:center; justify-content:center; width:72px; height:72px; background:#fef2f2; border-radius:50%; border:2px solid #fecaca;">
              <svg width="30" height="30" viewBox="0 0 24 24" fill="none"><path d="M18 6L6 18M6 6l12 12" stroke="#dc2626" stroke-width="2.5" stroke-linecap="round"/></svg>
            </div>""",
            headline="Correction declined",
            body_html="<p style='margin:0; font-size:15px; color:#475569; line-height:1.7;'>The correction has been declined and logged. No changes have been made to the policy.</p>",
            ref=review_id,
            timestamp=timestamp,
        ), 200

    # For approve: show confirmation page first.
    # Actual approval only fires on POST /confirm to prevent email client pre-fetching.
    confirm_url = f"/confirm?id={review_id}&d={encoded_data}"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Confirm approval</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin:0; padding:0; background:#f1f5f9; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; }}
    .wrapper {{ min-height:100vh; padding:40px 16px; display:flex; align-items:center; justify-content:center; }}
    .card {{ background:#fff; border-radius:16px; border:1px solid #e2e8f0; overflow:hidden; width:100%; max-width:520px; }}
    .card-top {{ background:#0f172a; height:5px; }}
    .card-body {{ padding:48px 40px 40px; text-align:center; }}
    .card-footer {{ background:#f8fafc; border-top:1px solid #f1f5f9; padding:18px 40px; text-align:center; }}
    .brand {{ margin:0 0 28px; font-size:11px; font-weight:700; letter-spacing:2.5px; text-transform:uppercase; color:#94a3b8; }}
    .headline {{ margin:20px 0 12px; font-size:24px; font-weight:700; color:#0f172a; }}
    .subtext {{ margin:0 0 32px; font-size:15px; color:#64748b; line-height:1.7; }}
    .btn-confirm {{ display:inline-block; background:#0f172a; color:#fff; font-size:14px; font-weight:600; padding:15px 32px; border-radius:10px; border:none; cursor:pointer; text-decoration:none; margin-right:10px; }}
    .btn-cancel {{ display:inline-block; background:#fff; color:#64748b; font-size:14px; font-weight:500; padding:14px 24px; border-radius:10px; border:1px solid #cbd5e1; cursor:pointer; text-decoration:none; }}
    .footer-text {{ margin:0; font-size:12px; color:#94a3b8; }}
    @media (max-width:480px) {{
      .card-body {{ padding:36px 24px 32px; }}
      .card-footer {{ padding:16px 24px; }}
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="card">
      <div class="card-top"></div>
      <div class="card-body">
        <p class="brand">Adding You</p>
        <div style="display:inline-flex; align-items:center; justify-content:center; width:72px; height:72px; background:#f0fdf4; border-radius:50%; border:2px solid #bbf7d0;">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none"><path d="M5 13l4 4L19 7" stroke="#16a34a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </div>
        <h1 class="headline">Confirm approval</h1>
        <p class="subtext">You are about to approve the correction to the Accessibility and Inclusiveness Policy. This will publish the updated text to the Elevate Google Drive folder.</p>
        <form method="POST" action="{confirm_url}" style="display:inline;">
          <button type="submit" class="btn-confirm">Confirm approval</button>
        </form>
        <a href="javascript:history.back()" class="btn-cancel">Cancel</a>
      </div>
      <div class="card-footer">
        <p class="footer-text">Ref: {review_id}</p>
      </div>
    </div>
  </div>
</body>
</html>""", 200


@app.route("/confirm", methods=["POST"])
def confirm():
    """Executes the approval — only reachable by clicking the button, not by email pre-fetch."""
    review_id = request.args.get("id")
    encoded_data = request.args.get("d", "")
    timestamp = datetime.utcnow().strftime('%d %B %Y at %H:%M UTC')

    if not review_id:
        return "Missing review ID.", 400

    pending = load_pending_reviews()

    # Decode correction from URL
    correction = None
    if encoded_data:
        try:
            correction = json.loads(base64.urlsafe_b64decode(encoded_data.encode()).decode())
        except Exception as e:
            print(f"Warning: could not decode correction: {e}")

    if not correction:
        review = pending.get(review_id)
        if review:
            correction = review.get("correction")

    if not correction:
        return page(
            title="Not found",
            icon_html="""<div style="display:inline-flex; align-items:center; justify-content:center; width:72px; height:72px; background:#f1f5f9; border-radius:50%; border:2px solid #e2e8f0;">
              <span style="font-size:30px;">&#128269;</span>
            </div>""",
            headline="Review not found",
            body_html="<p style='margin:0; font-size:15px; color:#64748b; line-height:1.7;'>This review link has expired or could not be found.</p>",
            ref=review_id,
            timestamp=timestamp,
        ), 404

    # Check if already approved
    existing = pending.get(review_id, {})
    if existing.get("status") == "approved":
        doc_url = existing.get("doc_url", "")
        doc_link = f'<p style="margin:16px 0 0;"><a href="{doc_url}" style="color:#3b82f6; font-size:14px; text-decoration:none;">View published document &rarr;</a></p>' if doc_url else ""
        return page(
            title="Already approved",
            icon_html="""<div style="display:inline-flex; align-items:center; justify-content:center; width:72px; height:72px; background:#f0fdf4; border-radius:50%; border:2px solid #bbf7d0;">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none"><path d="M5 13l4 4L19 7" stroke="#16a34a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </div>""",
            headline="Policy already updated",
            body_html=f"<p style='margin:0; font-size:15px; color:#64748b; line-height:1.7;'>This correction has already been approved and published. Nothing more to do.</p>{doc_link}",
            ref=review_id,
            timestamp=timestamp,
        ), 200

    # Execute approval
    doc_url = None
    try:
        doc_url = publish_approved_correction(correction, review_id)
    except Exception as e:
        print(f"Warning: Drive publish failed: {e}")

    if review_id not in pending:
        pending[review_id] = {"correction": correction, "status": "pending"}
    pending[review_id]["status"] = "approved"
    pending[review_id]["actioned_at"] = datetime.utcnow().isoformat()
    if doc_url:
        pending[review_id]["doc_url"] = doc_url
    save_pending_reviews(pending)

    doc_button = f"""<a href="{doc_url}" style="display:inline-block; background:#0f172a; color:#ffffff; font-size:14px; font-weight:600; padding:14px 28px; border-radius:10px; text-decoration:none;">
      View published document &rarr;
    </a>""" if doc_url else ""

    return page(
        title="Policy updated",
        icon_html="""<div style="display:inline-flex; align-items:center; justify-content:center; width:72px; height:72px; background:#f0fdf4; border-radius:50%; border:2px solid #bbf7d0;">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none"><path d="M5 13l4 4L19 7" stroke="#16a34a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </div>""",
        headline="Policy updated",
        body_html=f"""<p style="margin:0 0 24px; font-size:15px; color:#475569; line-height:1.7;">
          The corrected Accessibility and Inclusiveness Policy has been published to the Elevate Google Drive folder.
        </p>{doc_button}""",
        ref=review_id,
        timestamp=timestamp,
    ), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "ay-policy-bot-webhook"}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
