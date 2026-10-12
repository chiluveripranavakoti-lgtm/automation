"""SQLite database management for Daily AI Morning Briefing.

Maintains persistence across runs to prevent sending duplicate stories on consecutive days
and logs execution records.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Set
import logging

logger = logging.getLogger(__name__)


class Database:
    """Persistent SQLite database manager for articles and run history."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._shared_conn: Optional[sqlite3.Connection] = None
        if str(db_path) == ":memory:":
            self._shared_conn = sqlite3.connect(":memory:", timeout=10.0)
            self._shared_conn.row_factory = sqlite3.Row
        else:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._shared_conn is not None:
            return self._shared_conn
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create required tables if they don't already exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Table to track articles that have been sent or seen recently
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS seen_articles (
                    url_hash TEXT PRIMARY KEY,
                    canonical_url TEXT,
                    title_norm TEXT,
                    title TEXT,
                    source TEXT,
                    category TEXT,
                    published_at TEXT,
                    first_seen_at TEXT,
                    sent_at TEXT
                );
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_seen_title_norm ON seen_articles(title_norm);
            """)

            # Table to record execution runs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS execution_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_timestamp TEXT,
                    status TEXT,
                    articles_fetched INTEGER,
                    articles_filtered INTEGER,
                    articles_deduped INTEGER,
                    articles_selected INTEGER,
                    email_sent INTEGER,
                    error_message TEXT
                );
            """)
            conn.commit()

    def get_sent_url_hashes(self, lookback_days: int = 7) -> Set[str]:
        """Return a set of URL hashes that were already sent in briefings within lookback_days."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT url_hash FROM seen_articles 
                WHERE sent_at IS NOT NULL 
                AND datetime(sent_at) >= datetime('now', ?)
                """,
                (f"-{lookback_days} days",),
            )
            return {row["url_hash"] for row in cursor.fetchall()}

    def get_recent_title_norms(self, lookback_days: int = 7) -> Set[str]:
        """Return normalized titles of stories already sent within lookback_days."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT title_norm FROM seen_articles 
                WHERE sent_at IS NOT NULL 
                AND datetime(sent_at) >= datetime('now', ?)
                """,
                (f"-{lookback_days} days",),
            )
            return {row["title_norm"] for row in cursor.fetchall()}

    def record_article(
        self,
        url_hash: str,
        canonical_url: str,
        title_norm: str,
        title: str,
        source: str,
        category: str,
        published_at: Optional[str] = None,
        sent: bool = False,
    ) -> None:
        """Insert or update an article record."""
        now_iso = datetime.now(timezone.utc).isoformat()
        sent_iso = now_iso if sent else None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO seen_articles (url_hash, canonical_url, title_norm, title, source, category, published_at, first_seen_at, sent_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url_hash) DO UPDATE SET
                    sent_at = coalesce(excluded.sent_at, seen_articles.sent_at)
                """,
                (url_hash, canonical_url, title_norm, title, source, category, published_at, now_iso, sent_iso),
            )
            conn.commit()

    def mark_articles_as_sent(self, url_hashes: list[str]) -> None:
        """Mark a list of URL hashes as sent today."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                "UPDATE seen_articles SET sent_at = ? WHERE url_hash = ?",
                [(now_iso, h) for h in url_hashes],
            )
            conn.commit()

    def record_run(
        self,
        status: str,
        fetched: int,
        filtered: int,
        deduped: int,
        selected: int,
        email_sent: bool,
        error_msg: Optional[str] = None,
    ) -> int:
        """Record an execution run metrics."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO execution_runs (run_timestamp, status, articles_fetched, articles_filtered, articles_deduped, articles_selected, email_sent, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (now_iso, status, fetched, filtered, deduped, selected, 1 if email_sent else 0, error_msg),
            )
            conn.commit()
            return cursor.lastrowid
