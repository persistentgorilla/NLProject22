"""Infer Free vs Premium user tier from review text (not account data)."""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from config.settings import FREE_TIER_KEYWORDS, PREMIUM_TIER_KEYWORDS

TIER_ALL = "all"
TIER_FREE = "free"
TIER_PREMIUM = "premium"
TIER_UNCLASSIFIED = "unclassified"

TIER_LABELS: Dict[str, str] = {
    TIER_ALL: "All users",
    TIER_FREE: "Free (inferred)",
    TIER_PREMIUM: "Premium (inferred)",
}


def _count_keyword_hits(text: str, keywords: List[str]) -> int:
    lowered = text.lower()
    hits = 0
    for keyword in keywords:
        if keyword in lowered:
            hits += 1
    return hits


def infer_tier_from_text(text: Any) -> str:
    """Return ``free``, ``premium``, or ``unclassified`` for a review."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return TIER_UNCLASSIFIED
    cleaned = str(text).strip()
    if not cleaned:
        return TIER_UNCLASSIFIED

    free_hits = _count_keyword_hits(cleaned, FREE_TIER_KEYWORDS)
    premium_hits = _count_keyword_hits(cleaned, PREMIUM_TIER_KEYWORDS)

    if free_hits == 0 and premium_hits == 0:
        return TIER_UNCLASSIFIED
    if free_hits > premium_hits:
        return TIER_FREE
    if premium_hits > free_hits:
        return TIER_PREMIUM
    return TIER_UNCLASSIFIED


def assign_inferred_tier(df: pd.DataFrame) -> pd.DataFrame:
    """Add ``inferred_user_tier`` column to the dataframe."""
    result = df.copy()
    if result.empty or "review_text" not in result.columns:
        result["inferred_user_tier"] = pd.Series(dtype="object", index=result.index)
        return result
    result["inferred_user_tier"] = result["review_text"].apply(infer_tier_from_text)
    return result


def filter_by_tier(df: pd.DataFrame, tier_filter: str) -> pd.DataFrame:
    """Filter dataframe by tier toggle selection."""
    if tier_filter == TIER_ALL or tier_filter not in (TIER_FREE, TIER_PREMIUM):
        return df.copy()
    if "inferred_user_tier" not in df.columns:
        df = assign_inferred_tier(df)
    return df[df["inferred_user_tier"] == tier_filter].copy()


def tier_counts(df: pd.DataFrame) -> Dict[str, int]:
    """Count reviews per inferred tier."""
    if df.empty:
        return {TIER_FREE: 0, TIER_PREMIUM: 0, TIER_UNCLASSIFIED: 0}
    working = assign_inferred_tier(df) if "inferred_user_tier" not in df.columns else df
    counts = working["inferred_user_tier"].value_counts().to_dict()
    return {
        TIER_FREE: int(counts.get(TIER_FREE, 0)),
        TIER_PREMIUM: int(counts.get(TIER_PREMIUM, 0)),
        TIER_UNCLASSIFIED: int(counts.get(TIER_UNCLASSIFIED, 0)),
    }
