"""Article Filter module for Daily AI Morning Briefing.

Implements Component 3: Limit
Filters out stale articles using a configurable lookback window (defaulting to 48 hours),
limits processing to candidate limit (defaulting to 50 articles), and drops malformed entries.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from rss_reader import Article

logger = logging.getLogger(__name__)


class ArticleFilter:
    """Filters articles by age, validity, and limits candidate pool."""

    def __init__(self, lookback_hours: int = 48, max_candidates: int = 50):
        self.lookback_hours = lookback_hours
        self.max_candidates = max_candidates

    def filter_by_recency_and_quality(
        self,
        articles: List[Article],
        reference_time: Optional[datetime] = None,
    ) -> List[Article]:
        """
        Filters out:
        1. Articles missing title or URL.
        2. Stale articles older than lookback_hours (relative to reference_time or UTC now).
        Articles with missing publication dates are retained cautiously unless they are clearly invalid.
        """
        now = reference_time or datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=self.lookback_hours)

        filtered: List[Article] = []

        for art in articles:
            # Basic validation
            if not art.title or not art.url:
                continue

            if len(art.title.strip()) < 5:
                continue

            # Recency check
            if art.published_at is not None:
                # Ensure tz aware
                pub = art.published_at
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)

                if pub < cutoff_time:
                    logger.debug(f"Article '{art.title}' published {pub} is older than cutoff {cutoff_time}. Discarding.")
                    continue
                # Also filter future dates beyond 24 hours (clock drift / spam)
                if pub > now + timedelta(hours=24):
                    logger.debug(f"Article '{art.title}' has unrealistic future date {pub}. Discarding.")
                    continue

            filtered.append(art)

        logger.info(
            f"Recency filter: {len(articles)} articles -> {len(filtered)} within {self.lookback_hours} hours."
        )
        return filtered

    def apply_limit(self, articles: List[Article]) -> List[Article]:
        """Limits the article list to max_candidates."""
        if len(articles) > self.max_candidates:
            logger.info(f"Limiting candidate pool from {len(articles)} to {self.max_candidates}")
            return articles[: self.max_candidates]
        return articles
