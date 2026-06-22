"""
User segment analysis — four consolidated cohorts for business validation.

Overlapping membership is intentional: a low-star Play Store review about
repetitive recommendations may appear in both "Discovery" and "App store" segments.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from config.settings import SENTIMENT_NEGATIVE_THRESHOLD, THEME_TAXONOMY

DISCOVERY_THEMES = [
    "Discovery Frustrations",
    "Algorithm Complaints",
    "Playlist Issues",
    "Content Diversity",
]
PRODUCT_THEMES = ["UI/UX Issues", "Premium vs Free"]


def _is_negative(df: pd.DataFrame) -> pd.Series:
    if "sentiment_label" in df.columns:
        return df["sentiment_label"] == "Negative"
    if "sentiment_compound" in df.columns:
        return df["sentiment_compound"] < SENTIMENT_NEGATIVE_THRESHOLD
    return pd.Series(False, index=df.index)


def _theme_col(theme_name: str) -> str:
    return f"theme_{theme_name}"


def _any_theme(df: pd.DataFrame, theme_names: List[str]) -> pd.DataFrame:
    cols = [_theme_col(name) for name in theme_names if _theme_col(name) in df.columns]
    if not cols:
        return df.iloc[0:0]
    return df[df[cols].any(axis=1)]


class UserSegmentAnalyzer:
    """Build four consolidated user segment profiles from negative feedback."""

    SEGMENT_DEFINITIONS: List[Dict[str, Any]] = [
        {
            "id": "discovery_frustrated",
            "name": "Discovery & recommendation frustrated",
            "description": (
                "Users unhappy with repetitive music, weak recommendations, "
                "playlists (Discover Weekly, Daily Mix), or lack of variety."
            ),
            "filter": lambda df: _any_theme(df, DISCOVERY_THEMES),
        },
        {
            "id": "product_frustrated",
            "name": "App experience & value frustrated",
            "description": (
                "Users reporting crashes, slow performance, confusing UI, "
                "or frustration with free vs premium (ads, pricing, limits)."
            ),
            "filter": lambda df: _any_theme(df, PRODUCT_THEMES),
        },
        {
            "id": "app_store_critics",
            "name": "Low-rating app store users",
            "description": "Play Store or App Store users who left a 1 or 2 star rating.",
            "filter": lambda df: df[
                df["source"].astype(str).str.contains("Play Store|App Store", case=False, na=False)
                & df["rating"].notna()
                & (df["rating"] <= 2)
            ],
        },
        {
            "id": "social_discussants",
            "name": "Social & forum discussants",
            "description": "Users posting on Reddit or the Spotify community forum.",
            "filter": lambda df: df[
                df["source"].astype(str).str.contains("Reddit|Community", case=False, na=False)
            ],
        },
    ]

    PRIMARY_SEGMENT_PRIORITY = [
        "discovery_frustrated",
        "product_frustrated",
        "app_store_critics",
        "social_discussants",
    ]

    def negative_reviews(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df.copy()
        return df[_is_negative(df)].copy()

    def _top_pain_for_subset(self, subset: pd.DataFrame) -> str:
        theme_cols = [c for c in subset.columns if c.startswith("theme_") and c != "theme_count"]
        if not theme_cols or subset.empty:
            return "General dissatisfaction"
        counts = subset[theme_cols].sum().sort_values(ascending=False)
        for col, count in counts.items():
            if count > 0:
                return col.replace("theme_", "")
        return "General dissatisfaction"

    def _top_problems(self, subset: pd.DataFrame, top_n: int = 2) -> List[Dict[str, Any]]:
        theme_cols = [c for c in subset.columns if c.startswith("theme_") and c != "theme_count"]
        if not theme_cols or subset.empty:
            return []
        counts = subset[theme_cols].sum().sort_values(ascending=False)
        problems: List[Dict[str, Any]] = []
        for col, count in counts.items():
            if count <= 0:
                continue
            theme_name = col.replace("theme_", "")
            meta = THEME_TAXONOMY.get(theme_name, {})
            problems.append(
                {
                    "theme": theme_name,
                    "count": int(count),
                    "description": meta.get("description", theme_name),
                    "icon": meta.get("icon", ""),
                }
            )
            if len(problems) >= top_n:
                break
        return problems

    def _sample_quote(self, subset: pd.DataFrame) -> Optional[str]:
        if subset.empty or "review_text" not in subset.columns:
            return None
        text = str(subset.iloc[0]["review_text"]).strip()
        return text[:220] + "…" if len(text) > 220 else text

    def build_profiles(self, df: pd.DataFrame, use_llm: bool = False) -> List[Dict[str, Any]]:  # noqa: ARG002
        if df.empty:
            return []

        negatives = self.negative_reviews(df)
        total_negative = max(len(negatives), 1)
        total_all = max(len(df), 1)
        profiles: List[Dict[str, Any]] = []

        for seg in self.SEGMENT_DEFINITIONS:
            try:
                segment_df = seg["filter"](df)
            except Exception:
                segment_df = df.iloc[0:0]

            segment_negatives = self.negative_reviews(segment_df)
            neg_count = len(segment_negatives)
            if neg_count == 0:
                continue

            profiles.append(
                {
                    "id": seg["id"],
                    "name": seg["name"],
                    "description": seg["description"],
                    "negative_review_count": neg_count,
                    "total_in_segment": len(segment_df),
                    "pct_of_negative": round(neg_count / total_negative * 100, 1),
                    "pct_of_total": round(neg_count / total_all * 100, 1),
                    "top_pain_area": self._top_pain_for_subset(segment_negatives),
                    "top_problems": self._top_problems(segment_negatives),
                    "sample_quote": self._sample_quote(segment_negatives),
                }
            )

        profiles.sort(key=lambda item: item["negative_review_count"], reverse=True)

        profile_by_id = {profile["id"]: profile for profile in profiles}
        ordered: List[Dict[str, Any]] = []
        for seg in self.SEGMENT_DEFINITIONS:
            if seg["id"] in profile_by_id:
                ordered.append(profile_by_id[seg["id"]])
                continue
            ordered.append(
                {
                    "id": seg["id"],
                    "name": seg["name"],
                    "description": seg["description"],
                    "negative_review_count": 0,
                    "total_in_segment": 0,
                    "pct_of_negative": 0.0,
                    "pct_of_total": 0.0,
                    "top_pain_area": "—",
                    "top_problems": [],
                    "sample_quote": None,
                }
            )
        return ordered

    def segment_breakdown_for_subset(
        self, df: pd.DataFrame, subset: pd.DataFrame, top_n: int = 2
    ) -> List[Dict[str, Any]]:
        if subset.empty:
            return []

        breakdown: List[Dict[str, Any]] = []
        for seg in self.SEGMENT_DEFINITIONS:
            try:
                segment_df = seg["filter"](df)
            except Exception:
                continue
            if segment_df.empty:
                continue
            overlap = subset.index.intersection(segment_df.index)
            if len(overlap) == 0:
                continue
            overlap_neg = self.negative_reviews(subset.loc[overlap])
            breakdown.append(
                {
                    "id": seg["id"],
                    "name": seg["name"],
                    "negative_review_count": len(overlap_neg),
                    "pct_of_question_reviews": round(
                        len(overlap_neg) / max(len(subset), 1) * 100, 1
                    ),
                }
            )

        breakdown.sort(key=lambda item: item["negative_review_count"], reverse=True)
        return breakdown[:top_n]

    def pain_theme_summary(self, df: pd.DataFrame, top_n: int = 3) -> List[Dict[str, Any]]:
        negatives = self.negative_reviews(df)
        if negatives.empty:
            return []

        theme_cols = [c for c in negatives.columns if c.startswith("theme_") and c != "theme_count"]
        if not theme_cols:
            return []

        total_negative = max(len(negatives), 1)
        rows: List[Dict[str, Any]] = []
        for col in theme_cols:
            theme_name = col.replace("theme_", "")
            themed = negatives[negatives[col]]
            count = len(themed)
            if count == 0:
                continue
            meta = THEME_TAXONOMY.get(theme_name, {})
            rows.append(
                {
                    "theme": theme_name,
                    "count": count,
                    "pct_of_negative": round(count / total_negative * 100, 1),
                    "description": meta.get("description", theme_name),
                    "icon": meta.get("icon", ""),
                }
            )

        rows.sort(key=lambda item: item["count"], reverse=True)
        return rows[:top_n]

    def assign_primary_segments(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        if result.empty:
            result["primary_user_segment"] = pd.Series(dtype="object", index=result.index)
            return result

        seg_by_id = {seg["id"]: seg for seg in self.SEGMENT_DEFINITIONS}
        primary: List[str] = []

        for idx in result.index:
            row_df = result.loc[[idx]]
            chosen = "General feedback"
            for seg_id in self.PRIMARY_SEGMENT_PRIORITY:
                seg = seg_by_id.get(seg_id)
                if not seg:
                    continue
                try:
                    if not seg["filter"](row_df).empty:
                        chosen = seg["name"]
                        break
                except Exception:
                    continue
            primary.append(chosen)

        result["primary_user_segment"] = primary
        return result

    def headline(self, df: pd.DataFrame, pain_themes: List[Dict[str, Any]], profiles: List[Dict[str, Any]]) -> str:
        """One-line takeaway for dashboard headers."""
        if not pain_themes and not profiles:
            return "Run a scrape to surface user problems from India feedback channels."
        parts: List[str] = []
        if pain_themes:
            top = pain_themes[0]
            parts.append(
                f"The biggest pain area is {top['theme']} ({top['count']} negative mentions)."
            )
        if profiles:
            parts.append(
                f"The most affected group is {profiles[0]['name']} "
                f"({profiles[0]['negative_review_count']} negative reviews)."
            )
        return " ".join(parts)
