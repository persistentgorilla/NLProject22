"""
Spotify Review Discovery Engine - Streamlit Web Application
============================================================
Main entry point and orchestrator for scraping and analysis workflows.
"""

import os
import sys
import pandas as pd
import streamlit as st

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, ".")

from config import settings
from scrapers import PlayStoreScraper, AppStoreScraper, RedditScraper, CommunityForumScraper
from analysis import InsightsEngine
from utils.data_io import load_analyzed_data, restore_analyzed_dataframe, save_analyzed_data, export_analyzed_dataframe_to_excel
from utils.text_filters import filter_reviews_dataframe
from utils.dashboard_context import clear_dashboard_cache, dataset_version, get_exec_summary, negative_pct

# ============================================================
# Page Configuration
# ============================================================
st.set_page_config(
    page_title="Spotify Review Discovery Engine",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# Theme & Premium CSS Injection
# ============================================================
st.markdown(
    """
    <style>
    /* Main container background */
    .stApp {
        background-color: #121212;
        color: #FFFFFF;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #1E1E1E !important;
        border-right: 1px solid #282828;
    }
    
    /* Metrics panel cards */
    div[data-testid="stMetricValue"] {
        color: #1DB954 !important;
        font-weight: bold;
        font-family: 'Inter', sans-serif;
    }
    
    div[data-testid="stMetricLabel"] {
        color: #B3B3B3 !important;
        font-size: 14px !important;
    }
    
    div[data-testid="metric-container"] {
        background-color: #1E1E1E;
        border: 1px solid #282828;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    
    /* Custom headers and badges */
    .spotify-header {
        font-family: 'Inter', sans-serif;
        color: #FFFFFF;
        font-weight: 800;
        margin-bottom: 5px;
    }
    
    .spotify-accent {
        color: #1DB954;
    }
    
    .spotify-card {
        background-color: #1E1E1E;
        border: 1px solid #282828;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 15px;
    }
    
    /* Button styles */
    .stButton>button {
        background-color: #1DB954 !important;
        color: #FFFFFF !important;
        border-radius: 20px !important;
        border: none !important;
        padding: 8px 24px !important;
        font-weight: 600 !important;
        transition: background-color 0.3s ease;
    }
    
    .stButton>button:hover {
        background-color: #1ED760 !important;
        cursor: pointer;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background-color: #1E1E1E !important;
        color: #FFFFFF !important;
        border: 1px solid #282828 !important;
        border-radius: 5px !important;
    }
    
    /* Scrollbars */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: #121212;
    }
    ::-webkit-scrollbar-thumb {
        background: #282828;
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #1DB954;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# Session State Initialization
# ============================================================
if "raw_data" not in st.session_state:
    st.session_state.raw_data = pd.DataFrame()
if "analyzed_data" not in st.session_state:
    st.session_state.analyzed_data = pd.DataFrame()
if "topics" not in st.session_state:
    st.session_state.topics = []
if "insights" not in st.session_state:
    st.session_state.insights = []

# Ensure data folder exists
os.makedirs(settings.DATA_DIR, exist_ok=True)

# Helper function to get paths
scraped_data_path = os.path.join(settings.DATA_DIR, settings.SCRAPED_DATA_FILE)
analyzed_data_path = os.path.join(settings.DATA_DIR, settings.ANALYZED_DATA_FILE)

# ============================================================
# Sidebar Section (Data Controls)
# ============================================================
st.sidebar.markdown(
    '# <span class="spotify-accent">🎵</span> Spotify Discovery Engine',
    unsafe_allow_html=True,
)
st.sidebar.caption(f"Version {settings.APP_VERSION}")

st.sidebar.markdown("---")
st.sidebar.subheader("📥 Data Source Selection")

scrape_playstore = st.sidebar.checkbox("Google Play Store", value=True)
scrape_appstore = st.sidebar.checkbox("Apple App Store", value=True)
scrape_reddit = st.sidebar.checkbox("Reddit Discussions", value=True)
scrape_community = st.sidebar.checkbox("Community Forums", value=True)

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Scraping Configurations")
st.sidebar.caption("Region: **India (IN)** · Language: **English**")

count = st.sidebar.number_input(
    "Target Reviews per App Store",
    min_value=settings.PLAYSTORE_REVIEW_COUNT_MIN,
    max_value=settings.PLAYSTORE_REVIEW_COUNT_MAX,
    value=settings.PLAYSTORE_MIN_REVIEWS,
    step=50,
)
st.sidebar.caption(
    f"Minimum: {settings.PLAYSTORE_REVIEW_COUNT_MIN:,} · "
    f"Maximum: {settings.PLAYSTORE_REVIEW_COUNT_MAX:,} reviews per app store."
)

country = settings.PLAYSTORE_DEFAULT_COUNTRY
language = settings.PLAYSTORE_DEFAULT_LANG

st.sidebar.markdown("---")

# ============================================================
# Processing Actions
# ============================================================
if st.sidebar.button("🚀 Start Scraping & Analysis"):
    st.session_state.raw_data = pd.DataFrame()
    st.session_state.analyzed_data = pd.DataFrame()
    st.session_state.topics = []
    st.session_state.insights = []

    combined_dfs = []

    # Status container
    with st.status("🔍 Initializing Spotify data collection...", expanded=True) as status_box:
        
        # 1. Google Play Store Scraper
        if scrape_playstore and count > 0:
            status_box.update(label="📥 Scraping Google Play Store...")
            progress_bar = st.progress(0, text="Fetching Play Store reviews...")

            def play_cb(curr, total):
                prog = min(float(curr) / float(total), 1.0)
                progress_bar.progress(prog, text=f"Fetched {curr}/{total} Play Store reviews")

            try:
                scraper = PlayStoreScraper(
                    progress_callback=play_cb,
                    count=count,
                    country=country,
                    lang=language,
                )
                df_play = scraper.scrape()
                if not df_play.empty:
                    combined_dfs.append(df_play)
                    st.write(f"✅ Play Store reviews collected: **{len(df_play)}**")
                else:
                    st.write("⚠️ Play Store scraper returned no data.")
            except Exception as exc:
                st.write(f"⚠️ Play Store scraper failed: {exc}")
            progress_bar.empty()
        elif scrape_playstore:
            st.write("ℹ️ Play Store scrape skipped (target set to 0).")

        # 2. Apple App Store Scraper
        if scrape_appstore and count > 0:
            status_box.update(label="📥 Scraping Apple App Store...")
            progress_bar = st.progress(0, text="Fetching App Store reviews...")

            def app_cb(curr, total):
                prog = min(float(curr) / float(total), 1.0)
                progress_bar.progress(prog, text=f"Fetched {curr}/{total} App Store reviews")

            try:
                scraper = AppStoreScraper(
                    progress_callback=app_cb,
                    count=count,
                    country=country,
                )
                df_app = scraper.scrape()
                if not df_app.empty:
                    combined_dfs.append(df_app)
                    st.write(f"✅ App Store reviews collected: **{len(df_app)}**")
                else:
                    st.write("⚠️ App Store scraper returned no data (library and RSS fallback both failed).")
            except Exception as exc:
                st.write(f"⚠️ App Store scraper failed: {exc}")
            progress_bar.empty()
        elif scrape_appstore:
            st.write("ℹ️ App Store scrape skipped (target set to 0).")

        # 3. Reddit Discussions
        if scrape_reddit:
            status_box.update(label="📥 Scraping Reddit Discussions...")
            progress_bar = st.progress(0, text="Searching Reddit...")

            try:
                scraper = RedditScraper()
                df_reddit = scraper.scrape()
                if not df_reddit.empty:
                    combined_dfs.append(df_reddit)
                    st.write(f"✅ Reddit reviews/comments collected: **{len(df_reddit)}**")
                else:
                    st.write("⚠️ Reddit scraper returned no data.")
            except Exception as exc:
                st.write(f"⚠️ Reddit scraper failed: {exc}")
            progress_bar.empty()

        # 4. Spotify Community Forum
        if scrape_community:
            status_box.update(label="📥 Scraping Spotify Community Forum...")
            progress_bar = st.progress(0, text="Crawling community.spotify.com...")

            try:
                scraper = CommunityForumScraper()
                df_forum = scraper.scrape()
                if not df_forum.empty:
                    combined_dfs.append(df_forum)
                    st.write(f"✅ Community forum discussions collected: **{len(df_forum)}**")
                else:
                    st.write("⚠️ Community forum scraper returned no data.")
            except Exception as exc:
                st.write(f"⚠️ Community forum scraper failed: {exc}")
            progress_bar.empty()

        # Combine all sources
        if combined_dfs:
            status_box.update(label="🧩 Merging and deduplicating data...")
            raw_combined = pd.concat(combined_dfs, ignore_index=True)
            # Deduplicate by text (case insensitive)
            if "review_text" in raw_combined.columns:
                raw_combined["text_lower"] = raw_combined["review_text"].astype(str).str.lower().str.strip()
                raw_combined = raw_combined.drop_duplicates(subset=["text_lower"]).drop(columns=["text_lower"])

            status_box.update(label="🧹 Applying review quality filters...")
            raw_combined, filter_stats = filter_reviews_dataframe(raw_combined)
            if filter_stats["removed_total"] > 0:
                st.write(
                    "🧹 Quality filter removed "
                    f"**{filter_stats['removed_total']:,}** records "
                    f"({filter_stats['removed_emoji']:,} with emojis, "
                    f"{filter_stats['removed_short']:,} with fewer than "
                    f"{settings.MIN_REVIEW_WORD_COUNT} words). "
                    f"**{filter_stats['kept_total']:,}** records kept."
                )
            else:
                st.write(f"🧹 Quality filter passed all **{filter_stats['kept_total']:,}** records.")

            if raw_combined.empty:
                status_box.update(label="❌ No data remaining after quality filters.", state="error")
                st.error(
                    "All collected records were removed by the quality filter "
                    f"(emoji-free text with at least {settings.MIN_REVIEW_WORD_COUNT} words required)."
                )
            else:
                st.session_state.raw_data = raw_combined
                raw_combined.to_csv(scraped_data_path, index=False)
                st.write(f"✅ Total unique records compiled: **{len(raw_combined)}**")

                # Run Analysis
                status_box.update(label="🧠 Analyzing reviews with NLP & Sentiment Engines...")
                try:
                    engine = InsightsEngine()

                    analyzed_df = engine.run_full_analysis(raw_combined)
                    st.session_state.analyzed_data = analyzed_df
                    save_analyzed_data(analyzed_df, analyzed_data_path)

                    topics = engine.topic_modeler.get_topic_summary()
                    st.session_state.topics = topics

                    clear_dashboard_cache()
                    st.session_state.insights = engine.answer_strategic_questions(analyzed_df)
                    st.session_state.insights_version = dataset_version(analyzed_df)

                    status_box.update(label="📈 Analysis completed successfully!", state="complete")
                    st.success("🎉 Data collection and analysis complete! Browse the dashboard pages in the sidebar to explore insights.")
                except Exception as exc:
                    status_box.update(label="❌ Analysis failed.", state="error")
                    st.error(f"Analysis pipeline failed: {exc}")
        else:
            status_box.update(label="❌ No data collected.", state="error")
            st.error("Failed to collect any data. Please verify your internet connection or check the scraper logs.")

# Load saved data action
if os.path.exists(analyzed_data_path) or os.path.exists(scraped_data_path):
    if st.sidebar.button("📂 Load Previously Analyzed Data"):
        with st.spinner("Loading cached analysis..."):
            if os.path.exists(analyzed_data_path):
                df = load_analyzed_data(analyzed_data_path)
                st.session_state.analyzed_data = df
                st.session_state.raw_data = (
                    pd.read_csv(scraped_data_path) if os.path.exists(scraped_data_path) else df
                )
                
                # Re-run topic and insights generation
                engine = InsightsEngine()
                
                # Fit LDA topics on loaded dataset
                clear_dashboard_cache()
                engine.topic_modeler.analyze(df)
                st.session_state.topics = engine.topic_modeler.get_topic_summary()
                st.session_state.insights = engine.answer_strategic_questions(df)
                st.session_state.insights_version = dataset_version(df)
                
                st.sidebar.success("✅ Cached data loaded!")
                st.success("📂 Successfully loaded previously analyzed data!")
            elif os.path.exists(scraped_data_path):
                df = pd.read_csv(scraped_data_path)
                df, _ = filter_reviews_dataframe(df)
                st.session_state.raw_data = df
                # Analyze and save
                engine = InsightsEngine()
                clear_dashboard_cache()
                df_analyzed = engine.run_full_analysis(df)
                st.session_state.analyzed_data = df_analyzed
                save_analyzed_data(df_analyzed, analyzed_data_path)
                st.session_state.topics = engine.topic_modeler.get_topic_summary()
                st.session_state.insights = engine.answer_strategic_questions(df_analyzed)
                st.session_state.insights_version = dataset_version(df_analyzed)
                st.sidebar.success("✅ Raw cache analyzed and loaded!")
                st.success("📂 Successfully analyzed and loaded cached raw data!")

# ============================================================
# Main Page Dashboard UI
# ============================================================
st.markdown(
    '# <span class="spotify-header">Spotify <span class="spotify-accent">Review Discovery Engine</span></span>',
    unsafe_allow_html=True,
)
st.markdown(
    "User feedback from India app stores, Reddit, and community posts — collected and tagged "
    "so you can see where discovery and recommendations are breaking down."
)

if st.session_state.analyzed_data.empty:
    # Fresh welcome page
    st.markdown("---")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown(
            """
            ### Getting started
            
            This tool pulls together what users are saying about Spotify's music discovery experience — 
            where recommendations fall short, why people replay the same tracks, and what they wish the product did differently.
            
            #### How to run a pull
            1. **Pick your sources** in the sidebar. Play Store + Reddit is a good first pass.
            2. **Set a review target** for India app stores (0–5,000 per store; default 300).
            3. Click **Start Scraping & Analysis** to pull live English feedback.
            4. When it finishes, use the sidebar to move between:
                * **Dashboard** — Volume, sentiment, and themes at a glance.
                * **Deep Dive** — Search and filter individual reviews.
                * **Strategic Insights** — Answers to the six discovery questions below.
            
            #### Where the data comes from
            * **Play Store (India, English)** — Public reviews via `google-play-scraper`.
            * **App Store (India, English)** — Public reviews via iTunes RSS.
            * **Reddit** — Posts and comments from Spotify-related subreddits (RSS + archive fallback).
            * **Community forum** — Recent public posts on `community.spotify.com`.
            * **Quality filter** — We drop reviews with emojis or fewer than 4 words before analysis.
            """
        )
        
    with col2:
        st.markdown(
            """
            <div class="spotify-card">
                <h4 style="color: #1DB954; margin-top: 0;">Questions this tool helps answer</h4>
                <ol style="margin-bottom: 0; padding-left: 20px; line-height: 1.6;">
                    <li>Why do users struggle to discover new music?</li>
                    <li>What frustrates people about recommendations?</li>
                    <li>What listening habits are users trying to build?</li>
                    <li>What keeps people in repetitive listening loops?</li>
                    <li>Which segments hit different discovery problems?</li>
                    <li>What needs keep showing up that we are not meeting?</li>
                </ol>
            </div>
            <div class="spotify-card" style="margin-top: 15px;">
                <h4 style="color: #FFFFFF; margin-top: 0;">How reviews get tagged</h4>
                <ul style="margin-bottom: 0; padding-left: 20px; line-height: 1.6;">
                    <li><b>Sentiment</b> — Positive, neutral, or negative tone (VADER).</li>
                    <li><b>Subjectivity</b> — Opinion vs factual statement (TextBlob).</li>
                    <li><b>Themes</b> — Keyword rules for discovery, algorithm, playlists, etc.</li>
                    <li><b>Topics</b> — Clusters of reviews with similar language (LDA).</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

else:
    df = restore_analyzed_dataframe(st.session_state.analyzed_data.copy())
    exec_summary = get_exec_summary(df)
    pain_themes = exec_summary.get("pain_themes", [])
    neg_count = exec_summary.get("negative_review_count", 0)
    top_pain = pain_themes[0]["theme"] if pain_themes else "—"

    st.markdown("---")
    overview_col, export_col = st.columns([5, 1])
    with overview_col:
        st.markdown("### This run at a glance")
        st.caption(exec_summary.get("headline", ""))
    with export_col:
        st.download_button(
            label="Export Excel",
            data=export_analyzed_dataframe_to_excel(df),
            file_name="spotify_analyzed_reviews.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Reviews in this run", f"{len(df):,}")
    with c2:
        st.metric("Negative reviews", f"{neg_count:,}")
    with c3:
        st.metric("% negative", f"{negative_pct(df):.1f}%")
    with c4:
        st.metric("Top pain area", top_pain)

    st.page_link("pages/1_📊_Dashboard.py", label="Open Dashboard for segments, pain areas, and quotes →")
    st.page_link("pages/4_💡_Strategic_Insights.py", label="Open Strategic Insights for question-by-question answers →")
