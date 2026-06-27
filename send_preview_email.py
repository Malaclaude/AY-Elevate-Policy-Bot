"""
send_preview_email.py — sends the redesigned review email (TEST MODE) so the
reviewer can see the new premium design in their real inbox. No Drive changes.
Bypasses the Claude drafting step (not needed for the visual).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from detect_gap import detect_all_gaps
from read_policy import read_accessibility_policy
from send_review import send_review_email

# Mirror production exactly: live read, real detection, no fake substitution.
text = read_accessibility_policy()
findings = detect_all_gaps(text)
print(f"{len(findings)} finding(s) detected.")
review_id = send_review_email(findings, test_mode=True)
print(f"Sent. Review ID: {review_id}")
