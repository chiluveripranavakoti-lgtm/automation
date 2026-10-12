"""Aggregator module for Daily AI Morning Briefing.

Implements Component 4: Aggregate
Combines filtered and deduplicated articles into a clean, structured dataset for the LLM.
Ranks candidates using recency, source credibility, practical impact, novelty, and relevance.
Ensures balanced candidate representation across all five categories.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from rss_reader import Article

logger = logging.getLogger(__name__)

# Credibility and primary authority weightings
SOURCE_AUTHORITY_WEIGHTS: Dict[str, float] = {
    # Primary AI labs & frontier developers
    "OpenAI News": 1.4,
    "Google AI Blog": 1.4,
    "Google DeepMind": 1.4,
    "Hugging Face Blog": 1.3,
    "GitHub AI Blog": 1.3,
    "Simon Willison Weblog": 1.2,
    # Premier technical / analytical reporting
    "MIT Technology Review": 1.2,
    "TechCrunch AI": 1.1,
    "VentureBeat AI": 1.1,
    "The Verge AI": 1.0,
    "Stratechery": 1.1,
    # Research and Careers
    "arXiv cs.AI": 1.0,
    "Hacker News Jobs": 1.0,
    "RemoteOK AI Jobs": 1.0,
}

# High-signal keywords indicating major practical impact / breakthroughs
HIGH_SIGNAL_KEYWORDS = [
    "release", "launch", "open source", "weights", "benchmark", "breakthrough",
    "gpt", "gemini", "claude", "llama", "deepseek", "agent", "coding",
    "architecture", "multimodal", "reasoning", "funding", "hiring", "internship",
    "tool", "api", "framework", "vulnerability", "frontier", "inference"
]


def score_article(article: Article, reference_time: Optional[datetime] = None) -> float:
    """
    Compute a heuristic ranking score for an article.
    Combines:
    - Base source authority (1.0 to 1.4)
    - Recency score (up to 1.0)
    - High-signal keyword presence (up to 0.8)
    - Content description richness (up to 0.4)
    """
    now = reference_time or datetime.now(timezone.utc)
    
    # 1. Authority score
    authority = SOURCE_AUTHORITY_WEIGHTS.get(article.source, 1.0)

    # 2. Recency score (more recent = higher score)
    recency_score = 0.5
    if article.published_at:
        pub = article.published_at
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        age_hours = max(0.0, (now - pub).total_seconds() / 3600.0)
        # Decay smoothly over 48 hours
        recency_score = max(0.0, 1.0 - (age_hours / 48.0))

    # 3. High signal content
    text = (article.title + " " + article.description).lower()
    matches = sum(1 for kw in HIGH_SIGNAL_KEYWORDS if kw in text)
    keyword_score = min(0.8, matches * 0.15)

    # 4. Description completeness
    desc_score = 0.3 if len(article.description.strip()) > 50 else 0.0

    total_score = (authority * 2.0) + (recency_score * 2.0) + keyword_score + desc_score
    return round(total_score, 3)


class ArticleAggregator:
    """Aggregates and ranks articles ensuring balanced category representation."""

    def __init__(self, top_candidates_limit: int = 50):
        self.top_candidates_limit = top_candidates_limit

    def aggregate_and_rank(
        self,
        articles: List[Article],
        reference_time: Optional[datetime] = None,
    ) -> List[Article]:
        """
        Ranks candidate articles while ensuring all five categories are adequately represented
        in the top candidates pool passed to the LLM.
        """
        if not articles:
            return []

        # Calculate scores
        scored_articles = [
            (score_article(art, reference_time=reference_time), art)
            for art in articles
        ]
        # Sort descending by score
        scored_articles.sort(key=lambda x: x[0], reverse=True)

        # Categorize to preserve diversity
        by_category: Dict[str, List[Article]] = {}
        for score, art in scored_articles:
            by_category.setdefault(art.category, []).append(art)

        # Guarantee at least up to 5 top stories per available category first (if available)
        selected_set = set()
        balanced_pool: List[Article] = []

        categories = list(by_category.keys())
        # Pick top 4 from each category first
        for cat in categories:
            for art in by_category[cat][:4]:
                if art.url not in selected_set:
                    selected_set.add(art.url)
                    balanced_pool.append(art)

        # Fill the remainder from the globally highest-scored articles
        for score, art in scored_articles:
            if len(balanced_pool) >= self.top_candidates_limit:
                break
            if art.url not in selected_set:
                selected_set.add(art.url)
                balanced_pool.append(art)

        logger.info(
            f"Aggregated {len(balanced_pool)} balanced candidates across categories: "
            f"{ {cat: len([a for a in balanced_pool if a.category == cat]) for cat in categories} }"
        )
        return balanced_pool[: self.top_candidates_limit]
