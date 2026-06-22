"""Review text quality filters for the scraping pipeline."""

from __future__ import annotations

import re
from typing import Any, Dict, Tuple

import pandas as pd

from config.settings import MIN_REVIEW_WORD_COUNT

_EMOJI_RE = re.compile(
    "["
    "\U0001F1E0-\U0001FAFF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F900-\U0001F9FF"
    "\U00002600-\U000026FF"
    "\U0000FE00-\U0000FE0F"
    "\U0000200D"
    "]+",
    flags=re.UNICODE,
)
_WORD_RE = re.compile(r"\b[\w']+\b", flags=re.UNICODE)


def contains_emoji(text: str) -> bool:
    """Return True if the text contains emoji characters."""
    return bool(_EMOJI_RE.search(text))


def count_words(text: str) -> int:
    """Count words in review text."""
    return len(_WORD_RE.findall(text.strip()))


def is_valid_review_text(text: Any, min_words: int = MIN_REVIEW_WORD_COUNT) -> bool:
    """Check whether review text passes emoji and minimum word rules."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return False
    cleaned = str(text).strip()
    if not cleaned:
        return False
    if contains_emoji(cleaned):
        return False
    return count_words(cleaned) >= min_words


def filter_reviews_dataframe(
    df: pd.DataFrame,
    min_words: int = MIN_REVIEW_WORD_COUNT,
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Remove reviews containing emojis or fewer than ``min_words`` words."""
    stats = {
        "input_total": len(df),
        "removed_emoji": 0,
        "removed_short": 0,
        "removed_total": 0,
        "kept_total": 0,
    }
    if df.empty or "review_text" not in df.columns:
        stats["kept_total"] = len(df)
        return df.copy(), stats

    working = df.copy()
    texts = working["review_text"].fillna("").astype(str)
    emoji_mask = texts.apply(contains_emoji)
    short_mask = texts.apply(lambda value: count_words(value) < min_words)

    stats["removed_emoji"] = int(emoji_mask.sum())
    stats["removed_short"] = int((~emoji_mask & short_mask).sum())
    stats["removed_total"] = int((emoji_mask | short_mask).sum())

    filtered = working[~(emoji_mask | short_mask)].reset_index(drop=True)
    stats["kept_total"] = len(filtered)
    return filtered, stats
