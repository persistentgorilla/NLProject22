"""
Spotify Review Discovery Engine - Trend Analysis Page
======================================================
Explores sentiment shifts and theme changes over time.
"""

import sys
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

sys.path.insert(0, ".")

from config import settings
from visualizations import ChartBuilder
from utils.data_io import restore_analyzed_dataframe, normalize_date_column, export_analyzed_dataframe_to_excel

# ============================================================
# Page Config
# ============================================================
st.set_page_config(
    page_title="Trends - Spotify Review Engine",
    page_icon="📈",
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
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# Data Validation
# ============================================================
if "analyzed_data" not in st.session_state or st.session_state.analyzed_data.empty:
    st.warning("⚠️ No analyzed data found. Please go back to the main portal page (app.py) in the sidebar to scrape or load data first.")
    st.stop()

df_all = restore_analyzed_dataframe(st.session_state.analyzed_data.copy())
df = normalize_date_column(df_all)
dated_count = int(df["date"].notna().sum()) if "date" in df.columns else 0
df = df.dropna(subset=["date"])

if df.empty:
    st.info(
        "No records with valid timestamps are available, so temporal trends cannot be computed. "
        "Re-run **Start Scraping & Analysis** on the home page to refresh Reddit and Community Forum "
        "sources — older sessions may only contain app-store reviews without usable dates."
    )
    if dated_count == 0 and not df_all.empty:
        sources = df_all["source"].value_counts().to_dict() if "source" in df_all.columns else {}
        st.caption(f"Loaded records by source: {sources}")
    st.stop()

# ============================================================
# Main Page Layout
# ============================================================
title_col, export_col = st.columns([5, 1])
with title_col:
    st.title("📈 Temporal Trend Analysis")
    st.markdown(
        "Track shifts in customer sentiments and theme prevalence over time to measure feature updates and service releases."
    )
    st.caption(
        f"Analyzing **{len(df):,}** dated records "
        f"({dated_count / max(len(df_all), 1) * 100:.0f}% of the loaded dataset) "
        f"from **{df['date'].min().date()}** to **{df['date'].max().date()}**."
    )
with export_col:
    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
    st.download_button(
        label="📥 Export Excel",
        data=export_analyzed_dataframe_to_excel(df, sheet_name="Trend Analysis Data"),
        file_name="spotify_trend_analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        help="Download the dated records used for trend charts.",
    )
st.markdown("---")

charts = ChartBuilder()

# 1. Sentiment Trends Over Time
st.subheader("1. Sentiment Trends")
sentiment_fig = charts.sentiment_over_time(df)
if len(sentiment_fig.data) == 0:
    st.info("Not enough dated sentiment records to render the trend chart.")
else:
    st.plotly_chart(sentiment_fig, use_container_width=True)

st.markdown("---")

# 2. Theme Trends Over Time
st.subheader("2. Theme Prevalence Over Time")
st.markdown(
    "Analyze how mentions of key discovery and UX themes have evolved week-over-week."
)

# Resample theme columns by week/month
theme_cols = [c for c in df.columns if c.startswith("theme_") and c != "theme_count"]
if theme_cols:
    df_themes = df[["date"] + theme_cols].copy()
    for col in theme_cols:
        df_themes[col] = df_themes[col].astype(int)
    df_themes = df_themes.set_index("date")
    
    # Weekly sum
    weekly_themes = df_themes.resample("W").sum().reset_index()
    
    # Melt for Plotly area chart
    melted_themes = weekly_themes.melt(
        id_vars=["date"],
        value_vars=theme_cols,
        var_name="Theme",
        value_name="Mentions",
    )
    # Clean theme names
    melted_themes["Theme"] = melted_themes["Theme"].str.replace("theme_", "")
    
    # Plotly Stacked Area Chart
    fig_area = px.area(
        melted_themes,
        x="date",
        y="Mentions",
        color="Theme",
        color_discrete_sequence=settings.PLOTLY_COLOR_SEQUENCE,
        title="Weekly Theme Frequency (Volume Over Time)",
        labels={"date": "Week Ending", "Mentions": "Volume of Mentions"},
    )
    # Theme layout updates
    fig_area.update_layout(
        template=settings.PLOTLY_TEMPLATE,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=settings.SPOTIFY_WHITE),
    )
    fig_area.update_xaxes(gridcolor=settings.SPOTIFY_MEDIUM_GRAY)
    fig_area.update_yaxes(gridcolor=settings.SPOTIFY_MEDIUM_GRAY)
    
    st.plotly_chart(fig_area, use_container_width=True)
