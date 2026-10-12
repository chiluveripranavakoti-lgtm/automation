"""Main orchestrator application for Daily AI Morning Briefing.

Executes the workflow pipeline components in exact required order:
Schedule Trigger -> RSS Read -> Limit -> Aggregate -> Basic LLM Chain -> Send a message
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
import pytz

from config import Config
from database import Database
from rss_reader import RSSReader
from article_filter import ArticleFilter
from deduplicator import ArticleDeduplicator
from aggregator import ArticleAggregator
from gemini_model import GeminiChatModel
from llm_chain import BasicLLMChain, BriefingReport
from email_sender import GmailSender


def setup_logging(verbose: bool = False) -> None:
    """Configure structured logging to console and rotating log file."""
    Config.resolve_paths()
    log_level = logging.DEBUG if verbose else logging.INFO
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    log_file = Config.LOGS_DIR / f"briefing_{datetime.now().strftime('%Y-%m')}.log"
    try:
        handlers.append(logging.FileHandler(str(log_file), encoding="utf-8"))
    except Exception:
        pass

    logging.basicConfig(level=log_level, format=log_format, handlers=handlers, force=True)


class BriefingPipeline:
    """Orchestrates the entire Daily AI Morning Briefing pipeline."""

    def __init__(self, dry_run: bool = False, interactive_auth: bool = False):
        self.dry_run = dry_run
        self.interactive_auth = interactive_auth
        self.logger = logging.getLogger("BriefingPipeline")

        Config.resolve_paths()
        self.db = Database(Config.DATABASE_PATH)
        self.rss_reader = RSSReader.from_config(Config.CUSTOM_FEEDS_FILE)
        self.article_filter = ArticleFilter(
            lookback_hours=Config.LOOKBACK_HOURS,
            max_candidates=Config.MAX_CANDIDATES,
        )
        self.deduplicator = ArticleDeduplicator(self.db)
        self.aggregator = ArticleAggregator(top_candidates_limit=Config.MAX_CANDIDATES)

        self.gemini_model = GeminiChatModel(
            api_key=Config.GEMINI_API_KEY,
            model_name=Config.GEMINI_MODEL,
            temperature=Config.GEMINI_TEMPERATURE,
            timeout=Config.GEMINI_TIMEOUT_SECONDS,
            max_retries=Config.GEMINI_MAX_RETRIES,
        )
        self.llm_chain = BasicLLMChain(self.gemini_model)

        self.email_sender = GmailSender(
            credentials_file=Config.GMAIL_CREDENTIALS_FILE,
            token_file=Config.GMAIL_TOKEN_FILE,
            recipient_email=Config.RECIPIENT_EMAIL,
        )

    def run(self) -> BriefingReport:
        """Execute the end-to-end briefing pipeline."""
        tz = pytz.timezone(Config.TIMEZONE)
        now_local = datetime.now(tz)
        today_date_str = now_local.strftime("%A, %B %d, %Y")

        self.logger.info("==========================================================")
        self.logger.info(f"Starting Daily AI Morning Briefing Pipeline [{today_date_str}]")
        self.logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE PRODUCTION'}")
        self.logger.info("==========================================================")

        # ----------------------------------------------------------------------
        # Component 2: RSS Read
        # ----------------------------------------------------------------------
        self.logger.info("Step 1/5: [RSS Read] Fetching articles across feeds...")
        raw_articles = self.rss_reader.fetch_all()
        fetched_count = len(raw_articles)
        self.logger.info(f"[RSS Read] Completed. Fetched {fetched_count} articles.")

        # ----------------------------------------------------------------------
        # Component 3: Limit & Deduplication
        # ----------------------------------------------------------------------
        self.logger.info("Step 2/5: [Limit & Filter] Filtering stale stories...")
        recency_filtered = self.article_filter.filter_by_recency_and_quality(raw_articles)
        filtered_count = len(recency_filtered)

        self.logger.info("Step 2b/5: [Deduplicate] Removing duplicates & cross-run repeats...")
        deduped = self.deduplicator.deduplicate(recency_filtered, lookback_days=7)
        deduped_count = len(deduped)

        # Apply candidate limit
        candidate_pool = self.article_filter.apply_limit(deduped)

        # ----------------------------------------------------------------------
        # Component 4: Aggregate
        # ----------------------------------------------------------------------
        self.logger.info("Step 3/5: [Aggregate] Ranking candidates across 5 categories...")
        ranked_candidates = self.aggregator.aggregate_and_rank(candidate_pool)
        self.logger.info(f"[Aggregate] Assembled {len(ranked_candidates)} ranked candidate stories.")

        # ----------------------------------------------------------------------
        # Component 5 & 6: Basic LLM Chain + Google Gemini Chat Model
        # ----------------------------------------------------------------------
        self.logger.info("Step 4/5: [LLM Chain] Synthesizing top briefing with Gemini Chat Model...")
        report = self.llm_chain.generate_briefing(
            candidate_articles=ranked_candidates,
            today_date_str=today_date_str,
            top_n=Config.TOP_STORIES,
        )
        selected_count = len(report.top_stories)
        self.logger.info(f"[LLM Chain] Selected {selected_count} top AI updates.")

        # ----------------------------------------------------------------------
        # Component 7: Send a message — Gmail
        # ----------------------------------------------------------------------
        email_sent = False
        error_msg = None

        if self.dry_run:
            self.logger.info("Step 5/5: [Send a message] DRY RUN enabled - skipping Gmail dispatch.")
            print("\n" + "=" * 70)
            print("                DRY RUN BRIEFING PREVIEW")
            print("=" * 70)
            print(self.email_sender.render_plain_text(report))
            print("=" * 70 + "\n")
        else:
            self.logger.info("Step 5/5: [Send a message] Dispatching briefing via Gmail API...")
            try:
                if self.interactive_auth:
                    self.email_sender.authenticate(interactive=True)
                email_sent = self.email_sender.send_briefing(report)
                if email_sent:
                    # Mark stories as sent in SQLite database to prevent repeats tomorrow
                    sent_hashes = [
                        self.deduplicator.hash_url(s.original_source_url)
                        for s in report.top_stories
                    ]
                    self.db.mark_articles_as_sent(sent_hashes)
                    self.logger.info("Briefing delivered and marked in database.")
                else:
                    error_msg = "Gmail dispatch returned false."
            except Exception as e:
                error_msg = str(e)
                self.logger.error(f"Error while dispatching email: {e}")

        # Record run execution metrics in database
        status_str = "SUCCESS" if (self.dry_run or email_sent) else "FAILED"
        self.db.record_run(
            status=status_str,
            fetched=fetched_count,
            filtered=filtered_count,
            deduped=deduped_count,
            selected=selected_count,
            email_sent=email_sent,
            error_msg=error_msg,
        )

        # Print summary report
        print("\n" + "-" * 50)
        print("PIPELINE EXECUTION METRICS:")
        print(f"  Articles Fetched:      {fetched_count}")
        print(f"  Articles Stale/Valid:  {filtered_count}")
        print(f"  Articles Unique:       {deduped_count}")
        print(f"  Articles Analyzed:     {len(ranked_candidates)}")
        print(f"  Stories Selected:      {selected_count}")
        print(f"  Email Dispatched:      {'YES' if email_sent else ('NO (DRY RUN)' if self.dry_run else 'FAILED')}")
        print("-" * 50 + "\n")

        return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily AI Morning Briefing Automation")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run full pipeline and print briefing preview locally without sending email",
    )
    parser.add_argument(
        "--auth-only",
        action="store_true",
        help="Run interactive Gmail OAuth authorization flow to generate token.json",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug log output",
    )
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    if args.auth_only:
        print("Launching interactive Gmail OAuth flow...")
        Config.resolve_paths()
        sender = GmailSender(
            credentials_file=Config.GMAIL_CREDENTIALS_FILE,
            token_file=Config.GMAIL_TOKEN_FILE,
            recipient_email=Config.RECIPIENT_EMAIL or "test@example.com",
        )
        success = sender.authenticate(interactive=True)
        if success:
            print(f"Successfully authenticated Gmail API! Token saved to {Config.GMAIL_TOKEN_FILE}")
            sys.exit(0)
        else:
            print("Authentication failed. Please check credentials.json")
            sys.exit(1)

    pipeline = BriefingPipeline(dry_run=args.dry_run)
    pipeline.run()


if __name__ == "__main__":
    main()
