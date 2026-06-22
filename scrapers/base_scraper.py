"""
Spotify Review Discovery Engine - Base Scraper
================================================
Abstract base class that all source-specific scrapers extend.
Provides standardized column handling, rate limiting, progress
callback support for Streamlit, and shared logging configuration.
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Callable, Optional

import pandas as pd

import sys
sys.path.insert(0, ".")

from config import settings


logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for all review scrapers.

    Every concrete scraper must implement the ``scrape()`` method and
    return a :class:`pandas.DataFrame` whose columns match
    :pydata:`config.settings.STANDARD_COLUMNS`.

    Parameters
    ----------
    progress_callback : callable or None
        An optional callback invoked as ``progress_callback(current, total)``
        so the Streamlit UI (or any other consumer) can show a progress bar.
    """

    def __init__(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> None:
        self.progress_callback = progress_callback
        self.logger = logging.getLogger(self.__class__.__name__)
        self._configure_logging()

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def _configure_logging(self) -> None:
        """Ensure the scraper logger has at least one handler."""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s | %(name)-24s | %(levelname)-7s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------
    @abstractmethod
    def scrape(self) -> pd.DataFrame:
        """Scrape reviews and return a standardized DataFrame.

        Returns
        -------
        pd.DataFrame
            A DataFrame with columns defined by
            ``config.settings.STANDARD_COLUMNS``.
        """
        ...

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _create_empty_dataframe(self) -> pd.DataFrame:
        """Return an empty DataFrame with standardized columns.

        Returns
        -------
        pd.DataFrame
            Empty DataFrame whose columns match ``STANDARD_COLUMNS``.
        """
        return pd.DataFrame(columns=settings.STANDARD_COLUMNS)

    def _rate_limit(self, seconds: float) -> None:
        """Sleep for *seconds* to respect rate limits.

        Parameters
        ----------
        seconds : float
            Number of seconds to pause between requests.
        """
        if seconds > 0:
            self.logger.debug("Rate-limiting: sleeping %.1f s", seconds)
            time.sleep(seconds)

    def _notify_progress(self, current: int, total: int) -> None:
        """Invoke the progress callback if one was provided.

        Parameters
        ----------
        current : int
            Number of items processed so far.
        total : int
            Target / total number of items.
        """
        if self.progress_callback is not None:
            try:
                self.progress_callback(current, total)
            except Exception as exc:  # pragma: no cover – UI callback errors must not crash
                self.logger.warning("Progress callback error: %s", exc)

    def _standardize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure the DataFrame has exactly the standard columns in order.

        Missing columns are filled with ``None``; extra columns are
        dropped.

        Parameters
        ----------
        df : pd.DataFrame
            Raw DataFrame to standardize.

        Returns
        -------
        pd.DataFrame
            DataFrame with ``STANDARD_COLUMNS`` only.
        """
        for col in settings.STANDARD_COLUMNS:
            if col not in df.columns:
                df[col] = None
        return df[settings.STANDARD_COLUMNS]
