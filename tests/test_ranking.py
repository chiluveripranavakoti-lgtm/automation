import pytest
from datetime import datetime, timezone, timedelta

from aggregator import ArticleAggregator, score_article
from rss_reader import Article


def test_ranking_weights_and_category_balance():
    now = datetime(2026, 10, 12, 10, 0, 0, tzinfo=timezone.utc)
    
    # Lab announcement with high-signal keywords and recency
    top_lab_art = Article(
        title="OpenAI announces GPT-5 release and reasoning benchmark",
        url="https://openai.com/news/gpt-5",
        published_at=now - timedelta(hours=2),
        source="OpenAI News",
        category="AI Research & Breakthroughs",
        description="Major benchmark results for new frontier model.",
    )

    # General news without high signals
    generic_art = Article(
        title="Some thoughts on technology and devices",
        url="https://example.com/thoughts",
        published_at=now - timedelta(hours=40),
        source="The Verge AI",
        category="Balanced AI News",
        description="Just general commentary.",
    )

    s1 = score_article(top_lab_art, reference_time=now)
    s2 = score_article(generic_art, reference_time=now)
    assert s1 > s2

    # Test category diversity aggregation
    categories = [
        "Balanced AI News",
        "Developer-Focused AI",
        "Business-Focused AI",
        "AI Research & Breakthroughs",
        "AI Careers & Opportunities",
    ]

    articles = []
    for cat in categories:
        for j in range(3):
            articles.append(
                Article(
                    title=f"{cat} Story {j}",
                    url=f"https://example.com/{cat.replace(' ', '_')}_{j}",
                    published_at=now - timedelta(hours=j),
                    source="Google AI Blog" if "Research" in cat else "TechCrunch AI",
                    category=cat,
                    description="Details on AI developments.",
                )
            )

    aggregator = ArticleAggregator(top_candidates_limit=15)
    ranked = aggregator.aggregate_and_rank(articles, reference_time=now)

    assert len(ranked) == 15
    # Verify that all 5 categories are represented
    found_cats = {a.category for a in ranked}
    assert len(found_cats) == 5
