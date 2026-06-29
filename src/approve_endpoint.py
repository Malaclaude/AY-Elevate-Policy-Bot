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


# Single-page review dashboard. Placeholders: __RID__ __TEST__ __COUNT__ __TESTNOTE__ __CARDS__
REVIEW_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="color-scheme" content="light dark">
<title>Approve corrections</title>
<style>
  :root{ --bg:#f4f4f5; --card:#ffffff; --ink:#1a1a1a; --soft:#5a5a5a; --muted:#9a9a9a; --line:#e6e6e6; --ok:#16a34a; }
  @media (prefers-color-scheme: dark){
    :root{ --bg:#0f0f10; --card:#1a1a1b; --ink:#f2f2f2; --soft:#bdbdbd; --muted:#8a8a8a; --line:#2c2c2e; }
  }
  *{box-sizing:border-box;}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;}
  .wrap{max-width:620px;margin:0 auto;padding:24px 16px 60px;}
  .head{padding:8px 4px 18px;}
  .brand{margin:0 0 14px;font-size:12px;font-weight:800;letter-spacing:3px;text-transform:uppercase;color:var(--muted);}
  h1{margin:0 0 6px;font-size:26px;font-weight:800;letter-spacing:-0.5px;}
  .sub{margin:0;font-size:14px;color:var(--muted);}
  .testnote{margin:14px 0 0;font-size:12px;font-weight:700;color:var(--soft);background:rgba(120,120,120,0.10);border:1px solid var(--line);border-radius:8px;padding:9px 14px;}
  .card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px 22px 20px;margin:14px 0;}
  .card.done{border-color:rgba(22,163,74,0.45);}
  .card.skipped{opacity:0.55;}
  .chead{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;}
  .idx{font-size:11px;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;color:var(--ink);}
  .sev{font-size:11px;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;color:var(--muted);}
  h3{margin:0 0 6px;font-size:17px;font-weight:700;letter-spacing:-0.2px;}
  .tag{margin:0 0 10px;font-size:11px;font-weight:700;letter-spacing:0.4px;text-transform:uppercase;color:var(--muted);}
  .desc{margin:0;font-size:14px;color:var(--soft);line-height:1.7;}
  .detail{margin-top:14px;}
  .chg{padding:11px 0;border-top:1px solid var(--line);}
  .lbl{display:block;font-size:11px;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;color:var(--muted);margin-bottom:3px;}
  .old{font-size:14px;color:var(--muted);text-decoration:line-through;}
  .new{font-size:14px;color:var(--ink);font-weight:700;}
  .act{font-size:14px;color:var(--soft);line-height:1.6;}
  .opts{margin-top:12px;}
  .opt{display:flex;align-items:flex-start;gap:10px;padding:11px 13px;border:1px solid var(--line);border-radius:10px;margin-bottom:8px;cursor:pointer;font-size:14px;color:var(--ink);}
  .opt input{margin-top:2px;}
  .opt span{line-height:1.5;}
  .src{margin:14px 0 0;font-size:12px;color:var(--muted);}
  .src a{color:var(--soft);}
  .actions{display:flex;align-items:center;gap:16px;margin-top:20px;}
  button.primary{background:var(--ink);color:var(--bg);border:none;padding:12px 26px;border-radius:9px;font-size:14px;font-weight:700;cursor:pointer;}
  button.primary:disabled{opacity:0.55;cursor:default;}
  button.skip{background:none;border:none;color:var(--muted);font-size:14px;font-weight:600;cursor:pointer;}
  .cstatus{font-size:13px;font-weight:700;color:var(--ok);}
  .card.skipped .cstatus{color:var(--muted);}
  .bar{position:sticky;bottom:0;margin-top:18px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 18px;display:flex;justify-content:space-between;align-items:center;}
  .bar span{font-size:13px;color:var(--muted);font-weight:600;}
  button.all{background:var(--ink);color:var(--bg);border:none;padding:11px 22px;border-radius:9px;font-size:13px;font-weight:700;cursor:pointer;}
  .alldone{display:none;text-align:center;background:var(--card);border:1px solid rgba(22,163,74,0.45);border-radius:14px;padding:22px;margin-top:18px;}
  .alldone h2{margin:0 0 4px;font-size:18px;font-weight:800;color:var(--ok);}
  .alldone p{margin:0;font-size:13px;color:var(--muted);}
  .foot{text-align:center;margin-top:26px;font-size:12px;color:var(--muted);}
