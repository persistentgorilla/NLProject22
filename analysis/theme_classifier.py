"""
Spotify Review Discovery Engine — Theme Classification Module

Rule-based multi-label classifier that matches review text against the
keyword lists defined in ``config.settings.THEME_TAXONOMY``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from config.settings import THEME_TAXONOMY

logger = logging.getLogger(__name__)


class ThemeClassifier:
    """Classify reviews into predefined thematic categories.

    The classifier is *rule-based*: for each review it checks whether
    any keyword from each theme's list appears in the lowercased text.

    Attributes
    ----------
    taxonomy : dict
        The full THEME_TAXONOMY from config (theme → keywords / meta).
    theme_names : list[str]
        Ordered list of theme names.
    """

    def __init__(self) -> None:
        """Load the theme taxonomy from config."""
        self.taxonomy: Dict[str, Dict[str, Any]] = THEME_TAXONOMY
        self.theme_names: List[str] = list(self.taxonomy.keys())
        logger.info(
            "ThemeClassifier initialised with %d themes: %s",
            len(self.theme_names),
            ", ".join(self.theme_names),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _match_theme(self, text: str, keywords: List[str]) -> bool:
        """Return ``True`` if any keyword appears in *text*.

        Parameters
        ----------
        text : str
            Lowercased review text.
        keywords : list[str]
            Keyword phrases for a single theme.

        Returns
        -------
        bool
        """
        for kw in keywords:
            if kw in text:
                return True
        return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        """Enrich *df* with theme classification columns.

        Parameters
        ----------
        df : pd.DataFrame
            Must contain a ``review_text`` column.

        Returns
        -------
        pd.DataFrame
            Same DataFrame with:
            * One boolean column per theme: ``theme_<ThemeName>``
            * ``themes`` — list[str] of matched theme names
            * ``theme_count`` — int, number of matched themes

        Raises
        ------
        ValueError
            If ``review_text`` column is missing.
        """
        if "review_text" not in df.columns:
            raise ValueError("DataFrame must contain a 'review_text' column.")

        result = df.copy()
        n_rows = len(result)
        logger.info("Starting theme classification on %d reviews …", n_rows)

        # Lowercased text series; NaN / empty → empty string
        lower_text: pd.Series = (
            result["review_text"]
            .fillna("")
            .astype(str)
            .str.lower()
        )

        # For each theme create a boolean column
        for theme_name, meta in self.taxonomy.items():
            col = f"theme_{theme_name}"
            keywords: List[str] = [kw.lower() for kw in meta["keywords"]]
            result[col] = lower_text.apply(
                lambda txt, kws=keywords: self._match_theme(txt, kws)
            )

        # Aggregate columns
        theme_cols = [f"theme_{tn}" for tn in self.theme_names]
        result["themes"] = result[theme_cols].apply(
            lambda row: [
                tn
                for tn, col in zip(self.theme_names, theme_cols)
                if row[col]
            ],
            axis=1,
        )
        result["theme_count"] = result["themes"].apply(len)

        # Logging summary
        for tn in self.theme_names:
            cnt = result[f"theme_{tn}"].sum()
            logger.info("  • %-25s  matched %4d reviews", tn, cnt)
        logger.info("Theme classification complete.")

        return result

    # ------------------------------------------------------------------
    # Distribution & co-occurrence helpers
    # ------------------------------------------------------------------

    def get_theme_distribution(self, df: pd.DataFrame) -> Dict[str, int]:
        """Count how many reviews match each theme, sorted descending.

        Parameters
        ----------
        df : pd.DataFrame
            A DataFrame already processed by :meth:`analyze`.

        Returns
        -------
        dict[str, int]
            ``{theme_name: count}`` ordered by count descending.
        """
        dist: Dict[str, int] = {}
        for tn in self.theme_names:
            col = f"theme_{tn}"
            if col in df.columns:
                dist[tn] = int(df[col].sum())
            else:
                dist[tn] = 0
        # Sort descending
        dist = dict(sorted(dist.items(), key=lambda kv: kv[1], reverse=True))
        return dist

    def get_theme_cooccurrence(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build a theme × theme co-occurrence matrix.

        Parameters
        ----------
        df : pd.DataFrame
            A DataFrame already processed by :meth:`analyze`.

        Returns
        -------
        pd.DataFrame
            Square DataFrame of shape ``(n_themes, n_themes)`` where
            each cell ``(i, j)`` counts how many reviews matched both
            theme *i* and theme *j*.
        """
        theme_cols = [f"theme_{tn}" for tn in self.theme_names]
        available = [c for c in theme_cols if c in df.columns]

        if not available:
            logger.warning(
                "No theme columns found — run analyze() first."
            )
            return pd.DataFrame()

        bool_matrix = df[available].astype(int)
        cooccurrence = bool_matrix.T.dot(bool_matrix)

        # Rename axes back to clean theme names
        clean_names = [c.replace("theme_", "") for c in available]
        cooccurrence.index = clean_names
        cooccurrence.columns = clean_names

        return cooccurrence
