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
from detect_gap import detect_gap
from draft_correction import draft_correction
from send_review import send_review_email

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run_monthly_check():
    """Full policy check cycle — runs on the 1st of each month."""
    logger.info("Monthly policy check started.")

    try:
        # Step 1: Read policy
        logger.info("Reading Accessibility policy...")
        policy_text = read_accessibility_policy()

        # Step 2: Detect gaps
        logger.info("Scanning for compliance gaps...")
        gap = detect_gap(policy_text)

        if not gap["found"]:
            logger.info("No gaps detected. Check complete.")
            return

        logger.info(f"Gap found: {gap['description']}")

        # Step 3: Draft correction
        logger.info("Drafting correction via Claude API...")
        correction = draft_correction(gap, policy_text)

        # Step 4: Send review email
        logger.info("Sending review email...")
        review_id = send_review_email(correction)

        logger.info(f"Monthly check complete. Review ID: {review_id}")

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
