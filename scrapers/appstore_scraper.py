"""
Spotify Review Discovery Engine - Apple App Store Scraper
===========================================================
Fetches Spotify reviews from the Apple App Store using the
``app_store_scraper`` library, with an iTunes RSS fallback when the
primary library fails.
"""

import logging
from typing import Callable, List, Optional

import pandas as pd
import requests

import sys
sys.path.insert(0, ".")

from config import settings
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class AppStoreScraper(BaseScraper):
    """Scrape Spotify reviews from the Apple App Store.

    Parameters
    ----------
    progress_callback : callable or None
        Optional ``(current, total)`` callback for progress bars.
    count : int
        Target number of reviews (default from config).
    country : str
        Two-letter ISO country code (default from config).
    """

    def __init__(
        self,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        count: int = settings.APPSTORE_DEFAULT_REVIEWS,
        country: str = settings.APPSTORE_DEFAULT_COUNTRY,
    ) -> None:
        super().__init__(progress_callback=progress_callback)
        self.count = count
        self.country = country

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def scrape(self) -> pd.DataFrame:
        """Fetch reviews from the Apple App Store.

        Returns
        -------
        pd.DataFrame
            Standardised DataFrame of reviews.  Returns an empty
            DataFrame on any error (graceful degradation).
        """
        if self.count <= 0:
            self.logger.info("App Store target count is 0 — skipping scrape.")
            return self._create_empty_dataframe()

        df = self._scrape_via_library()
        if not df.empty:
            return df

        self.logger.info("Primary App Store scraper returned no data — trying RSS fallback.")
        return self._scrape_rss_fallback()

    def _scrape_via_library(self) -> pd.DataFrame:
        """Attempt to fetch reviews via the app_store_scraper library."""
        try:
            from app_store_scraper import AppStore
        except ImportError:
            self.logger.error(
                "app_store_scraper is not installed. "
                "Run: pip install app-store-scraper"
            )
            return self._create_empty_dataframe()

        self.logger.info(
            "Starting App Store scrape — target=%d, country=%s",
            self.count,
            self.country,
        )

        try:
            app = AppStore(
                country=self.country,
                app_name=settings.SPOTIFY_APPSTORE_NAME,
                app_id=settings.SPOTIFY_APPSTORE_ID,
            )
        except Exception as exc:
            self.logger.warning(
                "Failed to initialise AppStore object: %s.",
                exc,
            )
            return self._create_empty_dataframe()

        try:
            app.review(how_many=self.count)
        except Exception as exc:
            self.logger.warning("AppStore.review() failed: %s.", exc)
            return self._create_empty_dataframe()

        try:
            raw_reviews: List[dict] = app.reviews
        except Exception as exc:
            self.logger.warning("Could not read app.reviews: %s.", exc)
            return self._create_empty_dataframe()

        if not raw_reviews:
            self.logger.warning("No App Store reviews were collected via library.")
            return self._create_empty_dataframe()

        self._notify_progress(len(raw_reviews), self.count)
        df = self._transform(raw_reviews)
        self.logger.info("App Store library scrape complete — %d reviews.", len(df))
        return df

    def _scrape_rss_fallback(self) -> pd.DataFrame:
        """Fetch reviews from the public iTunes RSS customer-reviews feed."""
        records: List[dict] = []
        page = 1
        max_pages = max(1, (self.count // 50) + 2)
        sleep_seconds = settings.PLAYSTORE_SLEEP_MS / 1000.0

        while len(records) < self.count and page <= max_pages:
            url = (
                f"https://itunes.apple.com/{self.country}/rss/customerreviews/"
                f"page={page}/id={settings.SPOTIFY_APPSTORE_ID}/sortby=mostrecent/json"
            )
            try:
                response = requests.get(
                    url,
                    timeout=30,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; SpotifyReviewEngine/1.0)"},
                )
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                self.logger.warning("RSS page %d failed: %s", page, exc)
                break

            entries = payload.get("feed", {}).get("entry", [])
            if not entries:
                break

            for entry in entries:
                rating = entry.get("im:rating", {}).get("label")
                if rating is None:
                    continue

                content = entry.get("content", {})
                if isinstance(content, dict):
                    review_text = content.get("label", "")
                else:
                    review_text = str(content) if content else ""

                title = entry.get("title", {}).get("label", "")
                username = entry.get("author", {}).get("name", {}).get("label", "")
                date_val = entry.get("updated", {}).get("label") or entry.get("im:date", {}).get("label")

                records.append(
                    {
                        "source": "Apple App Store",
                        "review_text": review_text,
                        "rating": int(rating) if rating else None,
                        "date": date_val,
                        "username": username,
                        "helpful_count": None,
                        "app_version": entry.get("im:version", {}).get("label"),
                        "language": None,
                        "country": self.country,
                        "title": title,
                    }
                )
                if len(records) >= self.count:
                    break

            self._notify_progress(len(records), self.count)
            page += 1
            if len(records) < self.count:
                self._rate_limit(sleep_seconds)

        if not records:
            self.logger.warning("RSS fallback returned no App Store reviews.")
            return self._create_empty_dataframe()

        df = pd.DataFrame(records, columns=settings.STANDARD_COLUMNS)
        df = self._standardize_dataframe(df)
        self.logger.info("App Store RSS fallback complete — %d reviews.", len(df))
        return df

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _transform(self, raw_reviews: List[dict]) -> pd.DataFrame:
        """Map raw App Store fields to standardised columns."""
        records = []
        for r in raw_reviews:
            try:
                date_val = r.get("date")
                if date_val is not None:
                    date_val = str(date_val)

                records.append(
                    {
                        "source": "Apple App Store",
                        "review_text": r.get("review"),
                        "rating": r.get("rating"),
                        "date": date_val,
                        "username": r.get("userName"),
                        "helpful_count": None,
                        "app_version": None,
                        "language": None,
                        "country": self.country,
                        "title": r.get("title"),
                    }
                )
            except Exception as exc:
                self.logger.debug("Skipping malformed review: %s", exc)
                continue

        if not records:
            return self._create_empty_dataframe()

        df = pd.DataFrame(records, columns=settings.STANDARD_COLUMNS)
        return self._standardize_dataframe(df)