</style>
</head>
<body>
  <div class="wrap">
    <div class="head">
      <p class="brand">Adding You</p>
      <h1>Approve corrections</h1>
      <p class="sub">__COUNT__ correction(s) for Elevate Performance Academy. Approve the ones you want. Each applies straight away, you stay on this page.</p>
      __TESTNOTE__
    </div>
    __CARDS__
    <div class="bar" id="bar">
      <span id="barcount"></span>
      <button class="all" onclick="approveAll()">Approve all remaining</button>
    </div>
    <div class="alldone" id="alldone">
      <h2>All done</h2>
      <p>Every correction has been actioned. You can close this tab.</p>
    </div>
    <p class="foot">Ref: __RID__</p>
  </div>
<script>
  var RID="__RID__", TEST="__TEST__";
  function url(path,d,extra){ return path+"?id="+RID+"&d="+encodeURIComponent(d)+TEST+(extra||""); }
  function refresh(){
    var pending=document.querySelectorAll('.card:not(.done):not(.skipped)').length;
    var bc=document.getElementById('barcount'); if(bc) bc.textContent=pending+" left to review";
    if(pending===0){ var bar=document.getElementById('bar'); if(bar) bar.style.display='none';
      document.getElementById('alldone').style.display='block'; }
  }
  function finish(card,label){
    card.classList.add('done');
    card.querySelector('.cstatus').textContent=label;
    card.querySelectorAll('.actions button').forEach(function(b){ b.remove(); });
    refresh();
  }
  async function postApply(card,choice){
    var d=card.dataset.d, mode=card.dataset.mode;
    var btn=card.querySelector('.primary'); var old=btn.textContent;
    btn.disabled=true; btn.textContent='Working...';
    try{
      var r=await fetch(url('/apply',d,choice?('&choice='+encodeURIComponent(choice)):''),{method:'POST'});
      var j=await r.json();
      if(r.ok && (j.status==='approved'||j.status==='already')){
        finish(card, mode==='notice'?'Acknowledged':'Applied');
      } else { btn.disabled=false; btn.textContent=old; alert('Could not apply: '+(j.message||'error')); }
    }catch(e){ btn.disabled=false; btn.textContent=old; alert('Network error, try again.'); }
  }
  function applyCard(btn){ postApply(btn.closest('.card')); }
  function applyChoice(btn){
    var card=btn.closest('.card');
    var sel=card.querySelector('input[type=radio]:checked');
    if(!sel){ alert('Please pick one option first.'); return; }
    postApply(card, sel.value);
  }
  function skipCard(btn){
    var card=btn.closest('.card'), d=card.dataset.d;
    card.classList.add('skipped');
    card.querySelector('.cstatus').textContent='Skipped';
    card.querySelectorAll('.actions button').forEach(function(b){ b.remove(); });
    fetch(url('/skip',d),{method:'POST'}).catch(function(){});
    refresh();
  }
  async function approveAll(){
    var cards=[].slice.call(document.querySelectorAll('.card:not(.done):not(.skipped)'))
      .filter(function(c){ return c.dataset.mode!=='clarify'; });
    for(var i=0;i<cards.length;i++){ await postApply(cards[i]); }
  }
  refresh();
