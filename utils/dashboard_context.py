"""Shared dashboard context, caching, and display helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from analysis import InsightsEngine, LLMAnalyzer
from config.settings import SENTIMENT_NEGATIVE_THRESHOLD
from utils.tier_inference import (
    TIER_ALL,
    TIER_FREE,
    TIER_LABELS,
    TIER_PREMIUM,
    assign_inferred_tier,
    filter_by_tier,
    tier_counts,
)


def dataset_version(df: pd.DataFrame, tier_filter: str = TIER_ALL) -> str:
    """Lightweight fingerprint so cached summaries refresh when data changes."""
    if df.empty:
        return f"empty:{tier_filter}"
    sources = ",".join(sorted(df["source"].astype(str).unique())) if "source" in df.columns else ""
    return f"{len(df)}:{sources}:{tier_filter}"


def get_insights_engine() -> InsightsEngine:
    if "insights_engine" not in st.session_state:
        st.session_state.insights_engine = InsightsEngine()
    return st.session_state.insights_engine


def prepare_dashboard_df(df: pd.DataFrame, tier_filter: str) -> pd.DataFrame:
    """Ensure tier column exists and apply tier filter."""
    working = assign_inferred_tier(df) if "inferred_user_tier" not in df.columns else df.copy()
    return filter_by_tier(working, tier_filter)


def render_tier_toggle() -> str:
    """Dashboard toggle for All / Free / Premium views. Persists in session."""
    if "dashboard_tier_filter" not in st.session_state:
        st.session_state.dashboard_tier_filter = TIER_ALL

    tier_filter = st.radio(
        "View by inferred user tier",
        options=[TIER_ALL, TIER_FREE, TIER_PREMIUM],
        format_func=lambda key: TIER_LABELS[key],
        horizontal=True,
        key="dashboard_tier_filter",
        help=(
            "Free and Premium are inferred from words in the review (e.g. ads, subscription). "
            "This is not Spotify account data."
        ),
    )
    return tier_filter


def get_exec_summary(df: pd.DataFrame, tier_filter: str = TIER_ALL) -> Dict[str, Any]:
    version = dataset_version(df, tier_filter)
    cache: Dict[str, Dict[str, Any]] = st.session_state.setdefault("exec_summary_by_tier", {})
    if version not in cache:
        engine = get_insights_engine()
        cache[version] = engine.get_executive_summary(df)
        st.session_state.exec_summary_by_tier = cache
    return cache[version]


def get_insights(
    df: pd.DataFrame,
    tier_filter: str = TIER_ALL,
    use_llm: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    version = dataset_version(df, tier_filter)
    llm = LLMAnalyzer()
    llm_enabled = llm.is_available() if use_llm is None else use_llm

    cache: Dict[str, List[Dict[str, Any]]] = st.session_state.setdefault("insights_by_tier", {})
    meta_key = f"{version}:llm={llm_enabled}"
    if meta_key not in cache:
        engine = get_insights_engine()
        with st.spinner("Building insight answers…"):
            cache[meta_key] = engine.answer_strategic_questions(df, use_llm=llm_enabled)
        st.session_state.insights_by_tier = cache

    return cache[meta_key]


def negative_review_count(df: pd.DataFrame) -> int:
    if "sentiment_label" in df.columns:
        return int((df["sentiment_label"] == "Negative").sum())
    if "sentiment_compound" in df.columns:
        return int((df["sentiment_compound"] < SENTIMENT_NEGATIVE_THRESHOLD).sum())
    return 0


def negative_pct(df: pd.DataFrame) -> float:
    total = len(df)
    if total == 0:
        return 0.0
    return round(negative_review_count(df) / total * 100, 1)


def validation_quotes(df: pd.DataFrame, n: int = 5) -> List[Dict[str, Any]]:
    """Negative reviews most useful for stakeholder validation."""
    if df.empty or "review_text" not in df.columns:
        return []

    working = df.copy()
    if "sentiment_label" in working.columns:
        working = working[working["sentiment_label"] == "Negative"]
    elif "sentiment_compound" in working.columns:
        working = working[working["sentiment_compound"] < SENTIMENT_NEGATIVE_THRESHOLD]

    if working.empty:
        return []

    theme_cols = [c for c in working.columns if c.startswith("theme_") and c != "theme_count"]
    if theme_cols:
        working = working.assign(_theme_hits=working[theme_cols].sum(axis=1))
        working = working.sort_values("_theme_hits", ascending=False)
    elif "sentiment_compound" in working.columns:
        working = working.sort_values("sentiment_compound")

    quotes: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for _, row in working.iterrows():
        text = str(row.get("review_text", "")).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        display = text[:280] + ("…" if len(text) > 280 else "")
        quotes.append(
            {
                "text": display,
                "source": str(row.get("source", "unknown")),
                "segment": str(row.get("primary_user_segment", "General feedback")),
                "tier": str(row.get("inferred_user_tier", "unclassified")),
                "sentiment": float(row.get("sentiment_compound", 0.0)),
            }
        )
        if len(quotes) >= n:
            break
    return quotes


def clear_dashboard_cache() -> None:
    for key in (
        "exec_summary",
        "exec_summary_version",
        "exec_summary_by_tier",
        "insights_by_tier",
        "insights_version",
        "insights_llm_enabled",
        "insights_engine",
    ):
        st.session_state.pop(key, None)
