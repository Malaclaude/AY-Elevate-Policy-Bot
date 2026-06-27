"""
send_live_test.py — LIVE-mode review email for the pre-push click test.
Approve links point at whatever APPROVE_BASE_URL env is set to (the local server).
Approving WILL apply the real corrections to Elevate's live docs.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from detect_gap import detect_all_gaps
from send_review import send_review_email

FALLBACK_TEXT = (
    "We adhere to relevant accessibility standards such as the Americans with "
    "Disabilities Act (ADA) and Web Content Accessibility Guidelines (WCAG). "
    "Our safeguarding policy follows Working Together to Safeguard Children 2018."
)
try:
    from read_policy import read_accessibility_policy
    text = read_accessibility_policy()
    if not text or "americans with disabilities" not in text.lower():
        text = FALLBACK_TEXT
except Exception as e:
    print(f"(using fallback policy text: {e})")
    text = FALLBACK_TEXT

findings = detect_all_gaps(text)
print(f"{len(findings)} finding(s) detected.")
review_id = send_review_email(findings, test_mode=False)   # LIVE
print(f"Sent LIVE. Review ID: {review_id}")
