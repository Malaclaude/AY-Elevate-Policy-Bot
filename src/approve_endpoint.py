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
    with open(PENDING_REVIEWS_PATH, "w") as f:
        json.dump(pending, f, indent=2)


@app.route("/approve", methods=["GET"])
def approve():
    review_id = request.args.get("id")
    action = request.args.get("action", "approve")

    if not review_id:
        return "Missing review ID.", 400

    pending = load_pending_reviews()

    if review_id not in pending:
        return f"Review ID '{review_id}' not found or already actioned.", 404

    review = pending[review_id]

    if review["status"] != "pending":
        return f"This review has already been actioned: {review['status']}.", 200

    if action == "approve":
        # Publish the correction
        correction = review["correction"]
        doc_url = publish_approved_correction(correction, review_id)

        # Update the record
        pending[review_id]["status"] = "approved"
        pending[review_id]["actioned_at"] = datetime.utcnow().isoformat()
        pending[review_id]["doc_url"] = doc_url
        save_pending_reviews(pending)

        return f"""
        <html>
        <body style="font-family:Arial,sans-serif; max-width:600px; margin:auto; padding:40px; text-align:center;">
            <h2 style="color:#5cb85c;">✅ Correction approved and published</h2>
            <p>The corrected Accessibility Policy has been written to the Elevate Google Drive folder.</p>
            <p><a href="{doc_url}" style="color:#5cb85c;">View the updated document →</a></p>
            <p style="color:#888; font-size:12px;">Review ID: {review_id} | Approved: {datetime.utcnow().strftime('%d %B %Y %H:%M')} UTC</p>
        </body>
        </html>
        """, 200

    elif action == "reject":
        pending[review_id]["status"] = "rejected"
        pending[review_id]["actioned_at"] = datetime.utcnow().isoformat()
        save_pending_reviews(pending)

        return f"""
        <html>
        <body style="font-family:Arial,sans-serif; max-width:600px; margin:auto; padding:40px; text-align:center;">
            <h2 style="color:#d9534f;">❌ Correction rejected / deferred</h2>
            <p>No changes have been made. This review has been logged as deferred.</p>
            <p style="color:#888; font-size:12px;">Review ID: {review_id} | Rejected: {datetime.utcnow().strftime('%d %B %Y %H:%M')} UTC</p>
        </body>
        </html>
        """, 200

    return "Unknown action.", 400


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "ay-policy-bot-webhook"}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
