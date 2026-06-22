"""
Spotify Review Discovery Engine - Google Play Store Scraper
=============================================================
Fetches Spotify reviews from the Google Play Store using the
``google_play_scraper`` library.  Supports pagination via
continuation tokens and maps raw fields to the project's
standardised column schema.
"""

import logging
from datetime import datetime
from typing import Callable, List, Optional

import pandas as pd

import sys
sys.path.insert(0, ".")

from config import settings
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class PlayStoreScraper(BaseScraper):
    """Scrape Spotify reviews from the Google Play Store.

    Parameters
    ----------
    progress_callback : callable or None
        Optional ``(current, total)`` callback for progress bars.
    count : int
        Target number of reviews to retrieve (default from config).
    country : str
        Two-letter ISO country code (default from config).
    lang : str
        Language code (default from config).
    sort : Sort
        Sort order — imported from ``google_play_scraper.Sort``
        (default ``Sort.NEWEST``).
    """

    def __init__(
        self,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        count: int = settings.PLAYSTORE_MIN_REVIEWS,
        country: str = settings.PLAYSTORE_DEFAULT_COUNTRY,
        lang: str = settings.PLAYSTORE_DEFAULT_LANG,
        sort=None,
    ) -> None:
        super().__init__(progress_callback=progress_callback)
        self.count = count
        self.country = country
        self.lang = lang
        # Defer the Sort import so the module still loads when the
        # library is absent (tests / dry-runs).
        self.sort = sort  # resolved lazily in scrape()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def scrape(self) -> pd.DataFrame:
        """Fetch reviews from the Google Play Store.

        Returns
        -------
        pd.DataFrame
            Standardised DataFrame of reviews.  Returns an empty
            DataFrame on failure.
        """
        try:
            from google_play_scraper import Sort, reviews
        except ImportError:
            self.logger.error(
                "google_play_scraper is not installed. "
                "Run: pip install google-play-scraper"
            )
            return self._create_empty_dataframe()

        # Resolve default sort if caller did not provide one.
        if self.sort is None:
            self.sort = Sort.NEWEST

        if self.count <= 0:
            self.logger.info("Play Store target count is 0 — skipping scrape.")
            return self._create_empty_dataframe()

        self.logger.info(
            "Starting Play Store scrape — target=%d, country=%s, lang=%s",
            self.count,
            self.country,
            self.lang,
        )

        all_reviews: List[dict] = []
        continuation_token: Optional[str] = None
        batch_size: int = settings.PLAYSTORE_BATCH_SIZE
        sleep_seconds: float = settings.PLAYSTORE_SLEEP_MS / 1000.0

        while len(all_reviews) < self.count:
            try:
                batch, continuation_token = reviews(
                    settings.SPOTIFY_PLAYSTORE_ID,
                    lang=self.lang,
                    country=self.country,
                    sort=self.sort,
                    count=batch_size,
                    continuation_token=continuation_token,
                )
            except Exception as exc:
                self.logger.error("Play Store API error: %s", exc)
                break

            if not batch:
                self.logger.info("No more reviews returned — stopping.")
                break

            all_reviews.extend(batch)
            self.logger.info(
                "Fetched batch of %d reviews (total so far: %d)",
                len(batch),
                len(all_reviews),
            )
            self._notify_progress(len(all_reviews), self.count)

            # If there is no token the API has exhausted available reviews.
            if continuation_token is None:
                self.logger.info("No continuation token — all reviews retrieved.")
                break

            # Respect rate limits between batches.
            self._rate_limit(sleep_seconds)

        if not all_reviews:
            self.logger.warning("No Play Store reviews were collected.")
            return self._create_empty_dataframe()

        all_reviews = all_reviews[: self.count]
        df = self._transform(all_reviews)
        self.logger.info("Play Store scrape complete — %d reviews.", len(df))
        return df

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _transform(self, raw_reviews: List[dict]) -> pd.DataFrame:
        """Map raw Play Store fields to standardised columns.

        Field mapping
        -------------
        content       → review_text
        score         → rating
        at            → date
        userName      → username
        thumbsUpCount → helpful_count
        reviewCreatedVersion → app_version
        """
        records = []
        for r in raw_reviews:
            date_val = r.get("at")
            if isinstance(date_val, datetime):
                date_val = date_val.isoformat()

            records.append(
                {
                    "source": "Google Play Store",
                    "review_text": r.get("content"),
                    "rating": r.get("score"),
                    "date": date_val,
                    "username": r.get("userName"),
                    "helpful_count": r.get("thumbsUpCount"),
                    "app_version": r.get("reviewCreatedVersion"),
                    "language": self.lang,
                    "country": self.country,
                    "title": None,
                }
            )

        df = pd.DataFrame(records, columns=settings.STANDARD_COLUMNS)
        return self._standardize_dataframe(df)
