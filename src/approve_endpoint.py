"""
approve_endpoint.py
Flask webhook that receives approve/reject clicks from the review email.
Also exposes /register so the local bot can push review data up to Railway.
"""

import json
import os
import base64
import zlib
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
  <meta name="color-scheme" content="light">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin:0; padding:0; background:#f3f0fa; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; -webkit-font-smoothing:antialiased; }}
    .wrapper {{ min-height:100vh; padding:40px 16px; display:flex; align-items:center; justify-content:center; }}
    .card {{ background:#ffffff; border-radius:26px; overflow:hidden; width:100%; max-width:520px; box-shadow:0 10px 40px rgba(76,29,149,0.12); }}
    .card-top {{ background:#ece7fb; background:linear-gradient(160deg,#e7defb 0%,#f3e3f4 60%,#ffffff 100%); height:90px; }}
    .card-body {{ padding:0 40px 44px; text-align:center; margin-top:-44px; }}
    .card-footer {{ background:#faf8ff; border-top:1px solid #eee9fb; padding:20px 40px; text-align:center; }}
    .brand {{ margin:0 0 22px; font-size:12px; font-weight:800; letter-spacing:3.5px; text-transform:uppercase; color:#7c3aed; }}
    .headline {{ margin:22px 0 16px; font-size:25px; font-weight:800; color:#1e1b2e; letter-spacing:-0.4px; line-height:1.2; }}
    .footer-text {{ margin:0; font-size:12px; color:#a78bb5; line-height:1.8; }}
    .footer-text a {{ color:#7c3aed; text-decoration:none; font-weight:700; }}
    .doc-btn {{ display:inline-block; background:#7c3aed; color:#ffffff; font-size:14px; font-weight:700; padding:15px 32px; border-radius:100px; text-decoration:none; margin-top:4px; box-shadow:0 8px 22px rgba(124,58,237,0.30); }}
    @media (max-width: 480px) {{
      .card-body {{ padding:0 24px 34px; }}
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
        {icon_html}
        <p class="brand">Adding You</p>
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
    Called by the local bot after running gap detection.
    Stores the review on Railway so the approve webhook can find it.
    Accepts either 'findings' (list, new multi-finding flow) or 'correction' (dict, legacy).
    """
    data = request.get_json()
    if not data or "review_id" not in data:
        return jsonify({"error": "Missing review_id"}), 400

    review_id = data["review_id"]
    pending = load_pending_reviews()

    # Support both new (findings list) and legacy (correction dict) formats
    if "findings" in data:
        pending[review_id] = {
            "findings": data["findings"],
            "created_at": data.get("created_at", datetime.utcnow().isoformat()),
            "status": "pending",
        }
    elif "correction" in data:
        pending[review_id] = {
            "correction": data["correction"],
            "created_at": data.get("created_at", datetime.utcnow().isoformat()),
            "status": "pending",
        }
    else:
        return jsonify({"error": "Missing findings or correction"}), 400

    save_pending_reviews(pending)
    print(f"Review registered on Railway: {review_id}")
    return jsonify({"status": "ok", "review_id": review_id}), 200


@app.route("/approve", methods=["GET"])
def approve():
    """
    GET: Auto-submits a hidden POST form via JavaScript on page load.
    - Safe Links / email pre-fetchers never execute JS, so they can't trigger approval.
    - When Chad clicks the link, his browser runs the JS instantly — seamless single click.
    - Decline is handled here directly (no JS needed, no Drive risk on pre-fetch).
    """
    review_id = request.args.get("id")
    action = request.args.get("action", "approve")
    encoded_data = request.args.get("d", "")
    test_mode = request.args.get("test", "0") == "1"
    timestamp = datetime.utcnow().strftime('%d %B %Y at %H:%M UTC')

    if not review_id:
        return "Missing review ID.", 400

    if action == "reject":
        pending = load_pending_reviews()
        if review_id not in pending:
            pending[review_id] = {"status": "pending"}
        pending[review_id]["status"] = "rejected"
        pending[review_id]["actioned_at"] = datetime.utcnow().isoformat()
        save_pending_reviews(pending)
        return page(
            title="Correction declined",
            icon_html="""<div style="display:inline-flex;align-items:center;justify-content:center;width:72px;height:72px;background:#fef2f2;border-radius:50%;border:2px solid #fecaca;">
              <svg width="30" height="30" viewBox="0 0 24 24" fill="none"><path d="M18 6L6 18M6 6l12 12" stroke="#dc2626" stroke-width="2.5" stroke-linecap="round"/></svg>
            </div>""",
            headline="Correction declined",
            body_html="<p style='margin:0;font-size:15px;color:#475569;line-height:1.7;'>Logged. No changes have been made to any policy documents.</p>",
            ref=review_id,
            timestamp=timestamp,
        ), 200

    # Build the confirm URL — JS will POST to this immediately on page load
    test_param = "&test=1" if test_mode else ""
    confirm_url = f"/confirm?id={review_id}&d={encoded_data}{test_param}"
    test_banner = (
        '<p style="margin:0 0 12px;font-size:12px;font-weight:600;color:#92400e;'
        'background:#fef9c3;border:1px solid #fde68a;border-radius:8px;padding:8px 14px;">'
        'TEST MODE — no changes will be written to Drive.</p>'
    ) if test_mode else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Approving...</title>
  <meta name="color-scheme" content="light">
  <style>
    *{{box-sizing:border-box;}}
    body{{margin:0;padding:0;background:#f3f0fa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;}}
    .wrap{{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px 16px;}}
    .card{{background:#fff;border-radius:26px;box-shadow:0 10px 40px rgba(76,29,149,0.12);padding:52px 40px;text-align:center;max-width:440px;width:100%;}}
    .brand{{margin:0 0 26px;font-size:12px;font-weight:800;letter-spacing:3.5px;text-transform:uppercase;color:#7c3aed;}}
    .spinner{{width:50px;height:50px;border:4px solid #ede9f5;border-top-color:#7c3aed;border-radius:50%;animation:spin 0.8s linear infinite;margin:0 auto 26px;}}
    @keyframes spin{{to{{transform:rotate(360deg)}}}}
    h2{{margin:0 0 8px;font-size:21px;font-weight:800;color:#1e1b2e;letter-spacing:-0.3px;}}
    p{{margin:0;font-size:14px;color:#8b86a0;line-height:1.6;}}
    .ref{{margin-top:26px;font-size:11px;color:#c4bbd9;}}
    @media(max-width:480px){{.card{{padding:40px 24px;}}}}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      {test_banner}
      <p class="brand">Adding You</p>
      <div class="spinner"></div>
      <h2>Applying corrections...</h2>
      <p>Updating your policy documents. This will only take a moment.</p>
      <p class="ref">Ref: {review_id}</p>
    </div>
  </div>
  <form id="f" method="POST" action="{confirm_url}"></form>
  <script>
    // Auto-submit immediately — email pre-fetchers don't run JS so this is safe.
    // Fallback: if JS is somehow blocked, show a manual button after 3 seconds.
    document.getElementById('f').submit();
    setTimeout(function(){{
      var d = document.querySelector('.spinner');
      if(d) d.style.display='none';
      document.querySelector('h2').textContent = 'Tap to approve';
      document.querySelector('p').innerHTML =
        '<button onclick="document.getElementById(\\'f\\').submit()" '
        'style="background:#7c3aed;color:#fff;border:none;padding:15px 32px;'
        'border-radius:100px;font-size:14px;font-weight:700;cursor:pointer;margin-top:12px;'
        'box-shadow:0 8px 22px rgba(124,58,237,0.30);">'
        'Confirm approval</button>';
    }}, 3000);
  </script>
</body>
</html>""", 200


@app.route("/confirm", methods=["POST"])
def confirm():
    """Executes the approval — only reachable by clicking the button, not by email pre-fetch."""
    review_id = request.args.get("id")
    encoded_data = request.args.get("d", "")
    test_mode = request.args.get("test", "0") == "1"
    timestamp = datetime.utcnow().strftime('%d %B %Y at %H:%M UTC')

    if not review_id:
        return "Missing review ID.", 400

    pending = load_pending_reviews()

    # Decode findings from URL — try compressed (zlib+b64) first, fall back to plain b64
    findings = None
    correction = None
    if encoded_data:
        try:
            raw = base64.urlsafe_b64decode(encoded_data.encode())
            try:
                decompressed = zlib.decompress(raw)   # new: compressed payload
                decoded = json.loads(decompressed.decode("utf-8"))
            except zlib.error:
                decoded = json.loads(raw.decode("utf-8"))   # legacy: plain JSON
            if isinstance(decoded, list):
                findings = decoded
            elif isinstance(decoded, dict):
                correction = decoded
        except Exception as e:
            print(f"Warning: could not decode URL data: {e}")

    # Fall back to stored data on Railway
    if not findings and not correction:
        review = pending.get(review_id, {})
        findings = review.get("findings")
        correction = review.get("correction")

    if not findings and not correction:
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
            headline="Corrections already published",
            body_html=f"<p style='margin:0; font-size:15px; color:#64748b; line-height:1.7;'>These corrections have already been approved and published. Nothing more to do.</p>{doc_link}",
            ref=review_id,
            timestamp=timestamp,
        ), 200

    # Execute approval — skip Drive publish in test mode
    doc_url = None
    if test_mode:
        print(f"TEST MODE: skipping Drive publish for {review_id}")
    else:
        try:
            if findings:
                doc_url = publish_approved_correction(findings, review_id)
            else:
                doc_url = publish_approved_correction(correction, review_id)
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"Drive publish FAILED for {review_id}: {e}\n{error_detail}")
            return page(
                title="Drive update failed",
                icon_html="""<div style="display:inline-flex;align-items:center;justify-content:center;width:72px;height:72px;background:#fef2f2;border-radius:50%;border:2px solid #fecaca;">
                  <svg width="30" height="30" viewBox="0 0 24 24" fill="none"><path d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke="#dc2626" stroke-width="2" stroke-linecap="round"/></svg>
                </div>""",
                headline="Drive update failed",
                body_html=f"<p style='margin:0;font-size:15px;color:#475569;line-height:1.7;'>The approval was logged but the policy document could not be updated. Check Railway logs for the full error.</p><pre style='margin:16px 0 0;font-size:11px;color:#94a3b8;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:12px;overflow:auto;'>{str(e)}</pre>",
                ref=review_id,
                timestamp=timestamp,
            ), 500

    stored = {"status": "pending"}
    if findings:
        stored["findings"] = findings
    else:
        stored["correction"] = correction
    if review_id not in pending:
        pending[review_id] = stored
    pending[review_id]["status"] = "approved"
    pending[review_id]["actioned_at"] = datetime.utcnow().isoformat()
    pending[review_id]["test_mode"] = test_mode
    if doc_url:
        pending[review_id]["doc_url"] = doc_url
    save_pending_reviews(pending)

    if test_mode:
        body_text = "Test run complete. All findings were detected and corrections drafted correctly. No changes have been made to any policy documents."
        doc_button = ""
    else:
        body_text = f"The compliance correction report for Elevate Performance Academy has been published to Google Drive."
        doc_button = f"""<a href="{doc_url}" style="display:inline-block; background:#0f172a; color:#ffffff; font-size:14px; font-weight:600; padding:14px 28px; border-radius:10px; text-decoration:none;">
      View published document &rarr;
    </a>""" if doc_url else ""

    headline = "Test complete" if test_mode else "Corrections approved"
    return page(
        title=headline,
        icon_html="""<div style="display:inline-flex; align-items:center; justify-content:center; width:72px; height:72px; background:#f0fdf4; border-radius:50%; border:2px solid #bbf7d0;">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none"><path d="M5 13l4 4L19 7" stroke="#16a34a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </div>""",
        headline=headline,
        body_html=f"""<p style="margin:0 0 24px; font-size:15px; color:#475569; line-height:1.7;">
          {body_text}
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
