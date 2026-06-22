"""
Spotify Review Discovery Engine - Deep Dive Search Page
=========================================================
Allows granular search and multi-dimensional filtering across scraped reviews.
"""

import sys
import math
import streamlit as st
import pandas as pd

sys.path.insert(0, ".")

from config import settings
from utils.data_io import restore_analyzed_dataframe, export_analyzed_dataframe_to_excel, export_dataframe_to_csv
from utils.html import escape_html
from utils.dashboard_context import prepare_dashboard_df
from utils.tier_inference import TIER_ALL, TIER_LABELS, assign_inferred_tier

# ============================================================
# Page Config
# ============================================================
st.set_page_config(
    page_title="Deep Dive - Spotify Review Engine",
    page_icon="🔍",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp {
        background-color: #121212;
        color: #FFFFFF;
    }
    .spotify-card {
        background-color: #1E1E1E;
        border: 1px solid #282828;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 15px;
    }
    .theme-tag {
        background-color: #282828;
        color: #1DB954;
        border: 1px solid #1DB954;
        border-radius: 12px;
        padding: 2px 10px;
        font-size: 11px;
        display: inline-block;
        margin-right: 5px;
        margin-top: 5px;
    }
    .source-badge {
        background-color: #1DB954;
        color: #FFFFFF;
        font-weight: bold;
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 11px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# Data Validation
# ============================================================
if "analyzed_data" not in st.session_state or st.session_state.analyzed_data.empty:
    st.warning("No data yet. Run a scrape from the home page, or load a saved export.")
    st.stop()

df = restore_analyzed_dataframe(st.session_state.analyzed_data.copy())
df = assign_inferred_tier(df) if "inferred_user_tier" not in df.columns else df

tier_filter = st.session_state.get("dashboard_tier_filter", TIER_ALL)
df = prepare_dashboard_df(df, tier_filter)

# Ensure proper types
df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True).dt.tz_convert(None)

# ============================================================
# Sidebar Granular Filters
# ============================================================
st.sidebar.title("Filters")
if tier_filter != TIER_ALL:
    st.sidebar.info(f"Tier view: **{TIER_LABELS[tier_filter]}** (set on Dashboard)")

# 1. Search Query
search_query = st.sidebar.text_input("Search review text", value="", placeholder="e.g. discover, algorithm, repeat")

# 2. User segment
if "primary_user_segment" in df.columns:
    segment_options = sorted(df["primary_user_segment"].dropna().unique().tolist())
    selected_segments = st.sidebar.multiselect(
        "User segment",
        options=segment_options,
        default=segment_options,
        help="Primary segment label assigned during analysis.",
    )
else:
    selected_segments = []

# 3. Source Filter
sources = df["source"].unique().tolist()
selected_sources = st.sidebar.multiselect("Data Source", options=sources, default=sources)

# 4. Sentiment Filter
sentiments = ["Positive", "Neutral", "Negative"]
selected_sentiments = st.sidebar.multiselect("Sentiment", options=sentiments, default=sentiments)

# 5. Rating Filter (Only applies to Store sources)
rated = df["rating"].dropna()
min_r = int(rated.min()) if not rated.empty else 1
max_r = int(rated.max()) if not rated.empty else 5
selected_ratings = st.sidebar.slider("Store Rating", min_value=1, max_value=5, value=(min_r, max_r))

# 6. Theme Filter
theme_list = list(settings.THEME_TAXONOMY.keys())
selected_themes = st.sidebar.multiselect("Classified Themes", options=theme_list, default=[])

# 7. Date Range Filter
valid_dates = df["date"].dropna()
if not valid_dates.empty:
    min_date = valid_dates.min().date()
    max_date = valid_dates.max().date()
    if min_date != max_date:
        selected_dates = st.sidebar.date_input("Date Range", value=[min_date, max_date])
    else:
        selected_dates = None
else:
    selected_dates = None

# ============================================================
# Apply Filters to DataFrame
# ============================================================
filtered_df = df.copy()

# Source filter
if selected_sources:
    filtered_df = filtered_df[filtered_df["source"].isin(selected_sources)]
else:
    filtered_df = filtered_df.iloc[0:0]

# User segment filter
if "primary_user_segment" in filtered_df.columns:
    if selected_segments:
        filtered_df = filtered_df[filtered_df["primary_user_segment"].isin(selected_segments)]
    else:
        filtered_df = filtered_df.iloc[0:0]

# Sentiment filter
if selected_sentiments:
    filtered_df = filtered_df[filtered_df["sentiment_label"].isin(selected_sentiments)]
else:
    filtered_df = filtered_df.iloc[0:0]

# Rating filter
if selected_ratings:
    store_mask = filtered_df["rating"].isna() | (
        (filtered_df["rating"] >= selected_ratings[0]) & (filtered_df["rating"] <= selected_ratings[1])
    )
    filtered_df = filtered_df[store_mask]

# Theme filter
if selected_themes:
    theme_masks = [filtered_df[f"theme_{t}"] == True for t in selected_themes]
    if theme_masks:
        combined_mask = theme_masks[0]
        for m in theme_masks[1:]:
            combined_mask = combined_mask | m
        filtered_df = filtered_df[combined_mask]

# Date range filter
if selected_dates and len(selected_dates) == 2:
    start_dt = pd.to_datetime(selected_dates[0])
    end_dt = pd.to_datetime(selected_dates[1])
    filtered_df = filtered_df[(filtered_df["date"] >= start_dt) & (filtered_df["date"] <= end_dt)]

# Keyword search query (literal match, not regex)
if search_query.strip():
    filtered_df = filtered_df[
        filtered_df["review_text"].astype(str).str.contains(
            search_query, case=False, na=False, regex=False
        )
    ]

# Reset pagination when filters change
filter_key = (
    search_query,
    tuple(selected_sources),
    tuple(selected_sentiments),
    selected_ratings,
    tuple(selected_themes),
    tuple(selected_dates) if selected_dates else None,
)
if st.session_state.get("filter_key") != filter_key:
    st.session_state.current_page = 1
    st.session_state.filter_key = filter_key

# ============================================================
# Main Page Render
# ============================================================
st.title("🔍 Deep Dive Feedback Explorer")
st.markdown("Query, filter, and inspect verbatim user reviews to discover patterns and feature requests.")
st.markdown("---")

# Header row with results summary and export buttons
hr_col1, hr_col2, hr_col3 = st.columns([3, 1, 1])
with hr_col1:
    st.markdown(f"Found **{len(filtered_df):,}** reviews matching your criteria.")
with hr_col2:
    if not filtered_df.empty:
        st.download_button(
            label="📥 Export CSV",
            data=export_dataframe_to_csv(filtered_df),
            file_name="filtered_spotify_reviews.csv",
            mime="text/csv",
            use_container_width=True,
        )
with hr_col3:
    if not filtered_df.empty:
        st.download_button(
            label="📥 Export Excel",
            data=export_analyzed_dataframe_to_excel(filtered_df, sheet_name="Filtered Reviews"),
            file_name="filtered_spotify_reviews.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

st.markdown("---")

# Pagination setup
items_per_page = 20
total_items = len(filtered_df)
total_pages = max(1, math.ceil(total_items / items_per_page))

if "current_page" not in st.session_state:
    st.session_state.current_page = 1

# Page controller
p_col1, p_col2, p_col3 = st.columns([1, 4, 1])
with p_col1:
    prev_page = st.button("⬅️ Previous")
with p_col3:
    next_page = st.button("Next ➡️")

if prev_page and st.session_state.current_page > 1:
    st.session_state.current_page -= 1
if next_page and st.session_state.current_page < total_pages:
    st.session_state.current_page += 1

st.session_state.current_page = max(1, min(st.session_state.current_page, total_pages))

with p_col2:
    st.markdown(
        f"<div style='text-align: center; color: #B3B3B3; margin-top: 10px;'>"
        f"Page <b>{st.session_state.current_page}</b> of <b>{total_pages}</b>"
        f"</div>",
        unsafe_allow_html=True,
    )

st.markdown("---")

# Render paginated reviews
start_idx = (st.session_state.current_page - 1) * items_per_page
end_idx = min(start_idx + items_per_page, total_items)

page_items = filtered_df.iloc[start_idx:end_idx]

if page_items.empty:
    st.info("No reviews found. Try relaxing your filters in the sidebar.")
else:
    for _, row in page_items.iterrows():
        rating_stars = "N/A"
        if pd.notna(row["rating"]) and row["rating"] > 0:
            stars = max(0, min(5, round(float(row["rating"]))))
            rating_stars = f"{'★' * stars}{'☆' * (5 - stars)}"

        sent_val = row["sentiment_compound"]
        sent_color = (
            "#1DB954"
            if row["sentiment_label"] == "Positive"
            else "#E91429"
            if row["sentiment_label"] == "Negative"
            else "#B3B3B3"
        )

        themes_found = [t for t in theme_list if row.get(f"theme_{t}") == True]
        theme_badges = "".join(
            [
                f'<span class="theme-tag">{escape_html(settings.THEME_TAXONOMY[t]["icon"])} {escape_html(t)}</span>'
                for t in themes_found
            ]
        )

        date_str = (
            row["date"].strftime("%Y-%m-%d %H:%M:%S")
            if pd.notna(row["date"])
            else "Unknown"
        )
        app_version = escape_html(row["app_version"]) if pd.notna(row["app_version"]) else "N/A"

        st.markdown(
            f"""
            <div class="spotify-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <div>
                        <span class="source-badge">{escape_html(row['source'])}</span>
                        <span style="color: #FFC97E; font-weight: bold; margin-left: 10px; font-family: monospace;">{rating_stars}</span>
                    </div>
                    <div style="font-weight: bold; color: {sent_color};">
                        {escape_html(row['sentiment_label'])} ({sent_val:+.2f})
                    </div>
                </div>
                <div style="font-size: 12px; color: #B3B3B3; margin-bottom: 10px;">
                    User: {escape_html(row['username'])} | Date: {date_str} | Version: {app_version}
                </div>
                <p style="font-size: 14px; margin-bottom: 10px; line-height: 1.6;">"{escape_html(row['review_text'])}"</p>
                <div>
                    {theme_badges}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        f"<div style='text-align: center; color: #B3B3B3; font-size: 13px;'>"
        f"Showing reviews {start_idx + 1} to {end_idx} of {total_items}"
        f"</div>",
        unsafe_allow_html=True,
    )