</script>
</body>
</html>"""


def load_pending_reviews() -> dict:
    if not os.path.exists(PENDING_REVIEWS_PATH):
        return {}
    with open(PENDING_REVIEWS_PATH) as f:
        return json.load(f)


def save_pending_reviews(pending: dict):
    os.makedirs(os.path.dirname(PENDING_REVIEWS_PATH), exist_ok=True)
    with open(PENDING_REVIEWS_PATH, "w") as f:
        json.dump(pending, f, indent=2)


def _decode_payload(encoded_data: str):
    """Decode the URL payload into (findings_list, correction_dict)."""
    if not encoded_data:
        return None, None
    try:
        raw = base64.urlsafe_b64decode(encoded_data.encode())
        try:
            decoded = json.loads(zlib.decompress(raw).decode("utf-8"))
        except zlib.error:
            decoded = json.loads(raw.decode("utf-8"))
        if isinstance(decoded, list):
            return decoded, None
        if isinstance(decoded, dict):
            return None, decoded
    except Exception as e:
        print(f"Warning: could not decode URL data: {e}")
    return None, None


def _gid(finding: dict) -> str:
    """Stable id for one finding, used to track per-policy approve / skip state."""
    return finding.get("gap_id") or f"{finding.get('policy_name','')}|{finding.get('gap_type','')}"


def _mode(finding: dict) -> str:
    """How the dashboard handles a finding: edit | clarify | notice."""
    if finding.get("mode"):
        return finding["mode"]
    gt = finding.get("gap_type", "")
    if gt == "missing_coverage":
        return "clarify"
    if gt == "expired_document":
        return "notice"
    return "edit"


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
    body {{ margin:0; padding:0; background:#f4f4f5; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; -webkit-font-smoothing:antialiased; }}
    .wrapper {{ min-height:100vh; padding:40px 16px; display:flex; align-items:center; justify-content:center; }}
    .card {{ background:#ffffff; border-radius:22px; overflow:hidden; width:100%; max-width:520px; border:1px solid #e6e6e6; }}
    .card-top {{ background:#f0f0f2; background:linear-gradient(160deg,#eeeef1 0%,#f6f6f8 60%,#ffffff 100%); height:90px; }}
    .card-body {{ padding:0 40px 44px; text-align:center; margin-top:-44px; }}
    .card-footer {{ background:#fafafa; border-top:1px solid #ececec; padding:20px 40px; text-align:center; }}
    .brand {{ margin:0 0 22px; font-size:12px; font-weight:800; letter-spacing:3.5px; text-transform:uppercase; color:#1a1a1a; }}
    .headline {{ margin:22px 0 16px; font-size:25px; font-weight:800; color:#1a1a1a; letter-spacing:-0.4px; line-height:1.2; }}
    .footer-text {{ margin:0; font-size:12px; color:#9a9a9a; line-height:1.8; }}
    .footer-text a {{ color:#1a1a1a; text-decoration:none; font-weight:700; }}
    .doc-btn {{ display:inline-block; background:#1a1a1a; color:#ffffff; font-size:14px; font-weight:700; padding:15px 32px; border-radius:9px; text-decoration:none; margin-top:4px; }}
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
        rec = pending.setdefault(review_id, {"status": "pending"})
        skipped_findings, _corr = _decode_payload(encoded_data)
        skipped_ids = [_gid(f) for f in skipped_findings] if skipped_findings else []
        if skipped_ids:
            sk = set(rec.get("skipped_findings", []))
            sk.update(skipped_ids)
            rec["skipped_findings"] = sorted(sk)
            one = len(skipped_ids) == 1
            headline = "Correction skipped" if one else "Corrections declined"
            body = ("Logged. No change has been made to this policy. The other "
                    "corrections are still waiting for your decision."
                    if one else
                    "Logged. No changes have been made to any policy documents.")
        else:
            rec["status"] = "rejected"
            headline = "Corrections declined"
            body = "Logged. No changes have been made to any policy documents."
        rec["actioned_at"] = datetime.utcnow().isoformat()
        save_pending_reviews(pending)
        return page(
            title=headline,
            icon_html="""<div style="display:inline-flex;align-items:center;justify-content:center;width:72px;height:72px;background:#f3f3f3;border-radius:50%;border:1px solid #e0e0e0;">
              <svg width="30" height="30" viewBox="0 0 24 24" fill="none"><path d="M18 6L6 18M6 6l12 12" stroke="#6a6a6a" stroke-width="2.5" stroke-linecap="round"/></svg>
            </div>""",
            headline=headline,
            body_html=f"<p style='margin:0;font-size:15px;color:#4a4a4a;line-height:1.7;'>{body}</p>",
            ref=review_id,
            timestamp=timestamp,
        ), 200

    # Build the confirm URL — JS will POST to this immediately on page load
    test_param = "&test=1" if test_mode else ""
    confirm_url = f"/confirm?id={review_id}&d={encoded_data}{test_param}"
    test_banner = (
        '<p style="margin:0 0 12px;font-size:12px;font-weight:600;color:#555;'
        'background:#f3f3f3;border:1px solid #dcdcdc;border-radius:8px;padding:8px 14px;">'
        'TEST MODE. No changes will be written to Drive.</p>'
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
    .card{{background:#fff;border-radius:22px;border:1px solid #e6e6e6;padding:52px 40px;text-align:center;max-width:440px;width:100%;}}
    .brand{{margin:0 0 26px;font-size:12px;font-weight:800;letter-spacing:3.5px;text-transform:uppercase;color:#1a1a1a;}}
    .spinner{{width:50px;height:50px;border:4px solid #ededed;border-top-color:#1a1a1a;border-radius:50%;animation:spin 0.8s linear infinite;margin:0 auto 26px;}}
    @keyframes spin{{to{{transform:rotate(360deg)}}}}
    h2{{margin:0 0 8px;font-size:21px;font-weight:800;color:#1a1a1a;letter-spacing:-0.3px;}}
    p{{margin:0;font-size:14px;color:#7a7a7a;line-height:1.6;}}
    .ref{{margin-top:26px;font-size:11px;color:#bdbdbd;}}
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
  <form id="f" method="POST" action="{confirm_url}">
    <noscript>
      <button type="submit" style="background:#1a1a1a;color:#fff;border:none;padding:15px 34px;border-radius:9px;font-size:14px;font-weight:700;cursor:pointer;margin-top:8px;">Approve</button>
    </noscript>
  </form>
  <script>
    // Auto-submit immediately. Email pre-fetchers do not run JS, so this is safe.
    // If JS is disabled, the noscript button above is the fallback (no delayed prompt).
    document.getElementById('f').submit();
  </script>
</body>
</html>""", 200


