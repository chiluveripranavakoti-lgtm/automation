"""Deduplicator module for Daily AI Morning Briefing.

Performs URL normalization, canonical URL handling, normalized title similarity,
and cross-run SQLite persistence deduplication.
"""

from __future__ import annotations

import hashlib
import re
from typing import List, Set, Tuple
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
import logging

from rss_reader import Article
from database import Database

logger = logging.getLogger(__name__)

# Parameters to strip from URLs for canonical deduplication
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "ref",
    "source",
}


def normalize_url(url: str) -> str:
    """Normalize a URL by stripping tracking parameters, trailing slashes, and lowercasing domain."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        clean_scheme = parsed.scheme.lower() or "https"
        clean_netloc = parsed.netloc.lower()
        # Remove www.
        if clean_netloc.startswith("www."):
            clean_netloc = clean_netloc[4:]

        # Filter query params
        query_items = parse_qsl(parsed.query, keep_blank_values=False)
        filtered_query = [
            (k, v) for k, v in query_items if k.lower() not in TRACKING_PARAMS
        ]
        new_query = urlencode(filtered_query)

        # Normalize path
        path = parsed.path.rstrip("/")

        return urlunparse(
            (clean_scheme, clean_netloc, path, parsed.params, new_query, "")
        )
    except Exception:
        return url.strip().rstrip("/")


def hash_url(url: str) -> str:
    """Generate SHA256 hash of a normalized URL."""
    norm = normalize_url(url)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def normalize_title(title: str) -> str:
    """Normalize a title string for near-duplicate and exact-duplicate detection."""
    if not title:
        return ""
    # Strip trailing punctuation first so source suffixes like '- TechCrunch!' can be caught
    t = title.strip()
    # Remove trailing source branding like " - TechCrunch", " | The Verge"
    t = re.sub(r"(\s*[-|–—]\s*[a-zA-Z0-9\s]+[!.]*)$", "", t, flags=re.IGNORECASE)
    # Lowercase
    t = t.lower()
    # Remove all remaining punctuation
    t = re.sub(r"[^\w\s]", "", t)
    # Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


def compute_word_jaccard_similarity(t1: str, t2: str) -> float:
    """Compute Jaccard similarity coefficient between words of two normalized titles."""
    w1 = set(t1.split())
    w2 = set(t2.split())
    if not w1 or not w2:
        return 0.0
    intersection = len(w1.intersection(w2))
    union = len(w1.union(w2))
    return intersection / union if union > 0 else 0.0


class ArticleDeduplicator:
    """Deduplicates articles within the batch and across historical runs."""

    def __init__(self, db: Database, similarity_threshold: float = 0.65):
        self.db = db
        self.similarity_threshold = similarity_threshold

    @staticmethod
    def hash_url(url: str) -> str:
        """Expose URL hash helper method."""
        return hash_url(url)

    def deduplicate(
        self,
        articles: List[Article],
        lookback_days: int = 7,
    ) -> List[Article]:
        """
        Deduplicates candidate articles.
        1. Filters out articles already sent in previous runs.
        2. Deduplicates intra-batch items by normalized URL and title similarity.
        3. Persists newly seen candidate articles into the database.
        """
        sent_hashes = self.db.get_sent_url_hashes(lookback_days=lookback_days)
        sent_title_norms = self.db.get_recent_title_norms(lookback_days=lookback_days)

        unique_articles: List[Article] = []
        batch_seen_urls: Set[str] = set()
        batch_seen_title_norms: List[Tuple[str, Article]] = []

        for article in articles:
            norm_u = normalize_url(article.url)
            u_hash = hash_url(norm_u)
            norm_t = normalize_title(article.title)

            # Check 1: Already sent in recent days?
            if u_hash in sent_hashes:
                logger.debug(f"Skipping already sent URL: {article.title}")
                continue

            # Check 2: Near duplicate of a story already sent in previous days?
            is_recent_duplicate = False
            for prev_t in sent_title_norms:
                if norm_t == prev_t or compute_word_jaccard_similarity(norm_t, prev_t) >= self.similarity_threshold:
                    is_recent_duplicate = True
                    break
            if is_recent_duplicate:
                logger.debug(f"Skipping story similar to previously sent: {article.title}")
                continue

            # Check 3: Intra-batch URL duplicate
            if norm_u in batch_seen_urls:
                continue

            # Check 4: Intra-batch Title near-duplicate
            is_intra_duplicate = False
            for prev_batch_t, prev_art in batch_seen_title_norms:
                if norm_t == prev_batch_t or compute_word_jaccard_similarity(norm_t, prev_batch_t) >= self.similarity_threshold:
                    is_intra_duplicate = True
                    logger.debug(f"Intra-batch duplicate: '{article.title}' matches '{prev_art.title}'")
                    break

            if is_intra_duplicate:
                continue

            # Save in database as seen
            pub_str = article.published_at.isoformat() if article.published_at else None
            self.db.record_article(
                url_hash=u_hash,
                canonical_url=norm_u,
                title_norm=norm_t,
                title=article.title,
                source=article.source,
                category=article.category,
                published_at=pub_str,
                sent=False,
            )

            batch_seen_urls.add(norm_u)
            batch_seen_title_norms.append((norm_t, article))
            unique_articles.append(article)

        logger.info(
            f"Deduplication complete: {len(articles)} input articles -> {len(unique_articles)} unique articles"
        )
        return unique_articles
