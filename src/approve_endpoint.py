"""
approve_endpoint.py
Flask webhook that receives approve/reject clicks from the review email.
Also exposes /register so the local bot can push review data up to Railway.
"""

import json
import os
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
    """Render a branded confirmation page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin:0; padding:0; background:#f1f5f9; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f1f5f9; min-height:100vh; padding:60px 16px;">
    <tr>
      <td align="center" valign="middle">
        <table width="520" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff; border-radius:16px; border:1px solid #e2e8f0; overflow:hidden;">
          <tr>
            <td style="background:#0f172a; height:5px; font-size:0; line-height:0;">&nbsp;</td>
          </tr>
          <tr>
            <td style="padding:52px 52px 44px; text-align:center;">
              <p style="margin:0 0 28px; font-size:11px; font-weight:700; letter-spacing:2.5px; text-transform:uppercase; color:#94a3b8;">Adding You</p>
              {icon_html}
              <h1 style="margin:20px 0 16px; font-size:26px; font-weight:700; color:#0f172a; letter-spacing:-0.5px; line-height:1.2;">{headline}</h1>
              {body_html}
            </td>
          </tr>
          <tr>
            <td style="background:#f8fafc; border-top:1px solid #f1f5f9; padding:18px 52px; text-align:center;">
              <p style="margin:0; font-size:12px; color:#94a3b8; line-height:1.6;">
                <a href="https://addingyou.com" style="color:#94a3b8; text-decoration:none;">addingyou.com</a>
                &nbsp;&middot;&nbsp; Ref: {ref}
                &nbsp;&middot;&nbsp; {timestamp} UTC
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
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
    review_id = request.args.get("id")
    action = request.args.get("action", "approve")
    timestamp = datetime.utcnow().strftime('%d %B %Y, %H:%M')

    if not review_id:
        return "Missing review ID.", 400

    pending = load_pending_reviews()

    if review_id not in pending:
        return page(
            title="Not found",
            icon_html="""<div style="display:inline-flex; align-items:center; justify-content:center; width:72px; height:72px; background:#f1f5f9; border-radius:50%; border:2px solid #e2e8f0;">
              <span style="font-size:30px;">&#128269;</span>
            </div>""",
            headline="Review not found",
            body_html="<p style='margin:0; font-size:15px; color:#64748b; line-height:1.7;'>This review ID was not found. It may have expired or already been processed.</p>",
            ref=review_id,
            timestamp=timestamp,
        ), 404

    review = pending[review_id]

    if review["status"] != "pending":
        status = review["status"]
        if status == "approved":
            doc_url = review.get("doc_url", "")
            doc_link = f'<p style="margin:12px 0 0;"><a href="{doc_url}" style="color:#3b82f6; font-size:14px; text-decoration:none;">View published document &rarr;</a></p>' if doc_url else ""
            return page(
                title="Already complete",
                icon_html="""<div style="display:inline-flex; align-items:center; justify-content:center; width:72px; height:72px; background:#f0fdf4; border-radius:50%; border:2px solid #bbf7d0;">
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="none"><path d="M5 13l4 4L19 7" stroke="#16a34a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                </div>""",
                headline="Policy already updated",
                body_html=f"<p style='margin:0; font-size:15px; color:#64748b; line-height:1.7;'>This correction has already been approved and published to Google Drive. Nothing more to do.</p>{doc_link}",
                ref=review_id,
                timestamp=timestamp,
            ), 200
        else:
            return page(
                title="Already declined",
                icon_html="""<div style="display:inline-flex; align-items:center; justify-content:center; width:72px; height:72px; background:#fef2f2; border-radius:50%; border:2px solid #fecaca;">
                  <svg width="30" height="30" viewBox="0 0 24 24" fill="none"><path d="M18 6L6 18M6 6l12 12" stroke="#dc2626" stroke-width="2.5" stroke-linecap="round"/></svg>
                </div>""",
                headline="Correction already declined",
                body_html="<p style='margin:0; font-size:15px; color:#64748b; line-height:1.7;'>This correction was previously declined and logged. No changes have been made.</p>",
                ref=review_id,
                timestamp=timestamp,
            ), 200

    if action == "approve":
        correction = review["correction"]

        doc_url = None
        try:
            doc_url = publish_approved_correction(correction, review_id)
        except Exception as e:
            print(f"Warning: Drive publish failed: {e}")

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
              The corrected Accessibility and Inclusiveness Policy has been approved and logged. The correction is being applied to the Elevate policy folder.
            </p>{doc_button}""",
            ref=review_id,
            timestamp=timestamp,
        ), 200

    elif action == "reject":
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

    return "Unknown action.", 400


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "ay-policy-bot-webhook"}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
