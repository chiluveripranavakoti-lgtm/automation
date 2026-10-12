import pytest
from datetime import datetime, timezone, timedelta

from article_filter import ArticleFilter
from rss_reader import Article


def test_recency_filter_removes_stale_articles():
    now = datetime(2026, 10, 12, 10, 0, 0, tzinfo=timezone.utc)
    article_filter = ArticleFilter(lookback_hours=48, max_candidates=50)

    fresh_article = Article(
        title="Fresh AI Innovation",
        url="https://example.com/fresh",
        published_at=now - timedelta(hours=12),
        source="TechCrunch AI",
        category="Balanced AI News",
        description="Just released 12 hours ago.",
    )

    stale_article = Article(
        title="Old AI Innovation From Last Week",
        url="https://example.com/stale",
        published_at=now - timedelta(hours=72),
        source="TechCrunch AI",
        category="Balanced AI News",
        description="Released 72 hours ago.",
    )

    future_spam_article = Article(
        title="Spam From Far Future",
        url="https://example.com/spam",
        published_at=now + timedelta(days=5),
        source="Spam Source",
        category="Balanced AI News",
        description="Spam.",
    )

    results = article_filter.filter_by_recency_and_quality(
        [fresh_article, stale_article, future_spam_article],
        reference_time=now,
    )

    assert len(results) == 1
    assert results[0].title == "Fresh AI Innovation"


def test_apply_limit():
    article_filter = ArticleFilter(lookback_hours=48, max_candidates=3)
    articles = [
        Article(
            title=f"Article {i}",
            url=f"https://example.com/{i}",
            published_at=datetime.now(timezone.utc),
            source="Test Source",
            category="Balanced AI News",
            description=f"Desc {i}",
        )
        for i in range(10)
    ]

    limited = article_filter.apply_limit(articles)
    assert len(limited) == 3
