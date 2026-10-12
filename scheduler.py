"""Scheduler runner for Daily AI Morning Briefing.

Implements Component 1: Schedule Trigger
Allows running the briefing on a continuous schedule or triggering one-off runs,
designed to cooperate with Windows Task Scheduler or background services.
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
import pytz

from config import Config
from app import BriefingPipeline, setup_logging

logger = logging.getLogger("Scheduler")


def run_scheduled_loop() -> None:
    """
    Run an in-process daemon loop that checks the time and triggers
    at SCHEDULE_TIME (e.g. 08:00) in the configured TIMEZONE (Asia/Kolkata).
    """
    setup_logging()
    tz = pytz.timezone(Config.TIMEZONE)
    target_time_str = Config.SCHEDULE_TIME.strip()  # e.g., "08:00"
    target_hour, target_minute = map(int, target_time_str.split(":"))

    logger.info(f"Daily AI Morning Briefing Scheduler started.")
    logger.info(f"Target schedule: Every day at {target_time_str} {Config.TIMEZONE}")

    last_run_date = None

    while True:
        now = datetime.now(tz)
        today_date = now.date()

        if (
            now.hour == target_hour
            and now.minute == target_minute
            and last_run_date != today_date
        ):
            logger.info(f"Triggering scheduled run at {now.isoformat()}...")
            try:
                pipeline = BriefingPipeline(dry_run=False)
                pipeline.run()
                last_run_date = today_date
                logger.info(f"Scheduled run completed successfully for {today_date}.")
            except Exception as e:
                logger.error(f"Error during scheduled run: {e}", exc_info=True)

        # Sleep 30 seconds before next check
        time.sleep(30)


if __name__ == "__main__":
    run_scheduled_loop()
