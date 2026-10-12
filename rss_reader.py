"""RSS Reader module for Daily AI Morning Briefing.

Fetches AI news updates from reliable RSS feeds categorized across the five required domains:
1. Balanced AI News
2. Developer-Focused AI
3. Business-Focused AI
4. AI Research & Breakthroughs
5. AI Careers & Opportunities

Robust against timeouts, malformed XML, and unavailable feeds.
"""

from __future__ import annotations

import html
import json
import logging
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from time import mktime
from typing import List, Optional
import urllib.request
import urllib.error

import feedparser

logger = logging.getLogger(__name__)


@dataclass
class Article:
    """Represents a standardized RSS article."""
    title: str
    url: str
    published_at: Optional[datetime]
    source: str
    category: str
    description: str
    guid: Optional[str] = None
    author: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.published_at:
            d["published_at"] = self.published_at.isoformat()
        return d


# Reliable, high-quality RSS feeds mapped to the 5 mandatory categories
DEFAULT_FEEDS = [
    # 1. Balanced AI News
    {
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "source": "TechCrunch AI",
        "category": "Balanced AI News",
        "weight": 1.0,
    },
    {
        "url": "https://venturebeat.com/category/ai/feed/",
        "source": "VentureBeat AI",
        "category": "Balanced AI News",
        "weight": 1.0,
    },
    {
        "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "source": "The Verge AI",
        "category": "Balanced AI News",
        "weight": 1.0,
    },

    # 2. Developer-Focused AI
    {
        "url": "https://github.blog/category/ai-and-ml/feed/",
        "source": "GitHub AI Blog",
        "category": "Developer-Focused AI",
        "weight": 1.2,
    },
    {
        "url": "https://huggingface.co/blog/feed.xml",
        "source": "Hugging Face Blog",
        "category": "Developer-Focused AI",
        "weight": 1.2,
    },
    {
        "url": "https://simonwillison.net/atom/everything/",
        "source": "Simon Willison Weblog",
        "category": "Developer-Focused AI",
        "weight": 1.1,
    },

    # 3. Business-Focused AI
    {
        "url": "https://www.technologyreview.com/feed/",
        "source": "MIT Technology Review",
        "category": "Business-Focused AI",
        "weight": 1.1,
    },
    {
        "url": "https://stratechery.com/feed/",
        "source": "Stratechery",
        "category": "Business-Focused AI",
        "weight": 1.0,
    },

    # 4. AI Research & Breakthroughs
    {
        "url": "https://openai.com/news/rss.xml",
        "source": "OpenAI News",
        "category": "AI Research & Breakthroughs",
        "weight": 1.3,
    },
    {
        "url": "https://blog.google/technology/ai/rss/",
        "source": "Google AI Blog",
        "category": "AI Research & Breakthroughs",
        "weight": 1.3,
    },
    {
        "url": "https://www.deepmind.com/blog/rss.xml",
        "source": "Google DeepMind",
        "category": "AI Research & Breakthroughs",
        "weight": 1.3,
    },
    {
        "url": "https://arxiv.org/rss/cs.AI",
        "source": "arXiv cs.AI",
        "category": "AI Research & Breakthroughs",
        "weight": 0.9,
    },

    # 5. AI Careers & Opportunities
    {
        "url": "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
        "source": "WeWorkRemotely AI/Dev Jobs",
        "category": "AI Careers & Opportunities",
        "weight": 1.0,
    },
    {
        "url": "https://jobicy.com/?feed=job_feed&job_categories=data-science",
        "source": "Jobicy AI & Data Science",
        "category": "AI Careers & Opportunities",
        "weight": 1.0,
    },
]


def clean_html(raw_html: str) -> str:
    """Strip HTML tags and unescape HTML entities for clean text descriptions."""
    if not raw_html:
        return ""
    # Strip HTML tags
    clean = re.sub(r"<[^>]+>", " ", raw_html)
    # Decode HTML entities
    clean = html.unescape(clean)
    # Collapse multiple whitespaces
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def parse_entry_datetime(entry: dict) -> Optional[datetime]:
    """Extract standard UTC datetime from feed entry."""
    for time_key in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed_time = entry.get(time_key)
        if parsed_time:
            try:
                return datetime.fromtimestamp(mktime(parsed_time), tz=timezone.utc)
            except Exception:
                pass
    return None


class RSSReader:
    """Reads and parses articles from multiple RSS feeds."""

    def __init__(self, feeds: Optional[List[dict]] = None, timeout: int = 15):
        self.feeds = feeds or DEFAULT_FEEDS
        self.timeout = timeout

    @classmethod
    def from_config(cls, custom_feeds_file: Optional[str] = None, timeout: int = 15) -> "RSSReader":
        feeds = list(DEFAULT_FEEDS)
        if custom_feeds_file:
            path = Path(custom_feeds_file)
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        custom = json.load(f)
                        if isinstance(custom, list):
                            feeds = custom
                            logger.info(f"Loaded {len(feeds)} custom RSS feeds from {path}")
                except Exception as e:
                    logger.warning(f"Failed to load custom feeds file: {e}. Using default feeds.")
        return cls(feeds=feeds, timeout=timeout)

    def fetch_feed(self, feed_cfg: dict) -> List[Article]:
        """Fetch and parse a single feed safely."""
        url = feed_cfg["url"]
        source_name = feed_cfg.get("source", "Unknown Source")
        category = feed_cfg.get("category", "Balanced AI News")
        articles: List[Article] = []

        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DailyAIBriefingBot/1.0"
                },
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                content = resp.read()

            parsed = feedparser.parse(content)

            if parsed.bozo and not parsed.entries:
                logger.warning(f"Feed error ({source_name}): {parsed.bozo_exception}")
                return []

            for entry in parsed.entries:
                title = clean_html(entry.get("title", ""))
                link = entry.get("link", "").strip()
                if not title or not link:
                    continue

                raw_summary = (
                    entry.get("summary")
                    or (entry.get("description") if "description" in entry else "")
                    or ""
                )
                description = clean_html(raw_summary)

                # Truncate overly long descriptions to prevent bloat
                if len(description) > 600:
                    description = description[:597] + "..."

                pub_date = parse_entry_datetime(entry)

                articles.append(
                    Article(
                        title=title,
                        url=link,
                        published_at=pub_date,
                        source=source_name,
                        category=category,
                        description=description,
                        guid=entry.get("id"),
                        author=entry.get("author"),
                    )
                )

            logger.info(f"Fetched {len(articles)} articles from {source_name}")

        except urllib.error.URLError as e:
            logger.warning(f"Network error fetching {source_name} ({url}): {e.reason}")
        except TimeoutError:
            logger.warning(f"Timeout fetching {source_name} ({url})")
        except Exception as e:
            logger.warning(f"Unexpected error parsing {source_name} ({url}): {e}")

        return articles

    def fetch_all(self) -> List[Article]:
        """Fetch articles across all configured feeds."""
        all_articles: List[Article] = []
        for feed in self.feeds:
            articles = self.fetch_feed(feed)
            all_articles.extend(articles)
        logger.info(f"Total articles fetched across all feeds: {len(all_articles)}")
        return all_articles