else:
    st.info("Theme columns are not formatted correctly for temporal parsing.")

st.markdown("---")

# 3. Rating Trends by Source
st.subheader("3. Rating Trends (Stores Only)")
col1, col2 = st.columns([2, 1])

with col1:
    df_rated = df[df["rating"].notna() & (df["rating"] > 0)].copy()
    if not df_rated.empty:
        # Group by day and source, calculate rolling mean
        df_rated = df_rated.set_index("date")
        
        rating_stats = []
        for src, group in df_rated.groupby("source"):
            daily_rating = group["rating"].resample("D").mean().reset_index()
            daily_rating["rolling_7d"] = daily_rating["rating"].rolling(window=7, min_periods=1).mean()
            daily_rating["source"] = src
            rating_stats.append(daily_rating)
            
        if rating_stats:
            df_rating_trends = pd.concat(rating_stats, ignore_index=True)
            
            fig_rating = px.line(
                df_rating_trends,
                x="date",
                y="rolling_7d",
                color="source",
                color_discrete_sequence=settings.PLOTLY_COLOR_SEQUENCE,
                title="7-day Rolling Average Rating by App Store",
                labels={"date": "Date", "rolling_7d": "7-day Avg Rating"},
            )
            # Apply styling
            fig_rating.update_layout(
                template=settings.PLOTLY_TEMPLATE,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color=settings.SPOTIFY_WHITE),
                yaxis=dict(range=[1, 5]),
            )
            fig_rating.update_xaxes(gridcolor=settings.SPOTIFY_MEDIUM_GRAY)
            fig_rating.update_yaxes(gridcolor=settings.SPOTIFY_MEDIUM_GRAY)
            
            st.plotly_chart(fig_rating, use_container_width=True)
        else:
            st.info("No rating trend data found.")
    else:
        st.info("No rating data available for store-based review trends.")

with col2:
    st.markdown("### 🔍 Spike Detection & Key Dates")
    st.markdown(
        "Spike detection identifies dates where sentiment scores or feedback volume fluctuated significantly."
    )
    
    # Calculate daily feedback count and mean sentiment
    daily = df.set_index("date")
    daily_summary = daily.resample("D").agg(
        volume=("review_text", "count"),
        avg_sentiment=("sentiment_compound", "mean")
    ).reset_index()
    
    if len(daily_summary) > 2:
        # Detect sudden volume surges (> 2 standard dev)
        mean_vol = daily_summary["volume"].mean()
        std_vol = daily_summary["volume"].std()
        volume_threshold = mean_vol + 1.5 * std_vol if std_vol > 0 else 100
        
        surges = daily_summary[daily_summary["volume"] > volume_threshold]
        
        # Detect extremely negative days
        neg_days = daily_summary[daily_summary["avg_sentiment"] < -0.15]
        
        st.markdown("**🚨 Notable Volume Surges:**")
        if not surges.empty:
            for idx, row in surges.head(5).iterrows():
                st.markdown(f"- **{row['date'].strftime('%Y-%m-%d')}**: {int(row['volume'])} reviews (Avg Sentiment: {row['avg_sentiment']:+.2f})")
        else:
            st.markdown("*No significant volume spikes detected.*")
            
        st.markdown("**📉 Critical Sentiment Dips:**")
        if not neg_days.empty:
            for idx, row in neg_days.head(5).iterrows():
                st.markdown(f"- **{row['date'].strftime('%Y-%m-%d')}**: Avg Sentiment {row['avg_sentiment']:+.2f} ({int(row['volume'])} reviews)")
        else:
            st.markdown("*No severe sentiment drops detected.*")
    else:
        st.markdown("*Requires a longer date span to compute anomalies.*")
