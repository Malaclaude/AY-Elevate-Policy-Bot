"""
scheduler.py
Runs the policy bot automatically on the 1st of every month at 9am UTC.
Also keeps the Flask approval webhook running at all times.
This is the main entry point for Railway deployment.
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from approve_endpoint import app
from read_policy import read_accessibility_policy
from detect_gap import detect_all_gaps
from draft_correction import draft_all_corrections
from send_review import send_review_email

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run_monthly_check():
    """Full policy check cycle — runs on the 1st of each month."""
    logger.info("Monthly policy check started.")

    try:
        # Step 1: Read policy corpus
        logger.info("Reading policy corpus...")
        policy_text = read_accessibility_policy()

        # Step 2: Detect all gaps across all monitored sources
        logger.info("Scanning for compliance gaps...")
        findings = detect_all_gaps(policy_text)

        if not findings:
            logger.info("No gaps detected. Check complete.")
            return

        high = sum(1 for f in findings if f.get("severity") == "High")
        logger.info(f"{len(findings)} finding(s) detected ({high} High). Drafting corrections...")

        # Step 3: Draft corrections for all findings
        enriched = draft_all_corrections(findings, policy_text)

        # Step 4: Send consolidated review email with all findings + source links
        logger.info("Sending review email...")
        review_id = send_review_email(enriched)

        logger.info(f"Monthly check complete. Review ID: {review_id}. {len(enriched)} finding(s) sent.")

    except Exception as e:
        logger.error(f"Monthly check failed: {e}")


def start_scheduler():
    """Start the APScheduler cron job — 1st of every month at 9am UTC."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=run_monthly_check,
        trigger=CronTrigger(day=1, hour=9, minute=0),
        id="monthly_policy_check",
        name="Monthly Elevate Policy Check",
        replace_existing=True,
    )
    scheduler.start()

    next_run = scheduler.get_job("monthly_policy_check").next_run_time
    logger.info(f"Scheduler started. Next run: {next_run.strftime('%d %B %Y at %H:%M UTC')}")
    return scheduler


if __name__ == "__main__":
    import os

    # Start the monthly scheduler in the background
    scheduler = start_scheduler()

    # Start the Flask webhook on the main thread
    port = int(os.getenv("PORT", 5001))
    logger.info(f"Starting approval webhook on port {port}...")
    app.run(host="0.0.0.0", port=port)