def _encode_findings(findings) -> str:
    payload = json.dumps(findings, separators=(",", ":"))
    compressed = zlib.compress(payload.encode("utf-8"), level=9)
    return base64.urlsafe_b64encode(compressed).decode()


def _h(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _findings_from_request(review_id, encoded_data):
    findings, correction = _decode_payload(encoded_data)
    if not findings and not correction:
        review = load_pending_reviews().get(review_id, {})
        findings = review.get("findings")
        correction = review.get("correction")
    if correction and not findings:
        findings = [correction]
    return findings


def _apply_review(review_id, findings, test_mode):
    """Core per-finding apply, idempotent. Returns dict: status/message/doc_url/applied."""
    if not findings:
        return {"status": "none", "message": "No findings to apply.", "applied": []}
    pending = load_pending_reviews()
    rec = pending.setdefault(review_id, {"status": "pending"})
    approved_ids = set(rec.get("approved_findings", []))
    to_apply = [f for f in findings if _gid(f) not in approved_ids]
    if not to_apply:
        return {"status": "already", "message": "Already approved.",
                "doc_url": rec.get("doc_url"), "applied": []}
    doc_url = rec.get("doc_url")
    if test_mode:
        print(f"TEST MODE: skipping Drive publish for {review_id}")
    else:
        try:
            url = publish_approved_correction(to_apply, review_id)
            if url:
                doc_url = url
        except Exception as e:
            import traceback
            print(f"Drive publish FAILED for {review_id}: {e}\n{traceback.format_exc()}")
            return {"status": "failed", "message": str(e), "applied": []}
    approved_ids.update(_gid(f) for f in to_apply)
    rec["approved_findings"] = sorted(approved_ids)
    rec["findings"] = rec.get("findings") or findings
    rec["actioned_at"] = datetime.utcnow().isoformat()
    rec["test_mode"] = test_mode
    if doc_url:
        rec["doc_url"] = doc_url
    all_ids = {_gid(f) for f in rec.get("findings", findings)}
    if all_ids and all_ids.issubset(approved_ids | set(rec.get("skipped_findings", []))):
        rec["status"] = "approved"
    save_pending_reviews(pending)
    return {"status": "approved", "message": "Applied.", "doc_url": doc_url,
            "applied": [f.get("policy_name", "this policy") for f in to_apply]}


# ── Review dashboard (single page, per-policy, applies inline via fetch) ──────

def _review_card(index, finding, test_mode, state) -> str:
    gap_type = finding.get("gap_type", "")
    mode = _mode(finding)
    type_labels = {
        "wrong_reference": "Wrong reference", "outdated_reference": "Outdated reference",
        "missing_coverage": "Missing coverage", "expired_document": "Out of date",
    }
    type_label = type_labels.get(gap_type, gap_type.replace("_", " ").title())
    sev = "High priority" if finding.get("severity") == "High" else "Medium priority"

    tag = {"edit": "Approve to rewrite the policy text",
           "clarify": "Needs your answer before it can be applied",
           "notice": "For your awareness, no document is changed"}[mode]

    # Detail + actions vary by mode
    if mode == "edit":
        wrong = finding.get("wrong_reference", ""); correct = finding.get("correct_reference", "")
        detail = (f'<div class="chg"><span class="lbl">Currently in the document</span>'
                  f'<span class="old">{_h(wrong)}</span></div>'
                  f'<div class="chg"><span class="lbl">Will be corrected to</span>'
                  f'<span class="new">{_h(correct)}</span></div>') if wrong and correct else ""
        actions = ('<button class="primary" onclick="applyCard(this)">Approve and rewrite</button>'
                   '<button class="skip" onclick="skipCard(this)">Skip</button>')
    elif mode == "clarify":
        q = finding.get("clarify_question", "Please choose how to handle this.")
        opts = finding.get("clarify_options", [])
        radios = "".join(
            f'<label class="opt"><input type="radio" name="opt{index}" value="{_h(o.get("id",""))}">'
            f'<span>{_h(o.get("label",""))}</span></label>'
            for o in opts
        )
        detail = (f'<div class="chg"><span class="lbl">We need to know</span>'
                  f'<span class="act">{_h(q)}</span></div><div class="opts">{radios}</div>')
        actions = ('<button class="primary" onclick="applyChoice(this)">Apply my answer</button>'
                   '<button class="skip" onclick="skipCard(this)">Skip</button>')
    else:  # notice
        action = finding.get("recommended_action", "") or finding.get("description", "")
        detail = (f'<div class="chg"><span class="lbl">What to do</span>'
                  f'<span class="act">{_h(action)}</span></div>')
        actions = '<button class="primary" onclick="applyCard(this)">Mark as seen</button>'

    src = finding.get("source", {}) or {}
    src_html = (f'<p class="src">Checked against <a href="{_h(src.get("url",""))}" target="_blank" '
                f'rel="noopener">{_h(src.get("name",""))}</a></p>') if src.get("name") else ""

    d1 = _encode_findings([finding])
    if state == "approved":
        cls, status_txt = "card done", ("Applied" if mode != "notice" else "Acknowledged")
        actions = ""
    elif state == "skipped":
        cls, status_txt = "card skipped", "Skipped"
        actions = ""
    else:
        cls, status_txt = "card", ""

    return f"""
      <div class="{cls}" data-d="{d1}" data-mode="{mode}">
        <div class="chead">
          <span class="idx">{index + 1}. {type_label}</span>
          <span class="sev">{sev}</span>
        </div>
        <h3>{_h(finding.get('policy_name',''))}</h3>
        <p class="tag">{tag}</p>
        <p class="desc">{_h(finding.get('description',''))}</p>
        <div class="detail">{detail}</div>
        {src_html}
        <div class="actions">{actions}<span class="cstatus">{status_txt}</span></div>
      </div>"""


def _review_page(review_id, findings, test_mode) -> str:
    rec = load_pending_reviews().get(review_id, {})
    approved = set(rec.get("approved_findings", []))
    skipped = set(rec.get("skipped_findings", []))
    cards = "".join(
        _review_card(i, f, test_mode,
                     "approved" if _gid(f) in approved else ("skipped" if _gid(f) in skipped else "pending"))
        for i, f in enumerate(findings)
    )
    test_param = "&test=1" if test_mode else ""
    test_note = ('<p class="testnote">Test mode. Buttons work but nothing is written to Drive.</p>'
                 if test_mode else "")
    count = len(findings)
    return (REVIEW_TEMPLATE
            .replace("__RID__", _h(review_id))
            .replace("__TEST__", test_param)
            .replace("__COUNT__", str(count))
            .replace("__TESTNOTE__", test_note)
            .replace("__CARDS__", cards))


@app.route("/review", methods=["GET"])
def review():
    review_id = request.args.get("id")
    encoded_data = request.args.get("d", "")
    test_mode = request.args.get("test", "0") == "1"
    timestamp = datetime.utcnow().strftime('%d %B %Y at %H:%M UTC')
    if not review_id:
        return "Missing review ID.", 400
    findings = _findings_from_request(review_id, encoded_data)
    if not findings:
        return page(
            title="Not found",
            icon_html='<div style="display:inline-flex;align-items:center;justify-content:center;width:72px;height:72px;background:#f3f3f3;border-radius:50%;border:1px solid #e0e0e0;"><span style="font-size:30px;">&#128269;</span></div>',
            headline="Review not found",
            body_html="<p style='margin:0;font-size:15px;color:#4a4a4a;line-height:1.7;'>This review link has expired or could not be found.</p>",
            ref=review_id, timestamp=timestamp,
        ), 404
    return _review_page(review_id, findings, test_mode), 200


@app.route("/apply", methods=["POST"])
def apply_ajax():
    """JSON endpoint used by the dashboard. Applies finding(s) without navigation."""
    review_id = request.args.get("id")
    encoded_data = request.args.get("d", "")
    test_mode = request.args.get("test", "0") == "1"
    if not review_id:
        return jsonify({"status": "error", "message": "Missing review ID."}), 400
    findings = _findings_from_request(review_id, encoded_data)
    if not findings:
        return jsonify({"status": "error", "message": "Review not found."}), 404

    # Chad's multiple-choice answer for a "clarify" finding decides what gets written.
    choice = request.args.get("choice")
    if choice:
        for f in findings:
            if _mode(f) == "clarify":
                for opt in f.get("clarify_options", []):
                    if opt.get("id") == choice:
                        f["_insert_text"] = opt.get("insert")
                        break

    result = _apply_review(review_id, findings, test_mode)
    return jsonify(result), (500 if result["status"] == "failed" else 200)


@app.route("/skip", methods=["POST"])
def skip_ajax():
    """JSON endpoint: log a per-finding skip from the dashboard."""
    review_id = request.args.get("id")
    encoded_data = request.args.get("d", "")
    if not review_id:
        return jsonify({"status": "error"}), 400
    findings = _findings_from_request(review_id, encoded_data) or []
    pending = load_pending_reviews()
    rec = pending.setdefault(review_id, {"status": "pending"})
    sk = set(rec.get("skipped_findings", []))
    sk.update(_gid(f) for f in findings)
    rec["skipped_findings"] = sorted(sk)
    rec["actioned_at"] = datetime.utcnow().isoformat()
    save_pending_reviews(pending)
    return jsonify({"status": "skipped"}), 200


@app.route("/confirm", methods=["POST"])
def confirm():
    """HTML confirm used by the email's noscript fallback and legacy approve-all links."""
    review_id = request.args.get("id")
    encoded_data = request.args.get("d", "")
    test_mode = request.args.get("test", "0") == "1"
    timestamp = datetime.utcnow().strftime('%d %B %Y at %H:%M UTC')
    if not review_id:
        return "Missing review ID.", 400

    findings = _findings_from_request(review_id, encoded_data)
    SUCCESS_ICON = """<div style="display:inline-flex; align-items:center; justify-content:center; width:72px; height:72px; background:#ecfdf3; border-radius:50%; border:1px solid #bbf7d0;">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none"><path d="M5 13l4 4L19 7" stroke="#16a34a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
    </div>"""
    if not findings:
        return page(
            title="Not found",
            icon_html='<div style="display:inline-flex;align-items:center;justify-content:center;width:72px;height:72px;background:#f3f3f3;border-radius:50%;border:1px solid #e0e0e0;"><span style="font-size:30px;">&#128269;</span></div>',
            headline="Review not found",
            body_html="<p style='margin:0;font-size:15px;color:#4a4a4a;line-height:1.7;'>This review link has expired or could not be found.</p>",
            ref=review_id, timestamp=timestamp,
        ), 404

    result = _apply_review(review_id, findings, test_mode)

    if result["status"] == "failed":
        return page(
            title="Drive update failed",
            icon_html='<div style="display:inline-flex;align-items:center;justify-content:center;width:72px;height:72px;background:#fef2f2;border-radius:50%;border:1px solid #fecaca;"><svg width="30" height="30" viewBox="0 0 24 24" fill="none"><path d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke="#dc2626" stroke-width="2" stroke-linecap="round"/></svg></div>',
            headline="Drive update failed",
            body_html=f"<p style='margin:0;font-size:15px;color:#4a4a4a;line-height:1.7;'>The approval was logged but the policy document could not be updated.</p><pre style='margin:16px 0 0;font-size:11px;color:#8a8a8a;background:#fafafa;border:1px solid #ececec;border-radius:8px;padding:12px;overflow:auto;'>{_h(result['message'])}</pre>",
            ref=review_id, timestamp=timestamp,
        ), 500

    doc_url = result.get("doc_url") or ""
    doc_button = f'<a href="{doc_url}" class="doc-btn">View document</a>' if doc_url else ""
    if result["status"] == "already":
        body_text = "This correction has already been approved and applied. Nothing more to do here."
        headline = "Already approved"
    elif test_mode:
        n = len(result["applied"])
        headline = "Test complete"
        body_text = f"Test run complete. {n} correction{'s' if n != 1 else ''} validated. No changes have been made to any policy documents."
        doc_button = ""
    else:
        n = len(result["applied"])
        headline = "Correction approved" if n == 1 else "Corrections approved"
        body_text = (f"The correction to {result['applied'][0]} has been applied in Google Drive."
                     if n == 1 else
                     f"{n} corrections have been applied to Elevate's policy documents in Google Drive.")

    return page(
        title=headline, icon_html=SUCCESS_ICON, headline=headline,
        body_html=f'<p style="margin:0 0 24px; font-size:15px; color:#4a4a4a; line-height:1.7;">{body_text}</p>{doc_button}',
        ref=review_id, timestamp=timestamp,
    ), 200


@app.route("/calendar", methods=["GET"])
def calendar():
    """Read-only compliance expiry calendar (the always-on compliance diary)."""
    try:
        from expiry_tracker import load_tracker, evaluate, render_calendar_html
        tracker = load_tracker()
        ev = evaluate(tracker)
        return render_calendar_html(
            ev, client=tracker.get("client", ""),
            window=tracker.get("renewal_window_days", 60), as_page=True
        ), 200
    except Exception as e:
        return f"Compliance calendar unavailable: {e}", 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "ay-policy-bot-webhook"}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
