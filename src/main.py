"""
main.py
Orchestrates the full policy audit:
1. Read the Accessibility policy
2. Detect ALL compliance gaps across all monitored sources
3. Draft corrections for each finding via Claude API
4. Send one consolidated review email with all findings + source links
5. Await approval via the webhook (approve_endpoint.py)
6. On approval, publish a full correction report to Google Drive

Run this script to trigger the bot manually.
The approve_endpoint.py Flask app handles the approval step separately.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from read_policy import read_accessibility_policy
from detect_gap import detect_all_gaps
from draft_correction import draft_all_corrections
from send_review import send_review_email


def run(test_mode: bool = False, doc_path: str = None):
    mode_label = "TEST MODE — no Drive changes" if test_mode else "LIVE"
    print("=" * 60)
    print(f"AY POLICY BOT — Elevate Performance Academy [{mode_label}]")
    print("Full compliance audit across all monitored sources")
    print("=" * 60)

    # Step 1: Read the policy (default or specified via --doc)
    doc_label = doc_path if doc_path else "default Accessibility policy"
    print(f"\n[1/4] Reading: {doc_label}")
    policy_text = read_accessibility_policy(doc_path)

    # Step 2: Detect all gaps
    print("\n[2/4] Running compliance checks across all sources...")
    findings = detect_all_gaps(policy_text)

    if not findings:
        print("No gaps detected. Nothing to send.")
        return

    high = sum(1 for f in findings if f.get("severity") == "High")
    med = len(findings) - high
    print(f"  {len(findings)} finding(s): {high} High, {med} Medium")
    for f in findings:
        src = f.get("source", {})
        src_name = src.get("name", "") if isinstance(src, dict) else ""
        print(f"  [{f['severity']}] {f['gap_id']} — {f['policy_name']}")
        print(f"         Source: {src_name}")

    # Step 3: Draft corrections
    print("\n[3/4] Drafting corrections via Claude API...")
    enriched = draft_all_corrections(findings, policy_text)
    print(f"  Done — {len(enriched)} correction(s) drafted.")

    # Step 4: Send consolidated review email
    print("\n[4/4] Sending review email...")
    review_id = send_review_email(enriched, test_mode=test_mode)

    print("\n" + "=" * 60)
    print(f"DONE — Review ID: {review_id}")
    print(f"Email sent with {len(enriched)} finding(s), each with source link.")
    if test_mode:
        print("TEST MODE: Approve button works but will NOT write to Drive.")
    else:
        print("Approve in email → confirmation page → Confirm → doc published to Drive.")
    print("=" * 60)


if __name__ == "__main__":
    test_mode = "--test" in sys.argv
    # --doc <path> lets you point at any policy file
    doc_path = None
    if "--doc" in sys.argv:
        idx = sys.argv.index("--doc")
        if idx + 1 < len(sys.argv):
            doc_path = sys.argv[idx + 1]
    run(test_mode=test_mode, doc_path=doc_path)
