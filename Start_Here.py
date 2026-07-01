"""
Spotify Review Discovery Engine — Single-page application
All views unified under one page with tabs.
"""

import os
import sys
import math
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
from analysis import InsightsEngine, LLMAnalyzer
from utils.data_io import (
    load_analyzed_data, restore_analyzed_dataframe, save_analyzed_data,
    export_analyzed_dataframe_to_excel, export_dataframe_to_csv,
    export_insights_to_excel,
)
from utils.text_filters import filter_reviews_dataframe
from utils.html import escape_html
from utils.session_reset import reset_app_state
from utils.dashboard_context import (
    clear_dashboard_cache, dataset_version,
    get_exec_summary, get_insights, validation_quotes,
    negative_pct,
)
from visualizations import ChartBuilder, WordCloudGenerator

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Spotify Review Discovery Engine",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design system ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Base ── */
.stApp { background-color: #0D0D0D !important; color: #FFF; }
[data-testid="stSidebar"] { background-color: #111 !important; border-right: 1px solid #1E1E1E; }
footer { display: none !important; }
[data-testid="stMetricValue"] { color: #1DB954 !important; font-weight: bold; }
[data-testid="metric-container"] {
    background: #141414; border: 1px solid #1F1F1F;
    border-radius: 10px; padding: 16px;
}

/* ── KPI cards ── */
.kpi-row { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:20px 0 0; }
.kpi-card { border-radius:14px; padding:22px 20px 18px; background:#141414; border:1px solid #1F1F1F; position:relative; overflow:hidden; }
.kpi-card::before { content:""; position:absolute; inset:0 0 auto 0; height:3px; border-radius:14px 14px 0 0; }
.kpi-card.c-green::before { background:linear-gradient(90deg,#1DB954,#169940); }
.kpi-card.c-red::before   { background:linear-gradient(90deg,#E91429,#9b0c1a); }
.kpi-card.c-amber::before { background:linear-gradient(90deg,#F5A623,#c47520); }
.kpi-card.c-purple::before{ background:linear-gradient(90deg,#7B61FF,#5040cc); }
.kpi-card .lbl { font-size:10px; text-transform:uppercase; letter-spacing:1.2px; color:#555; font-weight:700; margin:0 0 12px 0; }
.kpi-card .val { font-size:36px; font-weight:800; line-height:1; margin:0; }
.kpi-card .sub { font-size:11px; color:#555; margin:10px 0 0; }
.c-green .val { color:#1DB954; }
.c-red   .val { color:#E91429; }
.c-amber .val { color:#F5A623; }
.c-purple .val{ color:#A08FFF; font-size:18px !important; padding-top:8px; }

/* ── Section headers ── */
.sec-hdr { margin:48px 0 22px; }
.sec-tag { display:inline-block; font-size:10px; font-weight:700; letter-spacing:1.5px; text-transform:uppercase; padding:3px 12px; border-radius:20px; margin-bottom:12px; }
.sec-tag.green  { background:#1DB95420; color:#1DB954; }
.sec-tag.red    { background:#E9142920; color:#E91429; }
.sec-tag.amber  { background:#F5A62320; color:#F5A623; }
.sec-tag.blue   { background:#4A9EFF20; color:#4A9EFF; }
.sec-tag.purple { background:#7B61FF20; color:#A08FFF; }
.sec-title { font-size:22px; font-weight:700; margin:0 0 6px; color:#F0F0F0; }
.sec-sub   { font-size:13px; color:#666; margin:0; line-height:1.55; }

/* ── Divider ── */
.divider { height:1px; border:none; margin:40px 0; background:linear-gradient(90deg,transparent,#252525,transparent); }

/* ── Headline banner ── */
.headline-banner { background:#141414; border:1px solid #222; border-left:3px solid #1DB954; border-radius:0 10px 10px 0; padding:14px 20px; font-size:14px; color:#B0B0B0; line-height:1.65; margin-bottom:4px; }

/* ── Q&A cards ── */
.qa-card { background:#121212; border:1px solid #1E1E1E; border-radius:12px; padding:18px 20px; margin-bottom:10px; display:flex; gap:16px; align-items:flex-start; }
.qa-num  { font-size:10px; font-weight:800; color:#1DB954; background:#1DB95420; border-radius:6px; padding:4px 8px; flex-shrink:0; letter-spacing:0.5px; margin-top:1px; }
.qa-q    { font-size:14px; font-weight:600; color:#DEDEDE; margin:0 0 7px; }
.qa-a    { font-size:13px; color:#888; margin:0; line-height:1.65; }

/* ── Pain bars ── */
.pain-row { background:#121212; border:1px solid #1E1E1E; border-radius:11px; padding:15px 20px; display:flex; align-items:center; gap:18px; margin-bottom:8px; }
.pain-left  { flex:1; min-width:0; }
.pain-name  { font-size:14px; font-weight:600; color:#E0E0E0; margin:0 0 3px; }
.pain-desc  { font-size:12px; color:#555; margin:0 0 10px; }
.pain-track { background:#1C1C1C; border-radius:4px; height:6px; }
.pain-fill  { height:6px; border-radius:4px; background:linear-gradient(90deg,#E91429,#FF6B6B); }
.pain-right { text-align:right; flex-shrink:0; min-width:80px; }
.pain-num   { font-size:24px; font-weight:700; color:#E91429; margin:0; line-height:1; }
.pain-pct   { font-size:11px; color:#555; margin:4px 0 0; }

/* ── Repeat cards ── */
.rpt-card { background:linear-gradient(160deg,#160808,#1A0C0C); border:1px solid #331515; border-radius:14px; padding:24px 20px; height:100%; box-sizing:border-box; }
.rpt-icon  { font-size:28px; margin-bottom:12px; display:block; }
.rpt-title { font-size:14px; font-weight:700; color:#FF8080; margin:0 0 8px; }
.rpt-desc  { font-size:12px; color:#6B4444; line-height:1.6; margin:0 0 18px; }
.rpt-num   { font-size:34px; font-weight:800; color:#FF6B6B; margin:0; line-height:1; }
.rpt-sub   { font-size:11px; color:#553333; margin:4px 0 0; }
.rpt-neg   { font-size:12px; color:#E91429; font-weight:600; margin:8px 0 0; }

/* ── Segment cards ── */
.seg-card { background:linear-gradient(160deg,#141414,#181818); border:1px solid #222; border-radius:14px; padding:22px 18px; height:100%; box-sizing:border-box; }
.seg-card.dim { opacity:.38; }
.seg-icon  { width:42px; height:42px; border-radius:10px; background:#1DB95420; display:flex; align-items:center; justify-content:center; font-size:20px; margin-bottom:16px; }
.seg-name  { font-size:14px; font-weight:700; color:#1DB954; margin:0 0 6px; }
.seg-desc  { font-size:12px; color:#555; margin:0 0 18px; line-height:1.5; }
.seg-num   { font-size:32px; font-weight:800; color:#FFF; margin:0; line-height:1; }
.seg-nlbl  { font-size:11px; color:#555; margin:2px 0 12px; }
.seg-pct   { font-size:11px; color:#777; margin:0 0 5px; }
.seg-track { background:#1C1C1C; border-radius:4px; height:4px; }
.seg-fill  { height:4px; border-radius:4px; background:linear-gradient(90deg,#1DB954,#57C878); }
.seg-pain  { font-size:12px; color:#888; margin:10px 0 0; }
.seg-pain b{ color:#C0C0C0; }

/* ── Want cards ── */
.want-card { background:linear-gradient(160deg,#0C1A10,#101E14); border:1px solid #1A3320; border-radius:14px; padding:24px 20px; height:100%; box-sizing:border-box; }
.want-icon  { font-size:28px; margin-bottom:12px; display:block; }
.want-title { font-size:14px; font-weight:700; color:#57C878; margin:0 0 8px; }
.want-desc  { font-size:12px; color:#3D6B4A; line-height:1.65; margin:0 0 18px; }
.want-num   { font-size:32px; font-weight:800; color:#1DB954; margin:0; line-height:1; }
.want-sub   { font-size:11px; color:#2D5236; margin:4px 0 0; }

/* ── Quote cards ── */
.quote-card { background:#0F0F0F; border:1px solid #1C1C1C; border-radius:12px; padding:22px 24px 18px; margin-bottom:10px; position:relative; }
.quote-mark { font-size:64px; font-family:Georgia,serif; color:#1DB95428; line-height:1; position:absolute; top:10px; left:16px; margin:0; }
.quote-text { font-size:14px; color:#C8C8C8; line-height:1.75; font-style:italic; margin:0 0 14px; padding-left:44px; }
.quote-pills { display:flex; gap:7px; align-items:center; padding-left:44px; flex-wrap:wrap; }
.qpill { font-size:10px; font-weight:600; letter-spacing:0.4px; padding:3px 10px; border-radius:12px; }
.qpill.src  { background:#1A2E1A; color:#57C878; }
.qpill.seg  { background:#1C1C1C; color:#777; }

/* ── Strategic insights ── */
.finding-card { background:#1A1A1A; border-left:4px solid #1DB954; padding:12px 15px; margin-bottom:10px; border-radius:0 8px 8px 0; line-height:1.55; }
.answer-card  { background:#142818; border-left:4px solid #1DB954; padding:14px 16px; margin:12px 0 16px 0; border-radius:0 8px 8px 0; line-height:1.6; font-size:15px; }
.problem-card { background:#241818; border-left:4px solid #E91429; padding:10px 14px; margin-bottom:10px; border-radius:0 8px 8px 0; }
.quote-box    { background:#282828; border-left:3px solid #B3B3B3; font-style:italic; padding:10px 15px; margin-bottom:10px; border-radius:0 4px 4px 0; font-size:13px; line-height:1.5; }
.segment-card { background:#1E1E1E; border:1px solid #282828; border-radius:10px; padding:16px; margin-bottom:12px; }

/* ── Deep Dive ── */
.review-card  { background:#141414; border:1px solid #1E1E1E; border-radius:12px; padding:18px; margin-bottom:10px; }
.theme-tag    { background:#282828; color:#1DB954; border:1px solid #1DB954; border-radius:12px; padding:2px 10px; font-size:11px; display:inline-block; margin-right:5px; margin-top:5px; }
.source-badge { background:#1DB954; color:#FFF; font-weight:bold; border-radius:4px; padding:2px 6px; font-size:11px; }

/* ── Start Here cards ── */
.spotify-card { background:#1A1A1A; border:1px solid #282828; border-radius:10px; padding:20px; margin-bottom:15px; }

/* ── Expander ── */
details[data-baseweb="accordion"] { background:#111 !important; border:1px solid #222 !important; border-radius:12px !important; }
</style>
""", unsafe_allow_html=True)

# ── Session defaults ───────────────────────────────────────────────────────────
for _k, _v in (
    ("raw_data", pd.DataFrame()), ("analyzed_data", pd.DataFrame()),
    ("topics", []), ("insights", []), ("scrape_triggered", False),
):
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── File paths ─────────────────────────────────────────────────────────────────
scraped_data_path  = os.path.join("data", "spotify_reviews_raw.csv")
analyzed_data_path = os.path.join("data", "spotify_reviews_analyzed.csv")

# ── Helpers ────────────────────────────────────────────────────────────────────
has_data = "analyzed_data" in st.session_state and not st.session_state.analyzed_data.empty

def _hdr(tag: str, color: str, title: str, sub: str = "") -> None:
    sub_html = f'<p class="sec-sub">{escape_html(sub)}</p>' if sub else ""
    st.markdown(
        f'<div class="sec-hdr"><span class="sec-tag {color}">{escape_html(tag)}</span>'
        f'<h2 class="sec-title">{escape_html(title)}</h2>{sub_html}</div>',
        unsafe_allow_html=True,
    )

# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.markdown("## 🎵 Spotify Review Engine")
st.sidebar.markdown("---")
st.sidebar.subheader("📡 Data Sources")
st.sidebar.caption("India · English only")
scrape_playstore = st.sidebar.checkbox("Google Play Store", value=True)
scrape_appstore  = st.sidebar.checkbox("Apple App Store",   value=True)
scrape_reddit    = st.sidebar.checkbox("Reddit Discussions", value=True)
scrape_community = st.sidebar.checkbox("Community Forums",  value=True)

# Always scrape maximum available reviews — no user input needed
count   = settings.PLAYSTORE_REVIEW_COUNT_MAX
country = settings.PLAYSTORE_DEFAULT_COUNTRY
language = settings.PLAYSTORE_DEFAULT_LANG

st.sidebar.markdown("---")

if has_data:
    if st.sidebar.button("↺ Reset", use_container_width=True,
                         help="Clears all data and analysis."):
        reset_app_state()
        st.rerun()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "🏠  Start Here",
    "📊  Dashboard",
    "🔍  Deep Dive",
    "💡  Strategic Insights",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — START HERE
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown(
        '<h1 style="margin:0 0 6px;font-size:28px;font-weight:800;">'
        'Spotify <span style="color:#1DB954;">Review Discovery Engine</span></h1>'
        '<p style="color:#666;font-size:14px;margin:0 0 24px;">India · English · Play Store · App Store · Reddit · Community Forums</p>',
        unsafe_allow_html=True,
    )

    # ── Action buttons ─────────────────────────────────────────────────────────
    btn_col1, btn_col2, btn_col3 = st.columns([2, 2, 3])
    with btn_col1:
        if st.button("🚀 Start Scraping & Analysis", use_container_width=True, type="primary"):
            st.session_state.scrape_triggered = True
    with btn_col2:
        load_visible = os.path.exists(analyzed_data_path) or os.path.exists(scraped_data_path)
        if load_visible and st.button("📂 Load Cached Data", use_container_width=True):
            with st.spinner("Loading cached analysis..."):
                if os.path.exists(analyzed_data_path):
                    df_cached = load_analyzed_data(analyzed_data_path)
                    st.session_state.analyzed_data = df_cached
                    st.session_state.raw_data = (
                        pd.read_csv(scraped_data_path)
                        if os.path.exists(scraped_data_path) else df_cached
                    )
                    engine = InsightsEngine()
                    clear_dashboard_cache()
                    engine.topic_modeler.analyze(df_cached)
                    st.session_state.topics   = engine.topic_modeler.get_topic_summary()
                    st.session_state.insights = engine.answer_strategic_questions(df_cached)
                    st.session_state.insights_version = dataset_version(df_cached)
                elif os.path.exists(scraped_data_path):
                    df_raw = pd.read_csv(scraped_data_path)
                    df_raw, _ = filter_reviews_dataframe(df_raw)
                    engine = InsightsEngine()
                    clear_dashboard_cache()
                    df_analyzed = engine.run_full_analysis(df_raw)
                    st.session_state.raw_data      = df_raw
                    st.session_state.analyzed_data = df_analyzed
                    save_analyzed_data(df_analyzed, analyzed_data_path)
                    st.session_state.topics   = engine.topic_modeler.get_topic_summary()
                    st.session_state.insights = engine.answer_strategic_questions(df_analyzed)
                    st.session_state.insights_version = dataset_version(df_analyzed)
                st.success("✅ Cached data loaded successfully!")
                st.rerun()

    # ── Scraping execution ─────────────────────────────────────────────────────
    if st.session_state.scrape_triggered:
        st.session_state.scrape_triggered = False
        st.session_state.raw_data      = pd.DataFrame()
        st.session_state.analyzed_data = pd.DataFrame()
        st.session_state.topics        = []
        st.session_state.insights      = []

        combined_dfs = []

        with st.status("🔍 Initializing Spotify data collection...", expanded=True) as status_box:

            if scrape_playstore:
                status_box.update(label="📥 Scraping Google Play Store...")
                pb = st.progress(0, text="Fetching Play Store reviews...")
                def play_cb(curr, total):
                    pb.progress(min(float(curr) / float(total), 1.0),
                                text=f"Fetched {curr}/{total} Play Store reviews")
                try:
                    scraper = PlayStoreScraper(progress_callback=play_cb, count=count,
                                               country=country, lang=language)
                    df_play = scraper.scrape()
                    if not df_play.empty:
                        combined_dfs.append(df_play)
                        st.write(f"✅ Play Store reviews collected: **{len(df_play):,}**")
                    else:
                        st.write("⚠️ Play Store returned no data.")
                except Exception as exc:
                    st.write(f"⚠️ Play Store scraper failed: {exc}")
                pb.empty()

            if scrape_appstore:
                status_box.update(label="📥 Scraping Apple App Store...")
                pb = st.progress(0, text="Fetching App Store reviews...")
                def app_cb(curr, total):
                    pb.progress(min(float(curr) / float(total), 1.0),
                                text=f"Fetched {curr}/{total} App Store reviews")
                try:
                    scraper = AppStoreScraper(progress_callback=app_cb, count=count, country=country)
                    df_app = scraper.scrape()
                    if not df_app.empty:
                        combined_dfs.append(df_app)
                        st.write(f"✅ App Store reviews collected: **{len(df_app):,}**")
                    else:
                        st.write("⚠️ App Store returned no data (library + RSS fallback both failed).")
                except Exception as exc:
                    st.write(f"⚠️ App Store scraper failed: {exc}")
                pb.empty()

            if scrape_reddit:
                status_box.update(label="📥 Scraping Reddit...")
                pb = st.progress(0, text="Searching Reddit...")
                try:
                    scraper = RedditScraper()
                    df_reddit = scraper.scrape()
                    if not df_reddit.empty:
                        combined_dfs.append(df_reddit)
                        st.write(f"✅ Reddit posts collected: **{len(df_reddit):,}**")
                    else:
                        st.write("⚠️ Reddit returned no data.")
                except Exception as exc:
                    st.write(f"⚠️ Reddit scraper failed: {exc}")
                pb.empty()

            if scrape_community:
                status_box.update(label="📥 Scraping Spotify Community Forum...")
                pb = st.progress(0, text="Crawling community.spotify.com...")
                try:
                    scraper = CommunityForumScraper()
                    df_forum = scraper.scrape()
                    if not df_forum.empty:
                        combined_dfs.append(df_forum)
                        st.write(f"✅ Community forum posts collected: **{len(df_forum):,}**")
                    else:
                        st.write("⚠️ Community forum returned no data.")
                except Exception as exc:
                    st.write(f"⚠️ Community forum scraper failed: {exc}")
                pb.empty()

            if combined_dfs:
                status_box.update(label="🧩 Merging and deduplicating...")
                raw = pd.concat(combined_dfs, ignore_index=True)
                if "review_text" in raw.columns:
                    raw["_tl"] = raw["review_text"].astype(str).str.lower().str.strip()
                    raw = raw.drop_duplicates(subset=["_tl"]).drop(columns=["_tl"])

                status_box.update(label="🧹 Applying quality filters...")
                raw, fstats = filter_reviews_dataframe(raw)
                if fstats["removed_total"] > 0:
                    st.write(
                        f"🧹 Removed **{fstats['removed_total']:,}** records "
                        f"({fstats['removed_emoji']:,} with emojis, "
                        f"{fstats['removed_short']:,} under {settings.MIN_REVIEW_WORD_COUNT} words). "
                        f"**{fstats['kept_total']:,}** kept."
                    )

                if raw.empty:
                    status_box.update(label="❌ No data after quality filters.", state="error")
                    st.error("All records removed by quality filter.")
                else:
                    st.session_state.raw_data = raw
                    raw.to_csv(scraped_data_path, index=False)
                    st.write(f"✅ Total unique records: **{len(raw):,}**")

                    status_box.update(label="🧠 Running NLP analysis...")
                    try:
                        engine = InsightsEngine()
                        analyzed = engine.run_full_analysis(raw)
                        st.session_state.analyzed_data = analyzed
                        save_analyzed_data(analyzed, analyzed_data_path)
                        clear_dashboard_cache()
                        st.session_state.topics   = engine.topic_modeler.get_topic_summary()
                        st.session_state.insights = engine.answer_strategic_questions(analyzed)
                        st.session_state.insights_version = dataset_version(analyzed)
                        status_box.update(label="✅ Analysis complete!", state="complete")
                        st.rerun()
                    except Exception as exc:
                        status_box.update(label="❌ Analysis failed.", state="error")
                        st.error(f"Analysis pipeline failed: {exc}")
            else:
                status_box.update(label="❌ No data collected.", state="error")
                st.error("No data collected. Check your internet connection.")

    # ── Welcome / summary ──────────────────────────────────────────────────────
    st.markdown("---")
    if not has_data:
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown("""
### Getting started

This tool pulls together what users are saying about Spotify's music discovery experience —
where recommendations fall short, why people replay the same tracks, and what they wish the product did differently.

#### How to run a pull
1. **Pick your sources** in the sidebar. Play Store + Reddit is a good first pass.
2. Click **Start Scraping & Analysis** above — it pulls as many reviews as possible.
3. Switch to **Dashboard** to explore findings, **Deep Dive** to search individual reviews,
   or **Strategic Insights** for question-by-question answers.

#### Where the data comes from
* **Play Store (India, English)** — Public reviews via `google-play-scraper`.
* **App Store (India, English)** — Public reviews via iTunes RSS.
* **Reddit** — Posts and comments from Spotify-related subreddits.
* **Community forum** — Recent public posts on `community.spotify.com`.
* **Quality filter** — Drops reviews with emojis or fewer than 4 words before analysis.
            """)
        with col2:
            st.markdown("""
<div class="spotify-card">
    <h4 style="color:#1DB954;margin-top:0;">Questions this answers</h4>
    <ol style="margin-bottom:0;padding-left:20px;line-height:1.8;">
        <li>Why do users struggle to discover new music?</li>
        <li>What frustrates people about recommendations?</li>
        <li>What listening habits are users trying to build?</li>
        <li>What keeps people in repetitive loops?</li>
        <li>Which segments hit different discovery problems?</li>
        <li>What unmet needs keep showing up?</li>
    </ol>
</div>
<div class="spotify-card" style="margin-top:15px;">
    <h4 style="color:#FFF;margin-top:0;">How reviews get tagged</h4>
    <ul style="margin-bottom:0;padding-left:20px;line-height:1.8;">
        <li><b>Sentiment</b> — Positive / neutral / negative (VADER).</li>
        <li><b>Themes</b> — Keyword rules for discovery, algorithm, playlists, etc.</li>
        <li><b>Topics</b> — Clusters by shared vocabulary (LDA).</li>
        <li><b>Tier</b> — Free vs Premium inferred from review text.</li>
    </ul>
</div>""", unsafe_allow_html=True)
    else:
        df_home = restore_analyzed_dataframe(st.session_state.analyzed_data.copy())
        exc_home = get_exec_summary(df_home)
        pain_home = exc_home.get("pain_themes", [])
        neg_home  = exc_home.get("negative_review_count", 0)
        top_pain_home = pain_home[0]["theme"] if pain_home else "—"

        ov_col, dl_col = st.columns([5, 1])
        with ov_col:
            st.markdown("### This run at a glance")
            if exc_home.get("headline"):
                st.caption(exc_home["headline"])
        with dl_col:
            st.download_button(
                label="⬇ Export",
                data=export_analyzed_dataframe_to_excel(df_home),
                file_name="spotify_analyzed_reviews.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="dl_home",
            )
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("Reviews", f"{len(df_home):,}")
        with c2: st.metric("Negative", f"{neg_home:,}")
        with c3: st.metric("% negative", f"{negative_pct(df_home):.1f}%")
        with c4: st.metric("Top pain", top_pain_home)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    if not has_data:
        st.warning("No data yet. Go to **Start Here** and run a scrape, or load cached data.")
        st.stop()

    df       = restore_analyzed_dataframe(st.session_state.analyzed_data.copy())
    topics   = st.session_state.get("topics", [])

    exec_summary     = get_exec_summary(df)
    segment_profiles = exec_summary.get("segment_profiles", [])
    pain_themes      = exec_summary.get("pain_themes", [])
    neg_count        = exec_summary.get("negative_review_count", 0)
    top_pain         = pain_themes[0]["theme"] if pain_themes else "None identified"
    total            = len(df)
    neg_pct_val      = negative_pct(df)
    src_count        = df["source"].nunique() if "source" in df.columns else 0

    # Title + export
    t_col, dl_col = st.columns([5, 1])
    with t_col:
        st.markdown(
            '<h2 style="margin:0 0 6px;font-size:24px;font-weight:800;">'
            'What Spotify users in India are saying about music discovery</h2>'
            '<p style="color:#666;font-size:13px;margin:0;">Play Store · App Store · Reddit · Community forums</p>',
            unsafe_allow_html=True,
        )
    with dl_col:
        st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)
        st.download_button(
            label="⬇ Export",
            data=export_analyzed_dataframe_to_excel(df),
            file_name="spotify_analyzed_reviews.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="dl_dashboard",
        )

    # KPI cards
    st.markdown(
        f"""<div class="kpi-row">
          <div class="kpi-card c-green"><p class="lbl">Reviews analyzed</p>
            <p class="val">{total:,}</p><p class="sub">{src_count} source{"s" if src_count!=1 else ""}</p></div>
          <div class="kpi-card c-red"><p class="lbl">Negative reviews</p>
            <p class="val">{neg_count:,}</p><p class="sub">Primary signal for pain areas</p></div>
          <div class="kpi-card c-amber"><p class="lbl">Share that is negative</p>
            <p class="val">{neg_pct_val:.1f}%</p><p class="sub">Of all reviews in this view</p></div>
          <div class="kpi-card c-purple"><p class="lbl">Biggest complaint</p>
            <p class="val">{escape_html(top_pain)}</p><p class="sub">By volume of negative mentions</p></div>
        </div>""",
        unsafe_allow_html=True,
    )
    if exec_summary.get("headline"):
        st.markdown(
            f'<div class="headline-banner">{escape_html(exec_summary["headline"])}</div>',
            unsafe_allow_html=True,
        )

    # Theme count helper
    def _tcnt(name: str, _df=df) -> int:
        col = f"theme_{name}"
        if col not in _df.columns: return 0
        base = _df[_df["sentiment_label"] == "Negative"] if "sentiment_label" in _df.columns else _df
        return int(base[col].astype(bool).sum())

    _disc  = _tcnt("Discovery Frustrations")
    _algo  = _tcnt("Algorithm Complaints")
    _play  = _tcnt("Playlist Issues")
    _div   = _tcnt("Content Diversity")
    _feat  = _tcnt("Feature Requests")
    _list  = _tcnt("Listening Behavior")
    _loop  = _disc + _algo
    _top_s = max(segment_profiles, key=lambda s: s["negative_review_count"], default=None) if segment_profiles else None

    # ── 6 Q&As ────────────────────────────────────────────────────────────────
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    _hdr("Overview", "green", "What the data is saying",
         "Six questions about music discovery, answered from the feedback — grounded in review volume, not assumptions.")

    _six = [
        ("Q1","Why do users struggle to discover new music?",
         f"The algorithm keeps serving what users already know. {_disc:,} negative reviews mention feeling stuck in the same rotation — users describe it as Spotify not taking risks."
         if _disc>0 else "Users report the app defaults to familiar artists and genres, leaving them unable to find music they haven't heard before."),
        ("Q2","What frustrates them most about recommendations?",
         f"{_algo:,} reviews name the recommendation algorithm directly — Discover Weekly feels predictable, Daily Mix recycles the same tracks, and Radio rarely surfaces anything genuinely new."
         if _algo>0 else "Recommendation features feel repetitive and too safe, rarely introducing music outside a user's comfort zone."),
        ("Q3","What are users actually trying to do when they listen?",
         f"{_list:,} reviews describe listening with a purpose — working, commuting, unwinding, exploring a genre. They want music that fits the moment, not just their history."
         if _list>0 else "Users want listening that matches their context — a study session, a workout, a mood — not a loop of songs they already know."),
        ("Q4","What causes them to keep replaying the same content?",
         f"Discovery features aren't surfacing enough variety. Across {_loop:,} negative reviews, users describe falling back on the same playlists not by choice, but because the alternatives feel worse."
         if _loop>0 else "Users replay familiar content as a default — not because they prefer it, but because they can't find anything better."),
        ("Q5","Which users feel this the most?",
         f"The loudest group is {_top_s.get('name','unknown')} — {_top_s.get('negative_review_count',0):,} negative reviews. Main frustration: {_top_s.get('top_pain_area','discovery')}."
         if _top_s else "Users who engage most actively with discovery features report the most frustration."),
        ("Q6","What do they wish Spotify would do instead?",
         f"{_feat+_div:,} reviews point to specific gaps — better genre exploration, smarter context awareness, and more control over what the algorithm considers new."
         if (_feat+_div)>0 else "Users consistently ask for more variety, smarter context-matching, and tools that help them explore deliberately."),
    ]
    ql, qr = st.columns(2)
    for i, (qnum, question, answer) in enumerate(_six):
        with (ql if i%2==0 else qr):
            st.markdown(
                f'<div class="qa-card"><div class="qa-num">{escape_html(qnum)}</div>'
                f'<div><p class="qa-q">{escape_html(question)}</p>'
                f'<p class="qa-a">{escape_html(answer)}</p></div></div>',
                unsafe_allow_html=True,
            )

    # ── Pain bars ──────────────────────────────────────────────────────────────
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    _hdr("Q1 · Q2","red","Where recommendations are breaking down",
         "Problems users name most when complaining about music discovery, ranked by volume of negative mentions.")

    _bar_data = []
    for col in [c for c in df.columns if c.startswith("theme_") and c!="theme_count"]:
        nm = col.replace("theme_","")
        cnt = int((df[col].astype(bool) & (df["sentiment_label"]=="Negative")).sum()) \
              if "sentiment_label" in df.columns else int(df[col].astype(bool).sum())
        if cnt > 0: _bar_data.append((nm, cnt))
    _bar_data.sort(key=lambda x: x[1], reverse=True)
    _pain_meta = {p["theme"]: p for p in exec_summary.get("pain_themes", [])}
    _max_bar   = _bar_data[0][1] if _bar_data else 1

    if _bar_data:
        for nm, cnt in _bar_data[:8]:
            w    = int(cnt / _max_bar * 100)
            meta = _pain_meta.get(nm, {})
            desc = escape_html(meta.get("description",""))
            pct  = meta.get("pct_of_negative",0)
            pct_lbl = f"{pct:.0f}% of negative reviews" if pct else f"{cnt:,} mentions"
            desc_html = f'<p class="pain-desc">{desc}</p>' if desc else ""
            st.markdown(
                f'<div class="pain-row"><div class="pain-left">'
                f'<p class="pain-name">{escape_html(nm)}</p>{desc_html}'
                f'<div class="pain-track"><div class="pain-fill" style="width:{w}%"></div></div>'
                f'</div><div class="pain-right">'
                f'<p class="pain-num">{cnt:,}</p><p class="pain-pct">{pct_lbl}</p>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No themed complaints found. Add more Reddit or community data.")

    # ── Repeat (Q4) ───────────────────────────────────────────────────────────
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    _hdr("Q4","red","What this leads to: users stuck on repeat",
         "The discovery gap has a behavioral outcome — users default to the familiar because the app doesn't offer a better path.")

    _rpt_cfg = [
        ("🔁","theme_Discovery Frustrations","Same songs, every time",
         "Users say they keep hearing the same artists and tracks — not by choice, but because nothing genuinely new surfaces."),
        ("🎯","theme_Algorithm Complaints","The algorithm plays it safe",
         "Discover Weekly, Daily Mix, and Radio get flagged for being predictable. Users feel Spotify optimizes for comfort, not curiosity."),
        ("📋","theme_Playlist Issues","Playlists that never feel fresh",
         "Auto-generated playlists feel static. Users return week after week to find the same songs."),
    ]
    _rpt_data = []
    for icon, col, title, desc in _rpt_cfg:
        if col in df.columns:
            cnt = int(df[col].astype(bool).sum())
            neg = int((df[col].astype(bool) & (df["sentiment_label"]=="Negative")).sum()) \
                  if "sentiment_label" in df.columns else 0
            if cnt > 0: _rpt_data.append((icon, title, desc, cnt, neg))

    if _rpt_data:
        rcols = st.columns(len(_rpt_data))
        for i, (icon, title, desc, cnt, neg) in enumerate(_rpt_data):
            with rcols[i]:
                neg_html = f'<p class="rpt-neg">↑ {neg:,} in negative reviews</p>' if neg else ""
                st.markdown(
                    f'<div class="rpt-card"><span class="rpt-icon">{icon}</span>'
                    f'<p class="rpt-title">{escape_html(title)}</p>'
                    f'<p class="rpt-desc">{escape_html(desc)}</p>'
                    f'<p class="rpt-num">{cnt:,}</p><p class="rpt-sub">total mentions</p>{neg_html}</div>',
                    unsafe_allow_html=True,
                )
    else:
        st.info("Add Reddit discussions to better quantify the repetitive listening pattern.")

    # ── Segments (Q5) ─────────────────────────────────────────────────────────
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    _hdr("Q5","blue","Who is feeling it most",
         "Four groups defined by where they post and what they complain about. One review can belong to multiple groups.")

    _seg_icons = ["🔍","📱","⭐","💬"]
    max_neg = max((p["negative_review_count"] for p in segment_profiles), default=1)
    scols   = st.columns(4)
    for i, profile in enumerate(segment_profiles[:4]):
        with scols[i]:
            cnt  = profile["negative_review_count"]
            barw = int(cnt / max_neg * 100)
            dim  = "dim" if cnt == 0 else ""
            st.markdown(
                f'<div class="seg-card {dim}"><div class="seg-icon">{_seg_icons[i]}</div>'
                f'<p class="seg-name">{escape_html(profile["name"])}</p>'
                f'<p class="seg-desc">{escape_html(profile["description"])}</p>'
                f'<p class="seg-num">{cnt:,}</p><p class="seg-nlbl">negative reviews</p>'
                f'<p class="seg-pct">{profile["pct_of_negative"]:.0f}% of all negative feedback</p>'
                f'<div class="seg-track"><div class="seg-fill" style="width:{barw}%"></div></div>'
                f'<p class="seg-pain">Main issue: <b>{escape_html(profile["top_pain_area"])}</b></p></div>',
                unsafe_allow_html=True,
            )

    # ── What they want (Q3+Q6) ────────────────────────────────────────────────
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    _hdr("Q3 · Q6","amber","What users actually want instead",
         "These aren't just complaints — users are describing gaps between what exists and what they need.")

    _want_cfg = [
        ("🎭","theme_Listening Behavior","Music that fits the moment",
         "Users listen with a purpose — working, commuting, a mood. They want Spotify to understand the context, not just replay their history."),
        ("🌍","theme_Content Diversity","More variety, less echo chamber",
         "Users feel the app only plays what they already know. They want to be genuinely surprised — not served a safer version of the familiar."),
        ("✨","theme_Feature Requests","Specific things they're asking for",
         "Better genre controls, smarter autoplay, the ability to define what new means for them."),
    ]
    _want_data = []
    for icon, col, title, desc in _want_cfg:
        if col in df.columns:
            cnt = int(df[col].astype(bool).sum())
            if cnt > 0: _want_data.append((icon, title, desc, cnt))

    if _want_data:
        wcols = st.columns(len(_want_data))
        for i, (icon, title, desc, cnt) in enumerate(_want_data):
            with wcols[i]:
                st.markdown(
                    f'<div class="want-card"><span class="want-icon">{icon}</span>'
                    f'<p class="want-title">{escape_html(title)}</p>'
                    f'<p class="want-desc">{escape_html(desc)}</p>'
                    f'<p class="want-num">{cnt:,}</p><p class="want-sub">mentions across all sources</p></div>',
                    unsafe_allow_html=True,
                )
    else:
        st.info("Add Reddit and community forum data to surface what users are asking for.")

    # ── Quotes ────────────────────────────────────────────────────────────────
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    _hdr("Voices","purple","In their own words",
         "Verbatim from the feedback — selected for carrying multiple pain signals, not for being the most extreme.")

    quotes = validation_quotes(df, n=5)
    if quotes:
        for q in quotes:
            st.markdown(
                f'<div class="quote-card"><div class="quote-mark">&ldquo;</div>'
                f'<p class="quote-text">{escape_html(q["text"])}</p>'
                f'<div class="quote-pills">'
                f'<span class="qpill src">{escape_html(q["source"])}</span>'
                f'<span class="qpill seg">{escape_html(q["segment"])}</span>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No negative quotes found in this run.")

    # ── Supporting charts ─────────────────────────────────────────────────────
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    with st.expander("Charts and supporting detail", expanded=False):
        charts     = ChartBuilder()
        wordclouds = WordCloudGenerator()
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(charts.sentiment_distribution(df), use_container_width=True)
        with c2: st.plotly_chart(charts.rating_distribution(df), use_container_width=True)
        c3, c4 = st.columns([3, 2])
        with c3: st.plotly_chart(charts.theme_prevalence(df, negative_only=True), use_container_width=True)
        with c4: st.plotly_chart(charts.source_comparison(df), use_container_width=True)
        c5, c6 = st.columns(2)
        with c5:
            st.markdown("**Most common words in the feedback**")
            all_text = " ".join(df["review_text"].dropna().astype(str).tolist())
            st.pyplot(wordclouds.generate(all_text, "Most common words"))
        with c6:
            st.plotly_chart(charts.rating_sentiment_scatter(df), use_container_width=True)
        st.markdown("**Discussion clusters**")
        st.caption("Groups of reviews sharing similar vocabulary.")
        if topics:
            st.plotly_chart(charts.topic_visualization(topics), use_container_width=True)
        else:
            st.caption("Not enough data to cluster into topics.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — DEEP DIVE
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    if not has_data:
        st.warning("No data yet. Go to **Start Here** and run a scrape, or load cached data.")
        st.stop()

    df_dd = restore_analyzed_dataframe(st.session_state.analyzed_data.copy())
    df_dd["date"] = pd.to_datetime(df_dd["date"], errors="coerce", utc=True).dt.tz_convert(None)

    st.markdown(
        '<h2 style="margin:0 0 4px;font-size:22px;font-weight:800;">Deep Dive</h2>'
        '<p style="color:#666;font-size:13px;margin:0 0 20px;">Search and filter individual reviews.</p>',
        unsafe_allow_html=True,
    )

    # ── Inline filter panel ────────────────────────────────────────────────────
    theme_list = list(settings.THEME_TAXONOMY.keys())

    with st.expander("🔎 Filters", expanded=True):
        fa, fb, fc = st.columns(3)
        with fa:
            search_query = st.text_input("Search review text", value="",
                                         placeholder="e.g. discover, algorithm, repeat")
            sources = df_dd["source"].unique().tolist()
            selected_sources = st.multiselect("Source", options=sources, default=sources)
        with fb:
            sentiments = ["Positive","Neutral","Negative"]
            selected_sentiments = st.multiselect("Sentiment", options=sentiments, default=sentiments)
            selected_themes = st.multiselect("Themes", options=theme_list, default=[])
        with fc:
            rated = df_dd["rating"].dropna()
            min_r = int(rated.min()) if not rated.empty else 1
            max_r = int(rated.max()) if not rated.empty else 5
            selected_ratings = st.slider("Store rating", min_value=1, max_value=5, value=(min_r, max_r))
            if "primary_user_segment" in df_dd.columns:
                seg_opts = sorted(df_dd["primary_user_segment"].dropna().unique().tolist())
                selected_segments = st.multiselect("Segment", options=seg_opts, default=seg_opts)
            else:
                selected_segments = []

        valid_dates = df_dd["date"].dropna()
        if not valid_dates.empty:
            min_date, max_date = valid_dates.min().date(), valid_dates.max().date()
            selected_dates = st.date_input("Date range", value=[min_date, max_date]) \
                             if min_date != max_date else None
        else:
            selected_dates = None

    # ── Apply filters ──────────────────────────────────────────────────────────
    fdf = df_dd.copy()
    if selected_sources:
        fdf = fdf[fdf["source"].isin(selected_sources)]
    else:
        fdf = fdf.iloc[0:0]
    if "primary_user_segment" in fdf.columns and selected_segments:
        fdf = fdf[fdf["primary_user_segment"].isin(selected_segments)]
    if selected_sentiments:
        fdf = fdf[fdf["sentiment_label"].isin(selected_sentiments)]
    else:
        fdf = fdf.iloc[0:0]
    if selected_ratings:
        store_mask = fdf["rating"].isna() | (
            (fdf["rating"] >= selected_ratings[0]) & (fdf["rating"] <= selected_ratings[1])
        )
        fdf = fdf[store_mask]
    if selected_themes:
        masks = [fdf[f"theme_{t}"].astype(bool) for t in selected_themes if f"theme_{t}" in fdf.columns]
        if masks:
            combined = masks[0]
            for m in masks[1:]: combined = combined | m
            fdf = fdf[combined]
    if selected_dates and len(selected_dates) == 2:
        fdf = fdf[
            (fdf["date"] >= pd.to_datetime(selected_dates[0])) &
            (fdf["date"] <= pd.to_datetime(selected_dates[1]))
        ]
    if search_query.strip():
        fdf = fdf[fdf["review_text"].astype(str).str.contains(search_query, case=False, na=False, regex=False)]

    # ── Pagination ─────────────────────────────────────────────────────────────
    filter_key = (search_query, tuple(selected_sources), tuple(selected_sentiments),
                  selected_ratings, tuple(selected_themes),
                  tuple(selected_dates) if selected_dates else None)
    if st.session_state.get("dd_filter_key") != filter_key:
        st.session_state.dd_page = 1
        st.session_state.dd_filter_key = filter_key

    items_per_page = 20
    total_items    = len(fdf)
    total_pages    = max(1, math.ceil(total_items / items_per_page))
    if "dd_page" not in st.session_state:
        st.session_state.dd_page = 1

    # Header row
    hr1, hr2, hr3, hr4 = st.columns([3, 1, 1, 1])
    with hr1:
        st.markdown(f"**{total_items:,}** reviews match your filters.")
    with hr2:
        if not fdf.empty:
            st.download_button("📥 CSV", data=export_dataframe_to_csv(fdf),
                               file_name="filtered_reviews.csv", mime="text/csv",
                               use_container_width=True, key="dl_dd_csv")
    with hr3:
        if not fdf.empty:
            st.download_button("📥 Excel", data=export_analyzed_dataframe_to_excel(fdf, sheet_name="Filtered"),
                               file_name="filtered_reviews.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True, key="dl_dd_xlsx")
    with hr4:
        pass  # spacer

    # Page controls
    pc1, pc2, pc3 = st.columns([1, 4, 1])
    with pc1:
        if st.button("⬅ Prev") and st.session_state.dd_page > 1:
            st.session_state.dd_page -= 1
    with pc3:
        if st.button("Next ➡") and st.session_state.dd_page < total_pages:
            st.session_state.dd_page += 1
    st.session_state.dd_page = max(1, min(st.session_state.dd_page, total_pages))
    with pc2:
        st.markdown(
            f'<div style="text-align:center;color:#666;margin-top:8px;">'
            f'Page <b>{st.session_state.dd_page}</b> of <b>{total_pages}</b></div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Review cards
    start_i = (st.session_state.dd_page - 1) * items_per_page
    end_i   = min(start_i + items_per_page, total_items)
    page_items = fdf.iloc[start_i:end_i]

    if page_items.empty:
        st.info("No reviews match your filters. Try relaxing them above.")
    else:
        for _, row in page_items.iterrows():
            rating_stars = "N/A"
            if pd.notna(row["rating"]) and row["rating"] > 0:
                stars = max(0, min(5, round(float(row["rating"]))))
                rating_stars = f"{'★'*stars}{'☆'*(5-stars)}"
            sent_val   = row["sentiment_compound"]
            sent_color = ("#1DB954" if row["sentiment_label"]=="Positive"
                          else "#E91429" if row["sentiment_label"]=="Negative"
                          else "#B3B3B3")
            themes_found = [t for t in theme_list if bool(row.get(f"theme_{t}", False))]
            theme_badges = "".join(
                f'<span class="theme-tag">{escape_html(settings.THEME_TAXONOMY[t]["icon"])} {escape_html(t)}</span>'
                for t in themes_found
            )
            date_str = row["date"].strftime("%Y-%m-%d") if pd.notna(row["date"]) else "Unknown"
            st.markdown(
                f'<div class="review-card">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
                f'<div><span class="source-badge">{escape_html(row["source"])}</span>'
                f'<span style="color:#FFC97E;font-weight:bold;margin-left:10px;font-family:monospace;">{rating_stars}</span></div>'
                f'<div style="font-weight:bold;color:{sent_color};">{escape_html(row["sentiment_label"])} ({sent_val:+.2f})</div>'
                f'</div>'
                f'<div style="font-size:12px;color:#666;margin-bottom:10px;">'
                f'{escape_html(str(row.get("username","")))} · {date_str}</div>'
                f'<p style="font-size:14px;margin-bottom:10px;line-height:1.6;">'
                f'"{escape_html(row["review_text"])}"</p>'
                f'<div>{theme_badges}</div></div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            f'<div style="text-align:center;color:#555;font-size:13px;">'
            f'Showing {start_i+1}–{end_i} of {total_items}</div>',
            unsafe_allow_html=True,
        )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — STRATEGIC INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    if not has_data:
        st.warning("No data yet. Go to **Start Here** and run a scrape, or load cached data.")
        st.stop()

    df_si   = restore_analyzed_dataframe(st.session_state.analyzed_data.copy())
    llm     = LLMAnalyzer()

    exc_si   = get_exec_summary(df_si)
    insights = get_insights(df_si, use_llm=llm.is_available())

    seg_si   = exc_si.get("segment_profiles", [])
    pain_si  = exc_si.get("pain_themes", [])

    si_t, si_dl = st.columns([5, 1])
    with si_t:
        st.markdown(
            '<h2 style="margin:0 0 6px;font-size:24px;font-weight:800;">Problems to validate</h2>'
            '<p style="color:#666;font-size:13px;margin:0;">Six discovery questions answered from the review data.</p>',
            unsafe_allow_html=True,
        )
        if exc_si.get("headline"):
            st.markdown(exc_si["headline"])
    with si_dl:
        st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)
        st.download_button(
            label="⬇ Export",
            data=export_insights_to_excel(df_si, insights, exc_si),
            file_name="spotify_strategic_insights.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="dl_insights",
        )

    if llm.is_available():
        st.caption("Answers use your OpenAI API key. Evidence comes from scraped data.")
    else:
        st.info("Add `OPENAI_API_KEY` to `.env` for AI-written answers. Rule-based summaries shown until then.")

    st.markdown("---")

    neg_si    = exc_si.get("negative_review_count", 0)
    total_si  = exc_si.get("total_reviews", len(df_si))
    g1, g2, g3 = st.columns(3)
    with g1: st.metric("Negative reviews", f"{neg_si:,}")
    with g2: st.metric("% of all feedback", f"{(neg_si/total_si*100) if total_si else 0:.1f}%")
    with g3: st.metric("Top pain area", pain_si[0]["theme"] if pain_si else "—")

    st.markdown("#### Key takeaways")
    for finding in exc_si.get("key_findings", []):
        st.markdown(f'<div class="finding-card">{escape_html(finding)}</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Four user segments")
    st.caption("Segments overlap — one review can count in more than one group.")

    si_seg_cols = st.columns(4)
    for idx, profile in enumerate(seg_si[:4]):
        with si_seg_cols[idx]:
            cnt = profile["negative_review_count"]
            dim = "opacity:0.55;" if cnt == 0 else ""
            st.markdown(
                f'<div class="segment-card" style="{dim}">'
                f'<strong style="color:#1DB954;">{escape_html(profile["name"])}</strong>'
                f'<p style="font-size:12px;color:#B3B3B3;margin:8px 0;">{escape_html(profile["description"])}</p>'
                f'<p style="font-size:22px;font-weight:bold;margin:0;">{cnt:,}'
                f'<span style="font-size:12px;color:#B3B3B3;font-weight:normal;"> negatives</span></p>'
                f'<p style="font-size:12px;color:#B3B3B3;margin:6px 0 0;">'
                f'{profile["pct_of_negative"]:.0f}% of negative feedback</p></div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")
    st.subheader("Answers by discovery question")

    for q_idx, q_ans in enumerate(insights):
        question = q_ans["question"]
        icon     = q_ans.get("icon","")
        problem  = q_ans.get("problem_statement","")
        answer   = q_ans.get("llm_answer", q_ans.get("summary",""))
        stats    = q_ans.get("key_stats", {})
        quotes_q = q_ans.get("quotes", [])
        segments = q_ans.get("segment_breakdown", [])

        with st.expander(f"{icon} {question}", expanded=(q_idx in (0, 3, 5))):
            st.markdown("**Answer**")
            st.markdown(f'<div class="answer-card">{escape_html(answer)}</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="problem-card"><strong>Underlying problem:</strong> {escape_html(problem)}</div>',
                unsafe_allow_html=True,
            )
            if segments:
                seg_line = " · ".join(
                    f"{escape_html(s['name'])} ({s['negative_review_count']})" for s in segments
                )
                st.markdown(f"**Most affected segments:** {seg_line}")
            st.markdown("**Evidence**")
            e1, e2, e3 = st.columns(3)
            with e1: st.metric("Negative reviews matched", f"{stats.get('total_relevant_reviews',0):,}")
            with e2: st.metric("% of all feedback", f"{stats.get('pct_of_total',0):.1f}%")
            with e3: st.metric("% of negatives", f"{stats.get('pct_of_negative',0):.1f}%")
            if quotes_q:
                st.markdown("**Quotes to validate**")
                for quote in quotes_q[:3]:
                    st.markdown(
                        f'<div class="quote-box">"{escape_html(quote["text"])}"<br/>'
                        f'<span style="font-size:10px;color:#888;font-style:normal;">'
                        f'{escape_html(quote["source"])}</span></div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No matching quotes in this run.")
