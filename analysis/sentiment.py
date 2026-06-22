"""
Spotify Review Discovery Engine — Sentiment Analysis Module

Uses VADER for compound/positive/negative/neutral scoring and TextBlob
for subjectivity.  Thresholds are imported from config.settings so they
stay in one place.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer as VaderAnalyzer

from config.settings import SENTIMENT_POSITIVE_THRESHOLD, SENTIMENT_NEGATIVE_THRESHOLD

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """Analyse review-level sentiment with VADER + TextBlob.

    Attributes
    ----------
    vader : VaderAnalyzer
        Pre-initialised VADER analyser (avoids repeated instantiation).
    pos_threshold : float
        Compound score ≥ this → *Positive*.
    neg_threshold : float
        Compound score ≤ this → *Negative*.
    """

    def __init__(self) -> None:
        """Initialise the VADER analyser and load thresholds from config."""
        self.vader = VaderAnalyzer()
        self.pos_threshold: float = SENTIMENT_POSITIVE_THRESHOLD
        self.neg_threshold: float = SENTIMENT_NEGATIVE_THRESHOLD
        logger.info(
            "SentimentAnalyzer initialised (pos_thresh=%.2f, neg_thresh=%.2f)",
            self.pos_threshold,
            self.neg_threshold,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _vader_scores(self, text: str) -> Dict[str, float]:
        """Return VADER polarity dict for a single string.

        Parameters
        ----------
        text : str
            The review text to score.

        Returns
        -------
        dict
            Keys: ``compound``, ``pos``, ``neg``, ``neu``.
        """
        try:
            scores = self.vader.polarity_scores(str(text))
            return {
                "compound": scores["compound"],
                "pos": scores["pos"],
                "neg": scores["neg"],
                "neu": scores["neu"],
            }
        except Exception as exc:  # pragma: no cover
            logger.warning("VADER scoring failed for text (%.30s…): %s", text, exc)
            return {"compound": 0.0, "pos": 0.0, "neg": 0.0, "neu": 1.0}

    def _subjectivity(self, text: str) -> float:
        """Return TextBlob subjectivity for a single string.

        Parameters
        ----------
        text : str
            The review text to score.

        Returns
        -------
        float
            Value in [0.0, 1.0] where 0 is objective and 1 is subjective.
        """
        try:
            return TextBlob(str(text)).sentiment.subjectivity
        except Exception as exc:  # pragma: no cover
            logger.warning("TextBlob subjectivity failed (%.30s…): %s", text, exc)
            return 0.0

    def _label(self, compound: float) -> str:
        """Map a compound score to a human-readable label.

        Parameters
        ----------
        compound : float
            VADER compound score in [-1, 1].

        Returns
        -------
        str
            ``'Positive'``, ``'Negative'``, or ``'Neutral'``.
        """
        if compound >= self.pos_threshold:
            return "Positive"
        if compound <= self.neg_threshold:
            return "Negative"
        return "Neutral"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        """Enrich *df* with sentiment columns.

        Parameters
        ----------
        df : pd.DataFrame
            Must contain a ``review_text`` column.

        Returns
        -------
        pd.DataFrame
            Same DataFrame with added columns:
            ``sentiment_compound``, ``sentiment_label``,
            ``sentiment_pos``, ``sentiment_neg``, ``sentiment_neu``,
            ``subjectivity``.

        Raises
        ------
        ValueError
            If ``review_text`` column is missing.
        """
        if "review_text" not in df.columns:
            raise ValueError("DataFrame must contain a 'review_text' column.")

        result = df.copy()
        n_rows = len(result)
        logger.info("Starting sentiment analysis on %d reviews …", n_rows)

        # Pre-fill with safe defaults so NaN rows get neutral values
        result["sentiment_compound"] = 0.0
        result["sentiment_pos"] = 0.0
        result["sentiment_neg"] = 0.0
        result["sentiment_neu"] = 1.0
        result["subjectivity"] = 0.0
        result["sentiment_label"] = "Neutral"

        # Build a boolean mask for rows that actually have text
        mask = result["review_text"].notna() & (
            result["review_text"].astype(str).str.strip() != ""
        )
        valid_texts: pd.Series = result.loc[mask, "review_text"].astype(str)

        if valid_texts.empty:
            logger.warning("No valid review texts found — returning neutral defaults.")
            return result

        # Compute VADER scores
        vader_results = valid_texts.apply(self._vader_scores)
        vader_df = pd.DataFrame(vader_results.tolist(), index=valid_texts.index)
        result.loc[mask, "sentiment_compound"] = vader_df["compound"]
        result.loc[mask, "sentiment_pos"] = vader_df["pos"]
        result.loc[mask, "sentiment_neg"] = vader_df["neg"]
        result.loc[mask, "sentiment_neu"] = vader_df["neu"]

        # Compute labels
        result.loc[mask, "sentiment_label"] = (
            result.loc[mask, "sentiment_compound"].apply(self._label)
        )

        # Compute subjectivity via TextBlob
        result.loc[mask, "subjectivity"] = valid_texts.apply(self._subjectivity)

        pos_count = (result["sentiment_label"] == "Positive").sum()
        neg_count = (result["sentiment_label"] == "Negative").sum()
        neu_count = (result["sentiment_label"] == "Neutral").sum()
        logger.info(
            "Sentiment analysis complete — Positive: %d, Negative: %d, Neutral: %d",
            pos_count,
            neg_count,
            neu_count,
        )
        return result

    # ------------------------------------------------------------------
    # Summary helpers
    # ------------------------------------------------------------------

    def get_summary_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Return aggregate sentiment statistics.

        Parameters
        ----------
        df : pd.DataFrame
            A DataFrame that has already been processed by :meth:`analyze`
            (i.e. contains ``sentiment_compound`` and ``sentiment_label``
            columns).

        Returns
        -------
        dict
            Keys:
            * ``avg_sentiment`` — mean compound score
            * ``median_sentiment`` — median compound score
            * ``std_sentiment`` — standard-deviation of compound
            * ``distribution`` — ``{label: count}``
            * ``distribution_pct`` — ``{label: percentage}``
            * ``most_positive_reviews`` — top-5 reviews by compound
            * ``most_negative_reviews`` — bottom-5 reviews by compound
            * ``avg_subjectivity`` — mean subjectivity score
        """
        stats: Dict[str, Any] = {}

        # Guard against missing columns
        required = {"sentiment_compound", "sentiment_label"}
        if not required.issubset(df.columns):
            logger.warning(
                "DataFrame missing sentiment columns — run analyze() first."
            )
            return {
                "avg_sentiment": 0.0,
                "median_sentiment": 0.0,
                "std_sentiment": 0.0,
                "distribution": {},
                "distribution_pct": {},
                "most_positive_reviews": [],
                "most_negative_reviews": [],
                "avg_subjectivity": 0.0,
            }

        compound = df["sentiment_compound"]
        stats["avg_sentiment"] = float(compound.mean()) if len(compound) else 0.0
        stats["median_sentiment"] = float(compound.median()) if len(compound) else 0.0
        stats["std_sentiment"] = float(compound.std()) if len(compound) > 1 else 0.0

        # Distribution counts & percentages
        dist = df["sentiment_label"].value_counts().to_dict()
        total = max(len(df), 1)
        stats["distribution"] = dist
        stats["distribution_pct"] = {k: round(v / total * 100, 1) for k, v in dist.items()}

        # Most positive / negative reviews (return as list of dicts)
        text_col = "review_text" if "review_text" in df.columns else None
        if text_col:
            top_pos = df.nlargest(5, "sentiment_compound")
            top_neg = df.nsmallest(5, "sentiment_compound")
            stats["most_positive_reviews"] = [
                {
                    "review_text": str(row.get(text_col, "")),
                    "sentiment_compound": float(row["sentiment_compound"]),
                }
                for _, row in top_pos.iterrows()
            ]
            stats["most_negative_reviews"] = [
                {
                    "review_text": str(row.get(text_col, "")),
                    "sentiment_compound": float(row["sentiment_compound"]),
                }
                for _, row in top_neg.iterrows()
            ]
        else:
            stats["most_positive_reviews"] = []
            stats["most_negative_reviews"] = []

        # Average subjectivity
        if "subjectivity" in df.columns:
            stats["avg_subjectivity"] = float(df["subjectivity"].mean())
        else:
            stats["avg_subjectivity"] = 0.0

        return stats
