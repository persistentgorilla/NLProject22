"""
Spotify Review Discovery Engine - Dashboard Page
==================================================
Presents overall KPIs, sentiment distributions, ratings, themes, and topic modeling.
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

# Inject dark mode styling
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
# Main Page Layout
# ============================================================
title_col, reset_col, export_col = st.columns([4, 1, 1])
with title_col:
    st.title("What Spotify users in India are saying")
    st.markdown(
        "Aggregated feedback from the Play Store, App Store, Reddit, and community forums — "
        "analyzed to understand **why users aren't discovering new music** and **what keeps them stuck in the same listening loops**."
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
    f"Inferred from review text (not account data): "
    f"{counts['free']:,} Free · {counts['premium']:,} Premium · "
    f"{counts['unclassified']:,} unclassified"
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

# 1. KPI Metrics — problem-focused
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Reviews in view", f"{len(df):,}", help=f"Filtered to: {view_label}")
with c2:
    st.metric("Negative reviews", f"{neg_count:,}", help="Primary signal for user problems.")
with c3:
    st.metric("% negative", f"{negative_pct(df):.1f}%")
with c4:
    st.metric("Top pain area", top_pain)

headline = exec_summary.get("headline", "")
if headline:
    st.info(headline)

st.markdown("### 1. Who is feeling it")
st.caption(
    "Four user groups, defined by where they post and what they complain about. "
    "Percentages can add up to more than 100% — a single review can belong to more than one group."
)

seg_cols = st.columns(4)
for idx, profile in enumerate(segment_profiles[:4]):
    with seg_cols[idx]:
        count = profile["negative_review_count"]
        dim = "opacity: 0.55;" if count == 0 else ""
        st.markdown(
            f"""
            <div class="spotify-card" style="{dim}">
                <h4 style="margin: 0 0 6px 0; color: #1DB954; font-size: 14px;">{escape_html(profile['name'])}</h4>
                <p style="font-size: 12px; color: #B3B3B3; margin: 0 0 8px 0;">{escape_html(profile['description'])}</p>
                <p style="font-size: 22px; font-weight: bold; margin: 0;">{count:,}
                <span style="font-size: 12px; color: #B3B3B3; font-weight: normal;"> negatives</span></p>
                <p style="font-size: 12px; color: #B3B3B3; margin: 6px 0 0 0;">
                    {profile['pct_of_negative']:.0f}% of all negative feedback
                </p>
                <p style="font-size: 12px; margin: 8px 0 0 0;">
                    Top issue: <b>{escape_html(profile['top_pain_area'])}</b>
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("### 2. The biggest complaints")
st.caption("Recurring problems across all sources, ranked by how often they appear in negative reviews.")
if pain_themes:
    pain_cols = st.columns(len(pain_themes))
    for idx, pain in enumerate(pain_themes):
        with pain_cols[idx]:
            st.markdown(
                f"""
                <div class="spotify-card" style="text-align: center;">
                    <h4 style="margin: 0; color: #E91429; font-size: 14px;">{escape_html(pain.get('icon', ''))} {escape_html(pain['theme'])}</h4>
                    <p style="font-size: 13px; color: #888; margin: 6px 0;">{escape_html(pain.get('description', ''))}</p>
                    <p style="font-size: 24px; font-weight: bold; margin: 8px 0 4px 0;">{pain['count']:,}</p>
                    <p style="font-size: 12px; color: #B3B3B3; margin: 0;">{pain['pct_of_negative']:.0f}% of negative reviews</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
else:
    st.warning("No themed pain areas found in negative reviews. Try increasing review volume or adding Reddit.")

st.markdown("### 3. What users want instead")
st.caption(
    "These aren't just complaints — users are telling us what they wish the product did. "
    "Each group below maps to a category of unmet need."
)

_want_themes = [
    ("theme_Feature Requests", "Explicit feature requests", "Users asking for something specific — better genre filters, smarter autoplay, controls they can't find today."),
    ("theme_Content Diversity", "More variety in recommendations", "Users who feel the app only plays what they already know — they want to be surprised, not just served the familiar."),
    ("theme_Listening Behavior", "Context-aware listening", "Users describe moods, activities, and energy levels. They want Spotify to understand the moment, not just their history."),
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
                    <p style="font-size: 22px; font-weight: bold; margin: 0;">{_w['count']:,}
                    <span style="font-size: 12px; color: #B3B3B3; font-weight: normal;"> mentions</span></p>
                </div>
                """,
                unsafe_allow_html=True,
            )
