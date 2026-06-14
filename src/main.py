"""
main.py
Orchestrates the full demo slice:
1. Read the Accessibility policy from Google Drive
2. Detect the ADA jurisdiction error
3. Draft a correction using Claude API
4. Send a review email to Malachi
5. Wait for approval via the webhook (approve_endpoint.py)
6. Publish the approved correction to Google Drive

Run this script to trigger the bot manually.
The approve_endpoint.py Flask app handles the approval step separately.
"""

import sys
import os

# Add src to path so imports work whether run from root or src/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from read_policy import read_accessibility_policy
from detect_gap import detect_gap
from draft_correction import draft_correction
from send_review import send_review_email


def run():
    print("=" * 60)
    print("AY POLICY BOT — Demo Slice")
    print("Elevate Performance Academy — Accessibility Policy Check")
    print("=" * 60)

    # Step 1: Read the policy
    print("\n[1/4] Reading Accessibility policy from Google Drive...")
    policy_text = read_accessibility_policy()

    # Step 2: Detect the gap
    print("\n[2/4] Scanning for compliance gaps...")
    gap = detect_gap(policy_text)

    if not gap["found"]:
        print("No gaps detected. Nothing to do.")
        return

    print(f"Gap found: {gap['description']}")

    # Step 3: Draft the correction
    print("\n[3/4] Drafting correction via Claude API...")
    correction = draft_correction(gap, policy_text)
    print("Draft complete.")
    print(f"\n  ORIGINAL: {correction['original_excerpt'][:100]}...")
    print(f"\n  CORRECTED: {correction['corrected_excerpt'][:100]}...")

    # Step 4: Send review email
    print("\n[4/4] Sending review email to Malachi...")
    review_id = send_review_email(correction)

    print("\n" + "=" * 60)
    print("DONE — bot has completed its run.")
    print(f"Review ID: {review_id}")
    print("Malachi will receive an email with approve/reject options.")
    print("Once approved, the webhook (approve_endpoint.py) will publish the correction.")
    print("=" * 60)


if __name__ == "__main__":
    run()
