"""Configuration module for Daily AI Morning Briefing.

Loads and validates environment variables, configuration parameters, and paths.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Load .env if present
load_dotenv(dotenv_path=BASE_DIR / ".env")


class Config:
    """Application configuration."""

    # Base Paths
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    LOGS_DIR: Path = BASE_DIR / "logs"

    # Email Settings
    RECIPIENT_EMAIL: str = os.getenv("RECIPIENT_EMAIL", "").strip()

    # Gemini Settings
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    GEMINI_TEMPERATURE: float = float(os.getenv("GEMINI_TEMPERATURE", "0.2"))
    GEMINI_TIMEOUT_SECONDS: int = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "45"))
    GEMINI_MAX_RETRIES: int = int(os.getenv("GEMINI_MAX_RETRIES", "3"))

    # Processing limits & parameters
    LOOKBACK_HOURS: int = int(os.getenv("LOOKBACK_HOURS", "48"))
    MAX_CANDIDATES: int = int(os.getenv("MAX_CANDIDATES", "50"))
    TOP_STORIES: int = int(os.getenv("TOP_STORIES", "5"))

    # Timezone & Schedule
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Kolkata").strip()
    SCHEDULE_TIME: str = os.getenv("SCHEDULE_TIME", "08:00").strip()

    # Gmail OAuth file paths
    GMAIL_CREDENTIALS_FILE: Path = Path(os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json"))
    GMAIL_TOKEN_FILE: Path = Path(os.getenv("GMAIL_TOKEN_FILE", "token.json"))

    # Database
    DATABASE_PATH: Path = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "briefing.db")))

    # Feeds
    CUSTOM_FEEDS_FILE: Optional[str] = os.getenv("CUSTOM_FEEDS_FILE")

    @classmethod
    def resolve_paths(cls) -> None:
        """Resolve relative paths relative to BASE_DIR and ensure directories exist."""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)

        if not cls.GMAIL_CREDENTIALS_FILE.is_absolute():
            cls.GMAIL_CREDENTIALS_FILE = cls.BASE_DIR / cls.GMAIL_CREDENTIALS_FILE

        if not cls.GMAIL_TOKEN_FILE.is_absolute():
            cls.GMAIL_TOKEN_FILE = cls.BASE_DIR / cls.GMAIL_TOKEN_FILE

        if not cls.DATABASE_PATH.is_absolute():
            cls.DATABASE_PATH = cls.BASE_DIR / cls.DATABASE_PATH

        cls.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate_for_execution(cls, dry_run: bool = False) -> tuple[bool, list[str]]:
        """
        Validate whether configuration is sufficient to run.
        Returns (is_valid, list_of_warning_or_error_messages).
        """
        cls.resolve_paths()
        issues: list[str] = []

        if not cls.GEMINI_API_KEY:
            issues.append(
                "GEMINI_API_KEY is not set. The workflow will fall back to the deterministic RSS metadata aggregator."
            )

        if not dry_run:
            if not cls.RECIPIENT_EMAIL:
                issues.append("RECIPIENT_EMAIL is required when sending emails (not dry-run).")
            if not cls.GMAIL_CREDENTIALS_FILE.exists() and not cls.GMAIL_TOKEN_FILE.exists():
                issues.append(
                    f"Gmail credentials not found at '{cls.GMAIL_CREDENTIALS_FILE}' and token not found at '{cls.GMAIL_TOKEN_FILE}'."
                )

        return len(issues) == 0, issues


Config.resolve_paths()