else:
    st.info("Scrape more Reddit or community data to surface unmet needs.")

st.markdown("### 4. Real user voices")
st.caption("Verbatim quotes from the feedback. These are useful for framing interview questions — not to be read as representative facts.")
quotes = validation_quotes(df, n=5)
if quotes:
    for quote in quotes:
        st.markdown(
            f"""
            <div class="spotify-card">
                <p style="margin: 0 0 8px 0; line-height: 1.5; font-style: italic;">"{escape_html(quote['text'])}"</p>
                <p style="margin: 0; font-size: 12px; color: #B3B3B3;">
                    {escape_html(quote['source'])} · {escape_html(quote['segment'])} · {escape_html(quote.get('tier', '—'))}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
else:
    st.info("No negative quotes available in this run.")

st.markdown("### 5. Who to speak with next")
st.caption(
    "This is the segment most worth interviewing — highest volume of negative feedback and the clearest pain signal. "
    "Use the quote above as a conversation starter."
)
_active_segments = [p for p in segment_profiles if p["negative_review_count"] > 0]
if _active_segments:
    _top = max(_active_segments, key=lambda s: s["negative_review_count"])
    st.markdown(
        f"""
        <div style="background: #142818; border: 1px solid #1DB954; border-radius: 10px; padding: 20px; margin-bottom: 16px;">
            <p style="color: #1DB954; font-size: 12px; font-weight: bold; margin: 0 0 4px 0; text-transform: uppercase; letter-spacing: 0.5px;">Recommended segment for interviews</p>
            <h3 style="margin: 0 0 8px 0; font-size: 18px;">{escape_html(_top['name'])}</h3>
            <p style="color: #B3B3B3; font-size: 13px; margin: 0 0 12px 0;">{escape_html(_top['description'])}</p>
            <p style="margin: 0 0 8px 0; font-size: 14px;">
                <b>{_top['negative_review_count']:,} negative reviews</b> &nbsp;·&nbsp;
                {_top['pct_of_negative']:.0f}% of all negative feedback &nbsp;·&nbsp;
                Top issue: <b>{escape_html(_top['top_pain_area'])}</b>
            </p>
            <p style="margin: 12px 0 0 0; font-size: 13px; color: #B3B3B3; border-top: 1px solid #282828; padding-top: 12px;">
                <b style="color: #FFFFFF;">Suggested opening question:</b>
                <i> "Walk me through the last time Spotify played something you hadn't heard before — and whether it stuck."</i>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if len(_active_segments) > 1:
        _runner_up = _active_segments[1] if _active_segments[1] != _top else (_active_segments[2] if len(_active_segments) > 2 else None)
        if _runner_up:
            st.caption(
                f"Runner-up: **{_runner_up['name']}** ({_runner_up['negative_review_count']:,} negative reviews). "
                "Consider them if you want a contrasting perspective."
            )
else:
    st.info("Scrape more feedback to identify the best segment for interviews.")

st.page_link("pages/4_💡_Strategic_Insights.py", label="See AI-written answers to all 6 discovery questions →")

st.markdown("---")

with st.expander("Supporting charts (optional detail)", expanded=False):
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
        st.markdown("**Words that show up most**")
        all_text = " ".join(df["review_text"].dropna().astype(str).tolist())
        fig_wc = wordclouds.generate(all_text, "Most common words in feedback")
        st.pyplot(fig_wc)
    with col6:
        st.plotly_chart(charts.rating_sentiment_scatter(df), use_container_width=True)

    st.markdown("**Recurring discussion themes (LDA)**")
    st.caption(
        "Unsupervised clusters — useful for nuance, not primary validation."
        + (" Computed on the full dataset." if tier_filter != TIER_ALL else "")
    )
    if topics:
        st.plotly_chart(charts.topic_visualization(topics), use_container_width=True)
    else:
        st.caption("Not enough data for topic clustering.")
