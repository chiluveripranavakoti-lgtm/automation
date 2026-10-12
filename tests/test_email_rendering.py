import pytest
from pathlib import Path
from email_sender import GmailSender
from llm_chain import BriefingReport, StoryItem


def test_email_rendering_and_escaping():
    sender = GmailSender(
        credentials_file=Path("dummy_creds.json"),
        token_file=Path("dummy_token.json"),
        recipient_email="test@example.com",
    )

    report = BriefingReport(
        briefing_date="Monday, October 12, 2026",
        overall_theme_summary="Breakthrough models released across frontier research labs with strong developer adoption.",
        top_stories=[
            StoryItem(
                headline="Google DeepMind announces Gemini 3.8 <script>alert('xss')</script>",
                category="AI Research & Breakthroughs",
                publication_date="2026-10-12",
                source_name="Google AI Blog",
                concise_summary="Gemini 3.8 is released with advanced reasoning and 1M context.",
                why_it_matters="Expands automated agent capabilities for enterprise users.",
                practical_impact="Developers can integrate through the new SDK.",
                original_source_url="https://blog.google/technology/ai/gemini-3-8/?utm_source=test",
                importance_score=9,
                fact_opinion_label="Official Announcement",
            )
        ],
    )

    html_out = sender.render_html(report)
    plain_out = sender.render_plain_text(report)

    # Check HTML output
    assert "Daily AI Morning Briefing" in html_out
    assert "Monday, October 12, 2026" in html_out
    assert "Gemini 3.8" in html_out
    # Critical security check: XSS script tag MUST be escaped
    assert "<script>" not in html_out
    assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in html_out or "&lt;script&gt;" in html_out

    # Check Plain text output
    assert "DAILY AI MORNING BRIEFING" in plain_out
    assert "https://blog.google/technology/ai/gemini-3-8/?utm_source=test" in plain_out
