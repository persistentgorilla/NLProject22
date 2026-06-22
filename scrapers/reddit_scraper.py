"""
Spotify Review Discovery Engine - Reddit Scraper
===================================================
Collects Spotify-related discussions from Reddit using public RSS feeds
(with optional JSON fallback). RSS avoids the 403 blocks that anonymous
JSON requests hit from cloud and datacenter IPs.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from typing import Any, Callable, Dict, List, Optional

import pandas as pd
import requests

import sys
sys.path.insert(0, ".")

from config import settings
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
_TAG_RE = re.compile(r"<[^>]+>")


class RedditScraper(BaseScraper):
    """Scrape Spotify-related posts from Reddit via RSS (primary) or JSON."""

    def __init__(
        self,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        subreddits: Optional[List[str]] = None,
        queries: Optional[List[str]] = None,
        posts_per_query: int = settings.REDDIT_POSTS_PER_QUERY,
    ) -> None:
        super().__init__(progress_callback=progress_callback)
        self.subreddits = subreddits or list(settings.REDDIT_SUBREDDITS)
        self.queries = queries or list(settings.REDDIT_SEARCH_QUERIES)
        self.posts_per_query = posts_per_query
        self.sleep_seconds: float = settings.REDDIT_SLEEP_SECONDS
        self._session = requests.Session()
        self._session.headers.update(settings.DEFAULT_REQUEST_HEADERS)

    def scrape(self) -> pd.DataFrame:
        """Collect Reddit discussions and return a standardised DataFrame."""
        if settings.REDDIT_USE_RSS:
            df = self._scrape_via_rss()
            if not df.empty:
                return df
            self.logger.warning("Reddit RSS returned no data — trying PullPush archive API.")

        df = self._scrape_via_pullpush()
        if not df.empty:
            return df

        self.logger.warning("PullPush returned no data — trying JSON fallback.")
        return self._scrape_via_json()

    def _scrape_via_rss(self) -> pd.DataFrame:
        """Fetch posts using Reddit Atom RSS feeds (one feed per subreddit)."""
        self.logger.info(
            "Starting Reddit RSS scrape — %d subreddits",
            len(self.subreddits),
        )

        all_reviews: List[Dict[str, Any]] = []

        for idx, subreddit in enumerate(self.subreddits, start=1):
            self.logger.info("[%d/%d] r/%s — new.rss", idx, len(self.subreddits), subreddit)
            records = self._fetch_rss_feed(subreddit)
            records = self._filter_records_for_subreddit(subreddit, records)
            all_reviews.extend(records)
            self._notify_progress(idx, len(self.subreddits))
            self._rate_limit(self.sleep_seconds)

        return self._records_to_dataframe(all_reviews)

    def _filter_records_for_subreddit(
        self, subreddit: str, records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Keep Spotify-focused posts on general music subreddits."""
        if subreddit.lower() in {"spotify", "spotifyindia"}:
            return records

        keywords = ["spotify"] + [q.lower() for q in self.queries]
        filtered: List[Dict[str, Any]] = []
        for record in records:
            text = str(record.get("review_text", "")).lower()
            if any(kw in text for kw in keywords):
                filtered.append(record)
        return filtered

    def _fetch_rss_feed(self, subreddit: str) -> List[Dict[str, Any]]:
        """Download and parse the latest-posts RSS feed for a subreddit."""
        url = f"https://old.reddit.com/r/{subreddit}/new.rss"
        for attempt in range(2):
            try:
                resp = self._session.get(
                    url,
                    timeout=20,
                    headers={
                        **settings.DEFAULT_REQUEST_HEADERS,
                        "Accept": "application/atom+xml, application/xml, text/xml",
                        "Referer": "https://old.reddit.com/",
                    },
                )
                if resp.status_code == 429 and attempt == 0:
                    self.logger.warning("Reddit RSS rate-limited — retrying in 5s …")
                    self._rate_limit(5)
                    continue
                if resp.status_code in (403, 429):
                    self.logger.warning(
                        "Reddit RSS blocked (%s) for r/%s",
                        resp.status_code,
                        subreddit,
                    )
                    return []
                resp.raise_for_status()
                return self._parse_rss_entries(resp.content)
            except requests.RequestException as exc:
                self.logger.error("Reddit RSS request failed for r/%s: %s", subreddit, exc)
                return []
        return []

    def _scrape_via_pullpush(self) -> pd.DataFrame:
        """Fetch recent submissions via the PullPush Reddit archive API."""
        self.logger.info(
            "Starting Reddit PullPush scrape — %d subreddits",
            len(self.subreddits),
        )
        all_reviews: List[Dict[str, Any]] = []

        for idx, subreddit in enumerate(self.subreddits, start=1):
            records = self._fetch_pullpush_subreddit(subreddit)
            records = self._filter_records_for_subreddit(subreddit, records)
            all_reviews.extend(records)
            self._notify_progress(idx, len(self.subreddits))
            self._rate_limit(self.sleep_seconds)

        return self._records_to_dataframe(all_reviews)

    def _fetch_pullpush_subreddit(self, subreddit: str) -> List[Dict[str, Any]]:
        """Load recent submissions for one subreddit from PullPush."""
        url = "https://api.pullpush.io/reddit/search/submission/"
        params = {
            "subreddit": subreddit,
            "size": self.posts_per_query,
            "sort": "desc",
            "sort_type": "created_utc",
        }
        try:
            resp = self._session.get(url, params=params, timeout=20)
            resp.raise_for_status()
            payload = resp.json()
        except (requests.RequestException, ValueError) as exc:
            self.logger.error("PullPush request failed for r/%s: %s", subreddit, exc)
            return []

        records: List[Dict[str, Any]] = []
        for item in payload.get("data", []):
            title = str(item.get("title") or "").strip()
            body = str(item.get("selftext") or "").strip()
            if body in ("[removed]", "[deleted]"):
                body = ""
            review_text = f"{title}\n\n{body}".strip() if body else title
            if not review_text:
                continue

            created = item.get("created_utc")
            date_val = self._unix_to_iso(float(created)) if created is not None else None
            records.append(
                {
                    "source": "Reddit",
                    "review_text": review_text,
                    "rating": None,
                    "date": date_val,
                    "username": item.get("author"),
                    "helpful_count": item.get("score"),
                    "app_version": None,
                    "language": None,
                    "country": None,
                    "title": title,
                }
            )
        return records

    def _parse_rss_entries(self, payload: bytes) -> List[Dict[str, Any]]:
        """Parse Atom entries from a Reddit RSS payload."""
        records: List[Dict[str, Any]] = []
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            self.logger.warning("Reddit RSS parse error: %s", exc)
            return []

        for entry in root.findall("atom:entry", _ATOM_NS):
            title_el = entry.find("atom:title", _ATOM_NS)
            updated_el = entry.find("atom:updated", _ATOM_NS)
            content_el = entry.find("atom:content", _ATOM_NS)
            author_el = entry.find("atom:author/atom:name", _ATOM_NS)

            title = unescape(title_el.text.strip()) if title_el is not None and title_el.text else ""
            body = ""
            if content_el is not None and content_el.text:
                body = _TAG_RE.sub("", unescape(content_el.text)).strip()

            review_text = f"{title}\n\n{body}".strip() if body else title
            if not review_text:
                continue

            username = author_el.text.strip() if author_el is not None and author_el.text else None
            date_val = updated_el.text if updated_el is not None else None

            records.append(
                {
                    "source": "Reddit",
                    "review_text": review_text,
                    "rating": None,
                    "date": date_val,
                    "username": username,
                    "helpful_count": None,
                    "app_version": None,
                    "language": None,
                    "country": None,
                    "title": title,
                }
            )

        return records

    def _scrape_via_json(self) -> pd.DataFrame:
        """Legacy JSON scraper kept as a fallback when RSS is unavailable."""
        total_combos = len(self.subreddits) * len(self.queries)
        self.logger.info(
            "Starting Reddit JSON scrape — %d subreddits × %d queries",
            len(self.subreddits),
            len(self.queries),
        )

        all_reviews: List[Dict[str, Any]] = []
        combo_idx = 0

        for subreddit in self.subreddits:
            for query in self.queries:
                combo_idx += 1
                posts = self._search_posts_json(subreddit, query)
                for post in posts:
                    all_reviews.append(self._post_to_record(post))
                    all_reviews.extend(self._fetch_comments_json(post["id"]))
                self._notify_progress(combo_idx, total_combos)
                self._rate_limit(self.sleep_seconds)

        return self._records_to_dataframe(all_reviews)

    def _records_to_dataframe(self, all_reviews: List[Dict[str, Any]]) -> pd.DataFrame:
        if not all_reviews:
            self.logger.warning("No Reddit reviews were collected.")
            return self._create_empty_dataframe()

        df = pd.DataFrame(all_reviews, columns=settings.STANDARD_COLUMNS)
        df = self._standardize_dataframe(df)
        before = len(df)
        df = df.drop_duplicates(subset=["review_text"], keep="first").reset_index(drop=True)
        if before != len(df):
            self.logger.info("Deduplicated Reddit reviews %d → %d.", before, len(df))
        self.logger.info("Reddit scrape complete — %d reviews.", len(df))
        return df

    def _get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        try:
            resp = self._session.get(
                url,
                params=params,
                timeout=15,
                headers={**settings.DEFAULT_REQUEST_HEADERS, "Accept": "application/json"},
            )
            if resp.status_code in (403, 429):
                self.logger.warning("Reddit JSON blocked (%s) on %s", resp.status_code, url)
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            self.logger.error("Reddit JSON request failed for %s: %s", url, exc)
            return None

    def _search_posts_json(self, subreddit: str, query: str) -> List[Dict[str, Any]]:
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {
            "q": query,
            "sort": "new",
            "limit": self.posts_per_query,
            "restrict_sr": 1,
        }
        data = self._get_json(url, params=params)
        if data is None:
            return []
        try:
            return [child["data"] for child in data["data"]["children"]]
        except (KeyError, TypeError):
            return []

    def _post_to_record(self, post: Dict[str, Any]) -> Dict[str, Any]:
        title = post.get("title", "")
        selftext = post.get("selftext", "")
        review_text = f"{title}\n\n{selftext}".strip() if selftext else title
        return {
            "source": "Reddit",
            "review_text": review_text,
            "rating": None,
            "date": self._unix_to_iso(post.get("created_utc")),
            "username": post.get("author"),
            "helpful_count": post.get("score"),
            "app_version": None,
            "language": None,
            "country": None,
            "title": title,
        }

    def _fetch_comments_json(self, post_id: str) -> List[Dict[str, Any]]:
        url = f"https://www.reddit.com/comments/{post_id}.json"
        data = self._get_json(url)
        if data is None:
            return []

        records: List[Dict[str, Any]] = []
        try:
            comment_listing = data[1]["data"]["children"]
        except (KeyError, TypeError, IndexError):
            return []

        for child in comment_listing:
            if child.get("kind") != "t1":
                continue
            c = child["data"]
            body = c.get("body", "")
            if not body or body in ("[deleted]", "[removed]"):
                continue
            records.append(
                {
                    "source": "Reddit",
                    "review_text": body,
                    "rating": None,
                    "date": self._unix_to_iso(c.get("created_utc")),
                    "username": c.get("author"),
                    "helpful_count": c.get("score"),
                    "app_version": None,
                    "language": None,
                    "country": None,
                    "title": None,
                }
            )
        return records

    @staticmethod
    def _unix_to_iso(ts: Optional[float]) -> Optional[str]:
        if ts is None:
            return None
        try:
            return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
        except (ValueError, OSError, OverflowError):
            return None
