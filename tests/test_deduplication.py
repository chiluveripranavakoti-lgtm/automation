import pytest
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from database import Database
from deduplicator import ArticleDeduplicator, normalize_url, normalize_title, compute_word_jaccard_similarity
from rss_reader import Article


@pytest.fixture
def temp_db():
    db = Database(Path(":memory:"))
    yield db


def test_url_normalization():
    raw_url = "https://www.example.com/ai/article/?utm_source=twitter&utm_medium=social&utm_campaign=launch#comments"
    norm = normalize_url(raw_url)
    assert norm == "https://example.com/ai/article"


def test_title_normalization():
    title = "Anthropic Unveils Claude 3.5 Sonnet - TechCrunch!"
    norm = normalize_title(title)
    assert norm == "anthropic unveils claude 35 sonnet"


def test_word_jaccard_similarity():
    t1 = "google deepmind introduces new gemini 2 model"
    t2 = "google deepmind releases new gemini 2 model"
    sim = compute_word_jaccard_similarity(t1, t2)
    assert sim >= 0.7


def test_intra_batch_and_database_deduplication(temp_db):
    dedup = ArticleDeduplicator(temp_db, similarity_threshold=0.6)

    art1 = Article(
        title="OpenAI Releases GPT-5 Frontier Model",
        url="https://openai.com/news/gpt-5?utm_source=rss",
        published_at=datetime.now(timezone.utc),
        source="OpenAI News",
        category="AI Research & Breakthroughs",
        description="Official release of GPT-5 with reasoning capabilities.",
    )

    art2_dup_url = Article(
        title="OpenAI Releases GPT-5 Frontier Model (Duplicate)",
        url="https://openai.com/news/gpt-5?utm_medium=feed",
        published_at=datetime.now(timezone.utc),
        source="TechCrunch AI",
        category="Balanced AI News",
        description="Duplicate URL with tracking tags.",
    )

    art3_dup_title = Article(
        title="OpenAI Releases GPT-5 Frontier Model!",
        url="https://theverge.com/ai/gpt-5-news",
        published_at=datetime.now(timezone.utc),
        source="The Verge AI",
        category="Balanced AI News",
        description="Reporting on the same release.",
    )

    art4_unique = Article(
        title="New Open Source Code LLM Released on HuggingFace",
        url="https://huggingface.co/blog/new-code-llm",
        published_at=datetime.now(timezone.utc),
        source="Hugging Face Blog",
        category="Developer-Focused AI",
        description="A lightweight coding model.",
    )

    result = dedup.deduplicate([art1, art2_dup_url, art3_dup_title, art4_unique])
    assert len(result) == 2
    assert result[0].title == "OpenAI Releases GPT-5 Frontier Model"
    assert result[1].title == "New Open Source Code LLM Released on HuggingFace"

    # Mark art1 as sent
    u_hash = dedup.hash_url(art1.url) if hasattr(dedup, "hash_url") else normalize_url(art1.url)
    import hashlib
    u_hash = hashlib.sha256(normalize_url(art1.url).encode()).hexdigest()
    temp_db.mark_articles_as_sent([u_hash])

    # In second run, art1 must be filtered out because it was already sent
    result2 = dedup.deduplicate([art1, art4_unique])
    assert len(result2) == 1
    assert result2[0].title == "New Open Source Code LLM Released on HuggingFace"
