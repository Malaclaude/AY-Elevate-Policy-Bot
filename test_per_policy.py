"""
test_per_policy.py — verifies per-policy approval state logic against the local
server in TEST MODE (no Drive writes). Repeatable, touches no client documents.
"""
import sys, os, json, time, urllib.request, urllib.parse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from detect_gap import detect_all_gaps
from send_review import encode_findings

BASE = "http://localhost:5001"
RID = "pptest01"
TEXT = (
    "We adhere to relevant accessibility standards such as the Americans with "
    "Disabilities Act (ADA) and Web Content Accessibility Guidelines (WCAG). "
    "Our safeguarding policy follows Working Together to Safeguard Children 2018."
)


def confirm(findings):
    d = urllib.parse.quote(encode_findings(findings))
    req = urllib.request.Request(f"{BASE}/confirm?id={RID}&d={d}&test=1", method="POST")
    return urllib.request.urlopen(req, timeout=10).read().decode()


def main():
    findings = detect_all_gaps(TEXT)
    print(f"{len(findings)} findings: {[f['gap_id'] for f in findings]}")

    r0 = confirm([findings[0]])
    print("approve finding 0 ->", "PASS" if ("approved" in r0.lower() or "test complete" in r0.lower()) else "FAIL")

    r0b = confirm([findings[0]])
    print("approve finding 0 again ->", "PASS (already approved)" if "already approved" in r0b.lower() else "FAIL")

    r1 = confirm([findings[1]])
    print("approve finding 1 (not blocked by 0) ->", "PASS" if ("approved" in r1.lower() or "test complete" in r1.lower()) and "already" not in r1.lower() else "FAIL")

    time.sleep(0.2)
    pend = json.load(open("data/pending_reviews.json"))
    approved = pend.get(RID, {}).get("approved_findings", [])
    print("approved_findings tracked:", approved)
    expect = {findings[0]["gap_id"], findings[1]["gap_id"]}
    print("per-finding state ->", "PASS" if expect.issubset(set(approved)) else "FAIL")


if __name__ == "__main__":
    main()
