"""
Spotify Review Discovery Engine - Community Forum Scraper
============================================================
Scrapes recent public posts from the Spotify Community forums.

Board-specific URLs now redirect to Spotify login, so this scraper reads
the public "All Posts" feed instead.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup, Tag

import sys
sys.path.insert(0, ".")

from config import settings
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

_DATE_SUFFIX_RE = re.compile(r"-\s*\([^)]+\)\s*$")


class CommunityForumScraper(BaseScraper):
    """Scrape recent posts from the Spotify Community public feed."""

    def __init__(
        self,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        pages: int = settings.COMMUNITY_PAGES,
    ) -> None:
        super().__init__(progress_callback=progress_callback)
        self.pages = pages
        self.base_url: str = settings.COMMUNITY_BASE_URL
        self.recent_posts_path: str = settings.COMMUNITY_RECENT_POSTS_PATH
        self.sleep_seconds: float = settings.COMMUNITY_SLEEP_SECONDS
        self._session = requests.Session()
        self._session.headers.update(settings.DEFAULT_REQUEST_HEADERS)

    def scrape(self) -> pd.DataFrame:
        """Scrape recent community posts and return a standardised DataFrame."""
        self.logger.info(
            "Starting Community Forum scrape — %d pages from recent posts feed",
            self.pages,
        )

        all_reviews: List[Dict[str, Any]] = []

        for page_num in range(1, self.pages + 1):
            try:
                page_reviews = self._scrape_recent_posts_page(page_num)
                all_reviews.extend(page_reviews)
                self.logger.info(
                    "  Page %d → %d posts (total so far: %d)",
                    page_num,
                    len(page_reviews),
                    len(all_reviews),
                )
            except Exception as exc:
                self.logger.warning("  Page %d failed: %s — skipping.", page_num, exc)

            self._notify_progress(page_num, self.pages)
            self._rate_limit(self.sleep_seconds)

        if not all_reviews:
            self.logger.warning("No Community Forum reviews were collected.")
            return self._create_empty_dataframe()

        df = pd.DataFrame(all_reviews, columns=settings.STANDARD_COLUMNS)
        df = self._standardize_dataframe(df)
        before = len(df)
        df = df.drop_duplicates(subset=["review_text"], keep="first").reset_index(drop=True)
        if before != len(df):
            self.logger.info("Deduplicated community posts %d → %d.", before, len(df))
        self.logger.info("Community Forum scrape complete — %d reviews.", len(df))
        return df

    def _scrape_recent_posts_page(self, page_num: int) -> List[Dict[str, Any]]:
        """Fetch and parse one page of the public recent-posts feed."""
        if page_num <= 1:
            url = f"{self.base_url}{self.recent_posts_path}"
            params = {"sort_by": "-date"}
        else:
            url = f"{self.base_url}{self.recent_posts_path}/page/{page_num}"
            params = {"sort_by": "-date"}

        try:
            resp = self._session.get(url, params=params, timeout=20)
            resp.raise_for_status()
        except requests.RequestException as exc:
            self.logger.warning("HTTP error fetching %s: %s", url, exc)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("tr.lia-list-row")
        records: List[Dict[str, Any]] = []

        for row in rows:
            record = self._parse_list_row(row)
            if record is not None:
                records.append(record)

        if not records:
            self.logger.warning(
                "No posts parsed on page %d — page layout may have changed.",
                page_num,
            )
        return records

    def _parse_list_row(self, row: Tag) -> Optional[Dict[str, Any]]:
        """Parse a community recent-post table row."""
        title: Optional[str] = None
        body: Optional[str] = None
        username: Optional[str] = None
        date_str: Optional[str] = None

        title_link = row.select_one("h2.message-subject a.page-link, h2.message-subject a")
        if title_link and title_link.get_text(strip=True):
            raw_title = title_link.get_text(strip=True)
            title = _DATE_SUFFIX_RE.sub("", raw_title).strip()

        body_tag = row.select_one("div.message-subject-body")
        if body_tag and body_tag.get_text(strip=True):
            body = body_tag.get_text(strip=True)

        user_tag = row.select_one("span.UserName a, a.UserAvatar")
        if user_tag:
            username = user_tag.get("title") or user_tag.get("alt") or user_tag.get_text(strip=True)

        date_tag = row.select_one("span.local-friendly-date")
        if date_tag:
            raw_date = date_tag.get("title") or date_tag.get_text(strip=True)
            date_str = raw_date.replace("\u200e", "").replace("\u200f", "").strip() if raw_date else None

        review_text = self._combine_text(title, body)
        if not review_text:
            return None

        return {
            "source": "Community Forum",
            "review_text": review_text,
            "rating": None,
            "date": date_str,
            "username": username,
            "helpful_count": None,
            "app_version": None,
            "language": None,
            "country": None,
            "title": title,
        }

    @staticmethod
    def _combine_text(title: Optional[str], body: Optional[str]) -> Optional[str]:
        parts = [p for p in (title, body) if p]
        return "\n\n".join(parts) if parts else None
