"""Gmail Sender module for Daily AI Morning Briefing.

Implements Component 7: Send a message — Gmail
Uses Gmail API with OAuth 2.0 (minimum required scope 'gmail.send').
Generates modern responsive HTML briefing emails with plain text fallbacks.
Escapes all untrusted article content to prevent HTML injection.
Handles token refresh, missing credentials, and sending errors.
"""

from __future__ import annotations

import base64
import html
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from llm_chain import BriefingReport

logger = logging.getLogger(__name__)

# Minimum required Gmail scope for sending automated briefings
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


class GmailSender:
    """Sends briefing emails via official Gmail API with OAuth 2.0."""

    def __init__(
        self,
        credentials_file: Path,
        token_file: Path,
        recipient_email: str,
    ):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.recipient_email = recipient_email.strip()
        self._service = None

    def authenticate(self, interactive: bool = True) -> bool:
        """
        Authenticate with Gmail API using OAuth 2.0.
        Loads existing token from token_file if valid or refreshes expired token.
        If interactive is True and token doesn't exist, launches local consent flow.
        """
        creds = None
        if self.token_file.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)
            except Exception as e:
                logger.warning(f"Failed to load cached token from {self.token_file}: {e}")

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    logger.info("Refreshing expired Gmail OAuth token...")
                    creds.refresh(Request())
                except Exception as e:
                    logger.warning(f"Error refreshing Gmail OAuth token: {e}")
                    creds = None

            if not creds:
                if not self.credentials_file.exists():
                    logger.error(
                        f"Gmail OAuth client credentials file '{self.credentials_file}' not found! "
                        "Please download it from Google Cloud Console."
                    )
                    return False

                if not interactive:
                    logger.error(
                        "Interactive OAuth login required, but non-interactive mode was specified."
                    )
                    return False

                logger.info("Initiating local Gmail OAuth consent flow...")
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_file), SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    logger.error(f"Failed interactive OAuth authentication flow: {e}")
                    return False

            # Save the newly refreshed or authorized token
            if creds and creds.valid:
                self.token_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.token_file, "w", encoding="utf-8") as token_out:
                    token_out.write(creds.to_json())
                logger.info(f"Saved OAuth token to {self.token_file}")

        try:
            self._service = build("gmail", "v1", credentials=creds)
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Gmail API service: {e}")
            return False

    def render_plain_text(self, report: BriefingReport) -> str:
        """Render fallback plain-text email."""
        lines = [
            f"DAILY AI MORNING BRIEFING - {report.briefing_date}",
            "=" * 60,
            "",
            "TRENDS & SYNTHESIS:",
            report.overall_theme_summary,
            "",
            "=" * 60,
            "TOP STORIES:",
            "",
        ]

        for i, s in enumerate(report.top_stories, start=1):
            lines.extend([
                f"{i}. {s.headline} [{s.category}]",
                f"   Source: {s.source_name} | Date: {s.publication_date} | Importance: {s.importance_score}/10",
                f"   Status: {s.fact_opinion_label}",
                "",
                f"   Summary: {s.concise_summary}",
                "",
                f"   Why it matters: {s.why_it_matters}",
                f"   Practical impact: {s.practical_impact}",
                f"   Read more: {s.original_source_url}",
                "-" * 40,
                "",
            ])

        lines.extend([
            "Automated briefing generated by Daily AI Morning Briefing Engine.",
        ])
        return "\n".join(lines)

    def render_html(self, report: BriefingReport) -> str:
        """Render a clean, responsive HTML email with HTML escaping for untrusted content."""
        date_safe = html.escape(report.briefing_date)
        theme_safe = html.escape(report.overall_theme_summary)

        stories_html = []
        category_colors = {
            "Balanced AI News": "#2563eb",
            "Developer-Focused AI": "#059669",
            "Business-Focused AI": "#d97706",
            "AI Research & Breakthroughs": "#7c3aed",
            "AI Careers & Opportunities": "#db2777",
        }

        for i, s in enumerate(report.top_stories, start=1):
            head_safe = html.escape(s.headline)
            cat_safe = html.escape(s.category)
            source_safe = html.escape(s.source_name)
            pub_safe = html.escape(s.publication_date)
            sum_safe = html.escape(s.concise_summary)
            why_safe = html.escape(s.why_it_matters)
            impact_safe = html.escape(s.practical_impact)
            label_safe = html.escape(s.fact_opinion_label)
            url_safe = html.escape(s.original_source_url)
            badge_color = category_colors.get(s.category, "#4b5563")

            story_card = f"""
            <div style="background-color: #ffffff; border-radius: 8px; border: 1px solid #e5e7eb; margin-bottom: 24px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                <div style="margin-bottom: 8px;">
                    <span style="background-color: {badge_color}; color: #ffffff; font-size: 11px; font-weight: 700; text-transform: uppercase; padding: 4px 8px; border-radius: 4px; display: inline-block;">
                        {cat_safe}
                    </span>
                    <span style="background-color: #f3f4f6; color: #4b5563; font-size: 11px; font-weight: 600; padding: 4px 8px; border-radius: 4px; margin-left: 6px; display: inline-block;">
                        Score: {s.importance_score}/10
                    </span>
                    <span style="background-color: #ecfdf5; color: #047857; font-size: 11px; font-weight: 600; padding: 4px 8px; border-radius: 4px; margin-left: 6px; display: inline-block;">
                        {label_safe}
                    </span>
                </div>
                <h2 style="font-size: 18px; line-height: 1.4; color: #111827; margin: 10px 0 6px 0;">
                    {i}. {head_safe}
                </h2>
                <div style="font-size: 12px; color: #6b7280; margin-bottom: 14px;">
                    <strong>{source_safe}</strong> &bull; {pub_safe}
                </div>
                <p style="font-size: 14px; line-height: 1.6; color: #374151; margin-bottom: 12px;">
                    {sum_safe}
                </p>
                <div style="background-color: #f9fafb; border-left: 3px solid {badge_color}; padding: 10px 14px; margin-bottom: 12px; border-radius: 0 4px 4px 0;">
                    <div style="font-size: 13px; color: #1f2937; margin-bottom: 4px;">
                        <strong>Why it matters:</strong> {why_safe}
                    </div>
                    <div style="font-size: 13px; color: #1f2937;">
                        <strong>Practical impact:</strong> {impact_safe}
                    </div>
                </div>
                <div>
                    <a href="{url_safe}" target="_blank" style="display: inline-block; font-size: 13px; font-weight: 600; color: #2563eb; text-decoration: none;">
                        Read full source article &rarr;
                    </a>
                </div>
            </div>
            """
            stories_html.append(story_card)

        stories_combined = "\n".join(stories_html)

        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily AI Morning Briefing - {date_safe}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f3f4f6; margin: 0; padding: 24px; color: #111827;">
    <div style="max-width: 680px; margin: 0 auto;">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); color: #ffffff; padding: 28px 24px; border-radius: 8px 8px 0 0;">
            <div style="font-size: 12px; text-transform: uppercase; letter-spacing: 1.5px; color: #94a3b8; margin-bottom: 4px;">Automated Executive Intelligence</div>
            <h1 style="font-size: 24px; margin: 0 0 8px 0; font-weight: 800;">Daily AI Morning Briefing</h1>
            <div style="font-size: 14px; color: #cbd5e1;">{date_safe} &bull; 08:00 AM IST Edition</div>
        </div>

        <!-- Synthesis & Trends Card -->
        <div style="background-color: #e0e7ff; border-left: 4px solid #4f46e5; padding: 18px 20px; margin-bottom: 24px; border-radius: 0 0 4px 4px;">
            <h3 style="font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; color: #3730a3; margin: 0 0 6px 0;">Daily Trend Synthesis</h3>
            <p style="font-size: 14px; line-height: 1.5; color: #1e1b4b; margin: 0;">
                {theme_safe}
            </p>
        </div>

        <!-- Stories Section -->
        <div>
            {stories_combined}
        </div>

        <!-- Footer -->
        <div style="text-align: center; padding: 20px; font-size: 12px; color: #9ca3af;">
            <p style="margin: 0 0 4px 0;">Generated by <strong>Daily AI Morning Briefing</strong> with Google Gemini.</p>
            <p style="margin: 0;">This email was dispatched automatically via Gmail API OAuth 2.0.</p>
        </div>
    </div>
