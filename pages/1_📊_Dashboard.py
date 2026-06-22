"""
Spotify Review Discovery Engine - Dashboard Page
==================================================
Narrative-first view: answers the 6 discovery questions from user feedback.
"""

import sys
import streamlit as st
import pandas as pd

sys.path.insert(0, ".")

from visualizations import ChartBuilder, WordCloudGenerator
from utils.data_io import restore_analyzed_dataframe, export_analyzed_dataframe_to_excel
from utils.html import escape_html
from utils.session_reset import reset_app_state
from utils.dashboard_context import (
    get_exec_summary,
    validation_quotes,
    negative_pct,
    prepare_dashboard_df,
    render_tier_toggle,
)
from utils.tier_inference import TIER_ALL, TIER_LABELS, tier_counts

# ============================================================
# Page Config
# ============================================================
st.set_page_config(
    page_title="Dashboard - Spotify Review Engine",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp {
        background-color: #121212;
        color: #FFFFFF;
    }
    div[data-testid="stMetricValue"] {
        color: #1DB954 !important;
        font-weight: bold;
    }
    div[data-testid="metric-container"] {
        background-color: #1E1E1E;
        border: 1px solid #282828;
        padding: 15px;
        border-radius: 10px;
    }
    .spotify-card {
        background-color: #1E1E1E;
        border: 1px solid #282828;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 15px;
    }
    .answer-card {
        background-color: #1A1A1A;
        border-left: 4px solid #1DB954;
        padding: 14px 18px;
        border-radius: 0 8px 8px 0;
        margin-bottom: 12px;
        line-height: 1.6;
    }
    .repeat-card {
        background-color: #1A1010;
        border: 1px solid #E91429;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 15px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Ensure core session keys exist before reset handling
for _key, _default in (
    ("raw_data", pd.DataFrame()),
    ("analyzed_data", pd.DataFrame()),
    ("topics", []),
    ("insights", []),
):
    if _key not in st.session_state:
        st.session_state[_key] = _default

# ============================================================
# Header
# ============================================================
title_col, reset_col, export_col = st.columns([4, 1, 1])
with title_col:
    st.title("What Spotify users in India are saying about music discovery")
    st.markdown(
        "Feedback from the Play Store, App Store, Reddit, and community forums — "
        "analyzed to understand why users aren't finding new music and what keeps them "
        "replaying the same songs."
    )
with reset_col:
    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
    if st.button(
        "Reset",
        use_container_width=True,
        help="Clears loaded data, analysis results, and local cache so you can start a fresh run.",
    ):
        reset_app_state()
        st.rerun()

has_data = (
    "analyzed_data" in st.session_state
    and not st.session_state.analyzed_data.empty
)

# ============================================================
# Data Validation
# ============================================================
if not has_data:
    st.warning("No data yet. Run a scrape from the home page, or load a saved export.")
    st.stop()

df_full = restore_analyzed_dataframe(st.session_state.analyzed_data.copy())
topics = st.session_state.get("topics", [])

tier_filter = render_tier_toggle()
counts = tier_counts(df_full)
st.caption(
    f"Inferred from review text — not Spotify account data: "
    f"{counts['free']:,} likely Free users · {counts['premium']:,} likely Premium · "
    f"{counts['unclassified']:,} unclear"
)

df = prepare_dashboard_df(df_full, tier_filter)
if tier_filter != TIER_ALL and df.empty:
    st.warning(
        f"No reviews matched **{TIER_LABELS[tier_filter]}** in this run. "
        "Switch to **All users** or scrape more feedback that mentions free/premium."
    )
    st.stop()

view_label = TIER_LABELS[tier_filter]
exec_summary = get_exec_summary(df, tier_filter)
segment_profiles = exec_summary.get("segment_profiles", [])
pain_themes = exec_summary.get("pain_themes", [])
neg_count = exec_summary.get("negative_review_count", 0)
top_pain = pain_themes[0]["theme"] if pain_themes else "None identified"

with export_col:
    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
    st.download_button(
        label="Export Excel",
        data=export_analyzed_dataframe_to_excel(df),
        file_name="spotify_analyzed_reviews.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        help="Download the full dataset for this run.",
    )

st.markdown("---")

# ============================================================
# KPI Metrics
# ============================================================
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Reviews analyzed", f"{len(df):,}", help=f"Filtered to: {view_label}")
with c2:
    st.metric("Negative reviews", f"{neg_count:,}", help="The primary signal for where users are in pain.")
with c3:
    st.metric("Share that is negative", f"{negative_pct(df):.1f}%")
with c4:
    st.metric("Biggest complaint", top_pain)

headline = exec_summary.get("headline", "")
if headline:
    st.info(headline)

# ============================================================
# The short version — 6 questions answered from the data
# ============================================================
st.markdown("---")
st.markdown("### What the data is saying")
st.caption(
    "Six questions about music discovery, answered directly from user feedback. "
    "Each answer is grounded in the volume of negative reviews — not assumptions."
)

# Build answers from exec_summary data
_pain_map = {p["theme"]: p for p in pain_themes}
_seg_map = {s["id"]: s for s in segment_profiles if s["negative_review_count"] > 0}

# Per-theme counts from df columns
def _theme_count(theme_name: str) -> int:
    col = f"theme_{theme_name}"
    if col not in df.columns:
        return 0
    neg = df[df.get("sentiment_label", pd.Series(dtype=str)) == "Negative"] if "sentiment_label" in df.columns else df
    return int(neg[col].astype(bool).sum())

_discovery_count = _theme_count("Discovery Frustrations")
_algorithm_count = _theme_count("Algorithm Complaints")
_playlist_count = _theme_count("Playlist Issues")
_diversity_count = _theme_count("Content Diversity")
_feature_count = _theme_count("Feature Requests")
_listening_count = _theme_count("Listening Behavior")
_repeat_count = _discovery_count + _algorithm_count  # repetitive listening signal

_top_seg = max(segment_profiles, key=lambda s: s["negative_review_count"], default={}) if segment_profiles else {}

_six_answers = [
    {
        "q": "Why do users struggle to discover new music?",
        "a": (
            f"The algorithm keeps serving what users already know. "
            f"{_discovery_count:,} negative reviews mention feeling stuck in the same rotation — "
            "users describe it as Spotify 'not taking risks' on their behalf."
        ) if _discovery_count > 0 else (
            "Users report the app defaults to familiar artists and genres, "
            "leaving them unable to find music they haven't heard before."
        ),
    },
    {
        "q": "What frustrates them most about recommendations?",
        "a": (
            f"{_algorithm_count:,} reviews name the recommendation algorithm directly — "
            "Discover Weekly feels predictable, Daily Mix recycles the same tracks, "
            "and the 'Radio' feature rarely surfaces anything genuinely new."
        ) if _algorithm_count > 0 else (
            "Users find recommendation features — Discover Weekly, Radio, Daily Mix — "
            "repetitive and too safe, rarely introducing music outside their comfort zone."
        ),
    },
    {
        "q": "What are users actually trying to do when they listen?",
        "a": (
            f"{_listening_count:,} reviews describe listening with a purpose — "
            "working, commuting, unwinding, exploring a new genre. "
            "They want music that fits the moment, not just their listening history."
        ) if _listening_count > 0 else (
            "Users want listening that matches their context — a study session, "
            "a workout, a mood — not a loop of songs they already know by heart."
        ),
    },
    {
        "q": "What causes them to keep replaying the same content?",
        "a": (
            f"The discovery features aren't surfacing enough variety. "
            f"Across {_repeat_count:,} negative reviews, users describe falling back on "
            "the same playlists not by choice, but because the alternatives feel worse."
        ) if _repeat_count > 0 else (
            "Users replay familiar content as a default — not because they prefer it, "
            "but because they can't find anything better through the app's discovery tools."
        ),
    },
    {
        "q": "Which users feel this the most?",
        "a": (
            f"The loudest group is **{_top_seg.get('name', 'unknown')}** — "
            f"{_top_seg.get('negative_review_count', 0):,} negative reviews. "
            f"Their top complaint: {_top_seg.get('top_pain_area', 'discovery')}."
        ) if _top_seg else (
            "Users who engage most actively with discovery features — "
            "playlist listeners and app store reviewers — report the most frustration."
        ),
    },
    {
        "q": "What do they wish Spotify would do instead?",
        "a": (
            f"{_feature_count + _diversity_count:,} reviews point to specific gaps — "
            "better genre exploration, smarter context awareness, and more control "
            "over what the algorithm considers 'new' for them."
        ) if (_feature_count + _diversity_count) > 0 else (
            "Users consistently ask for more variety, smarter context-matching, "
            "and tools that help them deliberately explore rather than passively replay."
        ),
    },
]

for i, item in enumerate(_six_answers, 1):
    st.markdown(
        f"""
        <div class="answer-card">
            <p style="font-size: 12px; color: #888; margin: 0 0 4px 0; text-transform: uppercase; letter-spacing: 0.5px;">Q{i}</p>
            <p style="font-weight: bold; margin: 0 0 6px 0; font-size: 14px;">{escape_html(item['q'])}</p>
            <p style="margin: 0; color: #D1D1D1; font-size: 14px; line-height: 1.6;">{escape_html(item['a'])}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# Section 1: Why users can't discover (Q1 + Q2)
# ============================================================
st.markdown("---")
st.markdown("### Where recommendations are breaking down")
st.caption(
    "These are the specific problems users name most often when they complain about "
    "music discovery. Ranked by volume of negative mentions."
)

if pain_themes:
    pain_cols = st.columns(len(pain_themes))
    for idx, pain in enumerate(pain_themes):
        with pain_cols[idx]:
            st.markdown(
                f"""
                <div class="spotify-card" style="text-align: center;">
                    <h4 style="margin: 0; color: #E91429; font-size: 14px;">{escape_html(pain.get('icon', ''))} {escape_html(pain['theme'])}</h4>
                    <p style="font-size: 13px; color: #888; margin: 6px 0;">{escape_html(pain.get('description', ''))}</p>
                    <p style="font-size: 28px; font-weight: bold; margin: 8px 0 2px 0;">{pain['count']:,}</p>
                    <p style="font-size: 12px; color: #B3B3B3; margin: 0;">negative mentions · {pain['pct_of_negative']:.0f}% of all negative feedback</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
else:
    st.info("No themed complaints found. Try adding more Reddit or community forum data.")

# ============================================================
# Section 2: Repetitive listening (Q4)
# ============================================================
st.markdown("---")
st.markdown("### What this leads to: users stuck on repeat")
st.caption(
    "The discovery gap has a behavioral outcome — users default to the familiar "
    "because the app doesn't give them a better path to something new."
)

_repeat_themes = [
    ("theme_Discovery Frustrations", "Stuck in the same rotation",
     "Users explicitly say they hear the same songs, same artists, over and over — "
     "not because they want to, but because nothing new comes up."),
    ("theme_Algorithm Complaints", "The algorithm plays it safe",
     "Discover Weekly, Daily Mix, and Radio features get flagged for being too predictable. "
     "Users feel the app is optimizing for comfort, not exploration."),
    ("theme_Playlist Issues", "Playlists don't refresh",
     "Curated and auto-generated playlists feel static. Users check back and find "
     "the same songs week after week."),
]

_repeat_data = []
for col, label, desc in _repeat_themes:
    if col in df.columns:
        count = int(df[col].astype(bool).sum())
        neg_in_theme = 0
        if "sentiment_label" in df.columns:
            neg_in_theme = int((df[col].astype(bool) & (df["sentiment_label"] == "Negative")).sum())
        if count > 0:
            _repeat_data.append({"label": label, "count": count, "neg": neg_in_theme, "desc": desc})

if _repeat_data:
    _r_cols = st.columns(len(_repeat_data))
    for _i, _r in enumerate(_repeat_data):
        with _r_cols[_i]:
            st.markdown(
                f"""
                <div class="repeat-card">
                    <h4 style="margin: 0 0 6px 0; color: #FF6B6B; font-size: 14px;">{escape_html(_r['label'])}</h4>
                    <p style="font-size: 12px; color: #B3B3B3; margin: 0 0 10px 0;">{escape_html(_r['desc'])}</p>
                    <p style="font-size: 26px; font-weight: bold; margin: 0;">{_r['count']:,}
                    <span style="font-size: 12px; color: #B3B3B3; font-weight: normal;"> total mentions</span></p>
                    {f'<p style="font-size: 12px; color: #E91429; margin: 4px 0 0 0;">{_r["neg"]:,} in negative reviews</p>' if _r["neg"] > 0 else ''}
                </div>
                """,
                unsafe_allow_html=True,
            )
else:
    st.info("Not enough data to quantify the repetitive listening pattern. Add Reddit discussions for richer signals.")

# ============================================================
# Section 3: Who feels it most (Q5)
# ============================================================
st.markdown("---")
st.markdown("### Who is feeling it")
st.caption(
    "Four user groups defined by where they post and what they talk about. "
    "One review can belong to more than one group — so percentages add up to more than 100%."
)

seg_cols = st.columns(4)
for idx, profile in enumerate(segment_profiles[:4]):
    with seg_cols[idx]:
        count = profile["negative_review_count"]
        dim = "opacity: 0.50;" if count == 0 else ""
        st.markdown(
            f"""
            <div class="spotify-card" style="{dim}">
                <h4 style="margin: 0 0 6px 0; color: #1DB954; font-size: 14px;">{escape_html(profile['name'])}</h4>
                <p style="font-size: 12px; color: #B3B3B3; margin: 0 0 8px 0;">{escape_html(profile['description'])}</p>
                <p style="font-size: 26px; font-weight: bold; margin: 0;">{count:,}
                <span style="font-size: 12px; color: #B3B3B3; font-weight: normal;"> negative reviews</span></p>
                <p style="font-size: 12px; color: #B3B3B3; margin: 6px 0 0 0;">
                    {profile['pct_of_negative']:.0f}% of all negative feedback
                </p>
                <p style="font-size: 12px; margin: 8px 0 0 0;">
                    Their main frustration: <b>{escape_html(profile['top_pain_area'])}</b>
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ============================================================
# Section 4: What they actually want (Q3 + Q6)
# ============================================================
st.markdown("---")
st.markdown("### What users want instead")
st.caption(
    "These aren't just complaints — users are describing what they wish the product did. "
    "Each category below represents a gap between what exists and what they need."
)

_want_themes = [
    ("theme_Listening Behavior", "Music that fits the moment",
     "Users listen with a purpose — working, commuting, a specific mood or energy level. "
     "They want Spotify to understand the context, not just replay their history."),
    ("theme_Content Diversity", "More variety, less echo chamber",
     "Users who feel the app only plays what they already know. "
     "They want to be genuinely surprised — not served a safer version of the familiar."),
    ("theme_Feature Requests", "Specific things they're asking for",
     "Better genre controls, smarter autoplay, the ability to tell the app what 'new' means for them. "
     "These are product gaps users have already articulated."),
]
_want_data = []
for col, label, desc in _want_themes:
    if col in df.columns:
        count = int(df[col].astype(bool).sum())
        if count > 0:
            _want_data.append({"label": label, "count": count, "desc": desc})

if _want_data:
    _w_cols = st.columns(len(_want_data))
    for _i, _w in enumerate(_want_data):
        with _w_cols[_i]:
            st.markdown(
                f"""
                <div class="spotify-card">
                    <h4 style="margin: 0 0 6px 0; color: #1DB954; font-size: 14px;">{escape_html(_w['label'])}</h4>
                    <p style="font-size: 12px; color: #B3B3B3; margin: 0 0 10px 0;">{escape_html(_w['desc'])}</p>
                    <p style="font-size: 26px; font-weight: bold; margin: 0;">{_w['count']:,}
                    <span style="font-size: 12px; color: #B3B3B3; font-weight: normal;"> mentions</span></p>
                </div>
                """,
                unsafe_allow_html=True,
            )
else:
    st.info("Add Reddit and community forum data to surface what users are asking for.")

# ============================================================
# Section 5: Real user voices
# ============================================================
st.markdown("---")
st.markdown("### In their own words")
st.caption(
    "Verbatim from the reviews — selected because they have multiple pain signals, "
    "not because they're the most extreme."
)
quotes = validation_quotes(df, n=5)
if quotes:
    for quote in quotes:
        st.markdown(
            f"""
            <div class="spotify-card">
                <p style="margin: 0 0 10px 0; line-height: 1.6; font-style: italic; font-size: 14px;">"{escape_html(quote['text'])}"</p>
                <p style="margin: 0; font-size: 12px; color: #B3B3B3;">
                    {escape_html(quote['source'])} &nbsp;·&nbsp; {escape_html(quote['segment'])}
                    {f" &nbsp;·&nbsp; {escape_html(quote['tier'])}" if quote.get('tier') not in ('unclassified', None) else ""}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
else:
    st.info("No negative quotes found in this run.")

# ============================================================
# Section 6: The group most worth exploring (bridges to Part 2)
# ============================================================
st.markdown("---")
st.markdown("### The group most worth understanding better")
st.caption(
    "Based on volume of negative feedback, clarity of pain signal, and distinctiveness of the complaint pattern."
)

_active_segments = [p for p in segment_profiles if p["negative_review_count"] > 0]
if _active_segments:
    _top = max(_active_segments, key=lambda s: s["negative_review_count"])
    st.markdown(
        f"""
        <div style="background: #142818; border: 1px solid #1DB954; border-radius: 10px; padding: 20px; margin-bottom: 16px;">
            <p style="color: #1DB954; font-size: 11px; font-weight: bold; margin: 0 0 4px 0; text-transform: uppercase; letter-spacing: 0.5px;">Highest signal group</p>
            <h3 style="margin: 0 0 8px 0; font-size: 18px;">{escape_html(_top['name'])}</h3>
            <p style="color: #B3B3B3; font-size: 13px; margin: 0 0 12px 0;">{escape_html(_top['description'])}</p>
            <p style="margin: 0 0 8px 0; font-size: 14px;">
                <b>{_top['negative_review_count']:,} negative reviews</b> &nbsp;·&nbsp;
                {_top['pct_of_negative']:.0f}% of all negative feedback &nbsp;·&nbsp;
                Main frustration: <b>{escape_html(_top['top_pain_area'])}</b>
            </p>
            {"".join(f'<div style="background:#282828; border-radius:6px; padding:10px 14px; margin-top:10px; font-size:13px; font-style:italic; color:#D1D1D1;">&ldquo;{escape_html(_top[\"sample_quote\"])}&rdquo;</div>' if _top.get("sample_quote") else [])}
        </div>
        """,
        unsafe_allow_html=True,
    )
    if len(_active_segments) > 1:
        _others = [s for s in _active_segments if s["id"] != _top["id"]]
        if _others:
            _runner_up = _others[0]
            st.caption(
                f"Also worth exploring: **{_runner_up['name']}** "
                f"({_runner_up['negative_review_count']:,} negative reviews, "
                f"main issue: {_runner_up['top_pain_area']})."
            )
else:
    st.info("Scrape more feedback to identify which group has the clearest pain signal.")

st.page_link("pages/4_💡_Strategic_Insights.py", label="See the full analysis behind each question →")

# ============================================================
# Supporting charts (optional, collapsed)
# ============================================================
st.markdown("---")
with st.expander("Charts and supporting detail", expanded=False):
    charts = ChartBuilder()
    wordclouds = WordCloudGenerator()

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(charts.sentiment_distribution(df), use_container_width=True)
    with col2:
        st.plotly_chart(charts.rating_distribution(df), use_container_width=True)

    col3, col4 = st.columns([3, 2])
    with col3:
        st.plotly_chart(charts.theme_prevalence(df, negative_only=True), use_container_width=True)
    with col4:
        st.plotly_chart(charts.source_comparison(df), use_container_width=True)

    col5, col6 = st.columns(2)
    with col5:
        st.markdown("**Most common words in the feedback**")
        all_text = " ".join(df["review_text"].dropna().astype(str).tolist())
        fig_wc = wordclouds.generate(all_text, "Most common words in feedback")
        st.pyplot(fig_wc)
    with col6:
        st.plotly_chart(charts.rating_sentiment_scatter(df), use_container_width=True)

    st.markdown("**Discussion clusters (what topics come up together)**")
    st.caption("Groups of reviews that share similar vocabulary — useful for spotting compound pain points.")
    if topics:
        st.plotly_chart(charts.topic_visualization(topics), use_container_width=True)
    else:
        st.caption("Not enough data to cluster into topics.")
