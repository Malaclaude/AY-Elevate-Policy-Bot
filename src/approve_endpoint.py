"""
approve_endpoint.py
Flask webhook that receives approve/reject clicks from the review email.
Run this on Railway so the approve link in the email has somewhere to land.
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


def confirmation_page(title, headline, body_html, ref, timestamp):
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

          <!-- Top bar -->
          <tr>
            <td style="background:#0f172a; height:5px; font-size:0; line-height:0;">&nbsp;</td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:52px 52px 44px; text-align:center;">

              <p style="margin:0 0 24px; font-size:11px; font-weight:700; letter-spacing:2.5px; text-transform:uppercase; color:#94a3b8;">Adding You</p>

              {body_html}

              <h1 style="margin:16px 0 12px; font-size:26px; font-weight:700; color:#0f172a; letter-spacing:-0.5px; line-height:1.2;">{headline}</h1>

            </td>
          </tr>

          <!-- Footer -->
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


@app.route("/approve", methods=["GET"])
def approve():
    review_id = request.args.get("id")
    action = request.args.get("action", "approve")
    timestamp = datetime.utcnow().strftime('%d %B %Y, %H:%M')

    if not review_id:
        return "Missing review ID.", 400

    pending = load_pending_reviews()

    if review_id not in pending:
        return confirmation_page(
            title="Already actioned",
            headline="Already actioned",
            body_html="""
              <div style="display:inline-flex; align-items:center; justify-content:center; width:64px; height:64px; background:#f1f5f9; border-radius:50%; margin-bottom:4px;">
                <span style="font-size:28px;">&#8987;</span>
              </div>
              <p style="margin:0; font-size:15px; color:#64748b; line-height:1.65;">This review has already been actioned or the ID was not found.</p>
            """,
            ref=review_id,
            timestamp=timestamp,
        ), 200

    review = pending[review_id]

    if review["status"] != "pending":
        already = review["status"].capitalize()
        return confirmation_page(
            title=f"Already {already}",
            headline=f"Already {already}",
            body_html=f"""
              <div style="display:inline-flex; align-items:center; justify-content:center; width:64px; height:64px; background:#f1f5f9; border-radius:50%; margin-bottom:4px;">
                <span style="font-size:28px;">&#8987;</span>
              </div>
              <p style="margin:0; font-size:15px; color:#64748b; line-height:1.65;">This correction was already marked as <strong>{already}</strong>. No further action needed.</p>
            """,
            ref=review_id,
            timestamp=timestamp,
        ), 200

    if action == "approve":
        correction = review["correction"]
        doc_url = publish_approved_correction(correction, review_id)

        pending[review_id]["status"] = "approved"
        pending[review_id]["actioned_at"] = datetime.utcnow().isoformat()
        pending[review_id]["doc_url"] = doc_url
        save_pending_reviews(pending)

        return confirmation_page(
            title="Correction approved",
            headline="Correction approved",
            body_html=f"""
              <div style="display:inline-flex; align-items:center; justify-content:center; width:72px; height:72px; background:#f0fdf4; border-radius:50%; margin-bottom:4px; border:2px solid #bbf7d0;">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M5 13l4 4L19 7" stroke="#16a34a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </div>
              <p style="margin:0 0 20px; font-size:15px; color:#475569; line-height:1.7;">
                The corrected Accessibility and Inclusiveness Policy has been published to the Elevate Google Drive folder. No further action is needed.
              </p>
              <a href="{doc_url}"
                 style="display:inline-block; background:#0f172a; color:#ffffff; font-size:14px; font-weight:600; padding:14px 28px; border-radius:10px; text-decoration:none; margin-bottom:16px;">
                View published document &rarr;
              </a>
              <br>
            """,
            ref=review_id,
            timestamp=timestamp,
        ), 200

    elif action == "reject":
        pending[review_id]["status"] = "rejected"
        pending[review_id]["actioned_at"] = datetime.utcnow().isoformat()
        save_pending_reviews(pending)

        return confirmation_page(
            title="Correction declined",
            headline="Correction declined",
            body_html="""
              <div style="display:inline-flex; align-items:center; justify-content:center; width:72px; height:72px; background:#fef2f2; border-radius:50%; margin-bottom:4px; border:2px solid #fecaca;">
                <svg width="30" height="30" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M18 6L6 18M6 6l12 12" stroke="#dc2626" stroke-width="2.5" stroke-linecap="round"/>
                </svg>
              </div>
              <p style="margin:0 0 8px; font-size:15px; color:#475569; line-height:1.7;">
                The correction has been declined and logged. No changes have been made to the policy. Adding You has been notified.
              </p>
            """,
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
