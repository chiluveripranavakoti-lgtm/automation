"""Basic LLM Chain module for Daily AI Morning Briefing.

Implements Component 5: Basic LLM Chain
- Connects to Google Gemini Chat Model
- Enforces strict briefing output requirements across the 5 categories
- Validates the structured output against Pydantic models
- Implements deterministic fallback generation using verified RSS metadata if LLM fails
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional
from pydantic import BaseModel, Field

from rss_reader import Article
from gemini_model import GeminiChatModel

logger = logging.getLogger(__name__)


class StoryItem(BaseModel):
    """Schema for each individual selected story in the briefing."""
    headline: str = Field(description="Clear, engaging news headline")
    category: str = Field(
        description="One of: Balanced AI News, Developer-Focused AI, Business-Focused AI, AI Research & Breakthroughs, AI Careers & Opportunities"
    )
    publication_date: str = Field(description="ISO or formatted publication date")
    source_name: str = Field(description="Original source publisher name")
    concise_summary: str = Field(
        description="Concise summary in approximately 2 to 4 sentences strictly based on the article text"
    )
    why_it_matters: str = Field(description="Strategic importance and context")
    practical_impact: str = Field(
        description="Actionable impact for developers, businesses, researchers, or job seekers"
    )
    original_source_url: str = Field(description="Exact URL to original story provided in input")
    importance_score: int = Field(
        ge=1, le=10, description="Numerical score from 1 to 10 evaluating global significance"
    )
    fact_opinion_label: str = Field(
        description="Clear label such as 'Verified Fact', 'Official Announcement', or 'Analysis / Opinion'"
    )


class BriefingReport(BaseModel):
    """Complete briefing output schema."""
    briefing_date: str
    overall_theme_summary: str = Field(
        description="A 2-3 sentence overview highlighting notable trends across the categories"
    )
    top_stories: List[StoryItem] = Field(
        description="The top selected AI updates overall (up to 5)"
    )


LLM_SYSTEM_INSTRUCTION = """You are an elite AI Intelligence Analyst producing the Daily AI Morning Briefing.
Your mission is to analyze the candidate articles and select the top 5 most important AI updates overall.

Consider these criteria when picking the top 5 stories:
- Technical significance
- Recency
- Reliability of the source
- Novelty
- Developer usefulness
- Business impact
- Career or earning opportunities
- Long-term importance

Requirements:
1. Cover the 5 categories (Balanced AI News, Developer-Focused AI, Business-Focused AI, AI Research & Breakthroughs, AI Careers & Opportunities) when genuinely useful stories exist, but do NOT force an equal number of articles per category. Select the strongest 5 overall.
2. For each selected story, provide:
   - headline
   - category
   - publication_date
   - source_name
   - concise_summary (2-4 sentences)
   - why_it_matters
   - practical_impact (for devs, businesses, researchers, or job seekers)
   - original_source_url (must match the supplied article URL exactly)
   - importance_score (1 to 10)
   - fact_opinion_label (e.g. 'Verified Fact', 'Official Announcement', 'Analysis / Opinion')
3. TRUTHFULNESS RULE: Use ONLY information supported by the supplied article metadata and descriptions. NEVER invent facts, dates, sources, URLs, benchmarks, job openings, salaries, or claims.
4. If article descriptions are brief or insufficient, clearly state that specific details require checking the original source URL.
5. Provide a synthesis of notable trends across the 5 categories in the overall_theme_summary.
"""


class BasicLLMChain:
    """Executes the briefing synthesis chain using Gemini or fallback."""

    def __init__(self, model: GeminiChatModel):
        self.model = model

    def build_prompt(self, candidate_articles: List[Article], today_date_str: str) -> str:
        """Construct a clean, structured representation of candidate articles."""
        lines = [
            f"DATE: {today_date_str}",
            f"TOTAL CANDIDATES: {len(candidate_articles)}",
            "",
            "=== CANDIDATE ARTICLES ===",
        ]

        for i, art in enumerate(candidate_articles, start=1):
            pub_str = art.published_at.strftime("%Y-%m-%d %H:%M UTC") if art.published_at else "Unknown date"
            lines.extend([
                f"[{i}] TITLE: {art.title}",
                f"    CATEGORY: {art.category}",
                f"    SOURCE: {art.source}",
                f"    DATE: {pub_str}",
                f"    URL: {art.url}",
                f"    SUMMARY: {art.description or 'No description provided.'}",
                "",
            ])

        lines.extend([
            "Select the 5 most important updates overall and output the structured JSON according to schema."
        ])
        return "\n".join(lines)

    def generate_briefing(
        self,
        candidate_articles: List[Article],
        today_date_str: str,
        top_n: int = 5,
    ) -> BriefingReport:
        """
        Synthesizes the morning briefing.
        Attempts Gemini LLM generation first; falls back to deterministic RSS aggregation if unavailable.
        """
        if not candidate_articles:
            return BriefingReport(
                briefing_date=today_date_str,
                overall_theme_summary="No new AI news articles were found in the lookback window.",
                top_stories=[],
            )

        if self.model.is_available():
            prompt = self.build_prompt(candidate_articles, today_date_str)
            try:
                raw_json = self.model.generate_chat_response(
                    prompt=prompt,
                    system_instruction=LLM_SYSTEM_INSTRUCTION,
                    response_schema=BriefingReport,
                )
                if raw_json:
                    parsed_dict = json.loads(raw_json)
                    briefing = BriefingReport.model_validate(parsed_dict)
                    # Limit to top_n just in case
                    briefing.top_stories = briefing.top_stories[:top_n]
                    logger.info(f"LLM chain successfully generated {len(briefing.top_stories)} stories.")
                    return briefing
            except Exception as e:
                logger.error(f"Error parsing Gemini output or LLM execution failed: {e}. Falling back to deterministic digest.")
        else:
            logger.warning("Gemini model not available. Generating deterministic fallback briefing.")

        # Fallback path
        return self._generate_fallback_briefing(candidate_articles, today_date_str, top_n)

    def _generate_fallback_briefing(
        self,
        candidate_articles: List[Article],
        today_date_str: str,
        top_n: int = 5,
    ) -> BriefingReport:
        """
        Deterministic fallback generator using verified RSS metadata.
        Guarantees that the pipeline never halts even if the LLM API is down or unconfigured.
        """
        selected_articles = candidate_articles[:top_n]
        stories: List[StoryItem] = []

        for art in selected_articles:
            pub_str = art.published_at.strftime("%Y-%m-%d") if art.published_at else today_date_str
            summary = art.description if art.description else f"Recent update reported by {art.source} regarding {art.title}."
            
            story = StoryItem(
                headline=art.title,
                category=art.category,
                publication_date=pub_str,
                source_name=art.source,
                concise_summary=summary,
                why_it_matters=f"Significant development in the {art.category} domain reported by {art.source}.",
                practical_impact="Check original source link for technical documentation, code repositories, or full announcements.",
                original_source_url=art.url,
                importance_score=8,
                fact_opinion_label="Verified RSS Metadata (Fallback)",
            )
            stories.append(story)

        return BriefingReport(
            briefing_date=today_date_str,
            overall_theme_summary=(
                "Automated deterministic digest generated directly from top-ranked verified RSS feeds "
                "(LLM synthesis unavailable or offline)."
            ),
            top_stories=stories,
        )