</body>
</html>
"""
        return html_template

    def send_briefing(self, report: BriefingReport) -> bool:
        """
        Send the briefing email via Gmail API.
        Never prints or logs sensitive access tokens.
        """
        if not self.recipient_email:
            logger.error("Cannot send email: RECIPIENT_EMAIL is not configured.")
            return False

        if not report.top_stories:
            logger.warning("No stories to email; skipping sending.")
            return False

        if not self._service:
            success = self.authenticate(interactive=False)
            if not success:
                logger.error("Gmail authentication failed; email cannot be sent.")
                return False

        try:
            subject = f"Daily AI Morning Briefing - {report.briefing_date}"
            plain_content = self.render_plain_text(report)
            html_content = self.render_html(report)

            message = MIMEMultipart("alternative")
            message["To"] = self.recipient_email
            message["Subject"] = subject

            # Plain text part
            part1 = MIMEText(plain_content, "plain", "utf-8")
            # HTML part
            part2 = MIMEText(html_content, "html", "utf-8")

            message.attach(part1)
            message.attach(part2)

            raw_base64 = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            body = {"raw": raw_base64}

            logger.info(f"Sending briefing email to {self.recipient_email}...")
            sent_msg = self._service.users().messages().send(userId="me", body=body).execute()
            msg_id = sent_msg.get("id")
            logger.info(f"Briefing email successfully sent! Gmail Message ID: {msg_id}")
            return True

        except HttpError as error:
            logger.error(f"Gmail API HTTP error occurred: {error}")
            return False
        except Exception as error:
            logger.error(f"Unexpected error while sending email: {error}")
            return False
