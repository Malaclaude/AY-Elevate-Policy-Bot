"""Verify the review dashboard + inline /apply flow against the local server (test mode)."""
import sys, os, json, urllib.request, urllib.parse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from detect_gap import detect_all_gaps
from send_review import encode_findings

BASE = "http://localhost:5001"
RID = "revtest1"
TEXT = ("such as the Americans with Disabilities Act (ADA) and WCAG. "
        "Our safeguarding policy follows Working Together to Safeguard Children 2018.")


def get(path):
    return urllib.request.urlopen(BASE + path, timeout=10).read().decode()


def post_json(path):
    req = urllib.request.Request(BASE + path, method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=10)
        return r.getcode(), json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


findings = detect_all_gaps(TEXT)
all_enc = urllib.parse.quote(encode_findings(findings))

# 1. dashboard renders with a card per finding
html = get(f"/review?id={RID}&d={all_enc}&test=1")
n_cards = html.count('class="card"')
print(f"/review renders {n_cards} cards (expected {len(findings)}) ->", "PASS" if n_cards == len(findings) else "FAIL")
print("has inline JS approveCard ->", "PASS" if "approveCard" in html and "fetch(" in html else "FAIL")

# 2. apply finding 0 inline
d0 = urllib.parse.quote(encode_findings([findings[0]]))
code, j = post_json(f"/apply?id={RID}&d={d0}&test=1")
print(f"/apply finding 0 -> {j.get('status')}", "PASS" if code == 200 and j["status"] == "approved" else "FAIL")

# 3. apply finding 0 again -> already
code, j = post_json(f"/apply?id={RID}&d={d0}&test=1")
print(f"/apply finding 0 again -> {j.get('status')}", "PASS" if j["status"] == "already" else "FAIL")

# 4. apply finding 1 -> approved (independent)
d1 = urllib.parse.quote(encode_findings([findings[1]]))
code, j = post_json(f"/apply?id={RID}&d={d1}&test=1")
print(f"/apply finding 1 -> {j.get('status')}", "PASS" if j["status"] == "approved" else "FAIL")

# 5. skip finding 2
d2 = urllib.parse.quote(encode_findings([findings[2]]))
code, j = post_json(f"/skip?id={RID}&d={d2}")
print(f"/skip finding 2 -> {j.get('status')}", "PASS" if j["status"] == "skipped" else "FAIL")

pend = json.load(open("data/pending_reviews.json"))
rec = pend.get(RID, {})
print("approved:", rec.get("approved_findings"), "| skipped:", rec.get("skipped_findings"))
