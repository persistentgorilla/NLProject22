"""
Spotify Review Discovery Engine – Dashboard
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

st.set_page_config(
    page_title="Dashboard · Spotify Discovery Engine",
    page_icon="📊",
    layout="wide",
)

# ── Design system ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Base ── */
.stApp { background-color: #0D0D0D !important; }
[data-testid="stSidebar"] { background-color: #111 !important; }
[data-testid="stSidebarContent"] { background-color: #111 !important; }
footer { display: none !important; }
[data-testid="stMetricValue"],
[data-testid="metric-container"] { display: none !important; }

/* ── Typography helpers ── */
.label {
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1.5px; color: #555; margin: 0 0 10px 0;
}

/* ── KPI row ── */
.kpi-row { display: grid; grid-template-columns: repeat(4,1fr); gap: 12px; margin: 20px 0 0; }
.kpi-card {
    border-radius: 14px; padding: 22px 20px 18px;
    background: #141414; border: 1px solid #1F1F1F;
    position: relative; overflow: hidden;
}
.kpi-card::before {
    content: ""; position: absolute; inset: 0 0 auto 0;
    height: 3px; border-radius: 14px 14px 0 0;
}
.kpi-card.c-green::before { background: linear-gradient(90deg,#1DB954,#169940); }
.kpi-card.c-red::before   { background: linear-gradient(90deg,#E91429,#9b0c1a); }
.kpi-card.c-amber::before { background: linear-gradient(90deg,#F5A623,#c47520); }
.kpi-card.c-purple::before{ background: linear-gradient(90deg,#7B61FF,#5040cc); }
.kpi-card .lbl { font-size:10px; text-transform:uppercase; letter-spacing:1.2px; color:#555; font-weight:700; margin:0 0 12px 0; }
.kpi-card .val { font-size:38px; font-weight:800; line-height:1; margin:0; }
.kpi-card .sub { font-size:11px; color:#555; margin:10px 0 0 0; }
.c-green .val { color:#1DB954; }
.c-red   .val { color:#E91429; }
.c-amber .val { color:#F5A623; }
.c-purple .val{ color:#A08FFF; font-size:18px !important; padding-top:8px; }

/* ── Section header ── */
.sec-hdr { margin: 52px 0 22px; }
.sec-tag {
    display: inline-block; font-size:10px; font-weight:700; letter-spacing:1.5px;
    text-transform:uppercase; padding:3px 12px; border-radius:20px; margin-bottom:12px;
}
.sec-tag.green  { background:#1DB95420; color:#1DB954; }
.sec-tag.red    { background:#E9142920; color:#E91429; }
.sec-tag.amber  { background:#F5A62320; color:#F5A623; }
.sec-tag.blue   { background:#4A9EFF20; color:#4A9EFF; }
.sec-tag.purple { background:#7B61FF20; color:#A08FFF; }
.sec-title { font-size:22px; font-weight:700; margin:0 0 6px; color:#F0F0F0; }
.sec-sub   { font-size:13px; color:#666; margin:0; line-height:1.55; }

/* ── Divider ── */
.divider {
    height:1px; border:none; margin:40px 0;
    background:linear-gradient(90deg,transparent,#252525,transparent);
}

/* ── Headline banner ── */
.headline-banner {
    background:#141414; border:1px solid #222; border-left:3px solid #1DB954;
    border-radius:0 10px 10px 0; padding:14px 20px;
    font-size:14px; color:#B0B0B0; line-height:1.65; margin-bottom:4px;
}

/* ── Q&A cards ── */
.qa-card {
    background:#121212; border:1px solid #1E1E1E; border-radius:12px;
    padding:18px 20px; margin-bottom:10px;
    display:flex; gap:16px; align-items:flex-start;
}
.qa-num {
    font-size:10px; font-weight:800; color:#1DB954;
    background:#1DB95420; border-radius:6px;
    padding:4px 8px; flex-shrink:0; letter-spacing:0.5px; margin-top:1px;
}
.qa-q { font-size:14px; font-weight:600; color:#DEDEDE; margin:0 0 7px; }
.qa-a { font-size:13px; color:#888; margin:0; line-height:1.65; }

/* ── Pain bars ── */
.pain-row {
    background:#121212; border:1px solid #1E1E1E; border-radius:11px;
    padding:15px 20px; display:flex; align-items:center; gap:18px; margin-bottom:8px;
}
.pain-left  { flex:1; min-width:0; }
.pain-name  { font-size:14px; font-weight:600; color:#E0E0E0; margin:0 0 3px; }
.pain-desc  { font-size:12px; color:#555; margin:0 0 10px; }
.pain-track { background:#1C1C1C; border-radius:4px; height:6px; }
.pain-fill  { height:6px; border-radius:4px; background:linear-gradient(90deg,#E91429,#FF6B6B); }
.pain-right { text-align:right; flex-shrink:0; min-width:80px; }
.pain-num   { font-size:24px; font-weight:700; color:#E91429; margin:0; line-height:1; }
.pain-pct   { font-size:11px; color:#555; margin:4px 0 0; }

/* ── Repeat cards ── */
.rpt-card {
    background:linear-gradient(160deg,#160808,#1A0C0C);
    border:1px solid #331515; border-radius:14px; padding:24px 20px;
    height:100%; box-sizing:border-box;
}
.rpt-icon  { font-size:28px; margin-bottom:12px; display:block; }
.rpt-title { font-size:14px; font-weight:700; color:#FF8080; margin:0 0 8px; }
.rpt-desc  { font-size:12px; color:#6B4444; line-height:1.6; margin:0 0 18px; }
.rpt-num   { font-size:34px; font-weight:800; color:#FF6B6B; margin:0; line-height:1; }
.rpt-sub   { font-size:11px; color:#553333; margin:4px 0 0; }
.rpt-neg   { font-size:12px; color:#E91429; font-weight:600; margin:8px 0 0; }

/* ── Segment cards ── */
.seg-card {
    background:linear-gradient(160deg,#141414,#181818);
    border:1px solid #222; border-radius:14px; padding:22px 18px;
    height:100%; box-sizing:border-box;
}
.seg-card.dim { opacity:.38; }
.seg-icon {
    width:42px; height:42px; border-radius:10px;
    background:#1DB95420; display:flex; align-items:center;
    justify-content:center; font-size:20px; margin-bottom:16px;
}
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
.want-card {
    background:linear-gradient(160deg,#0C1A10,#101E14);
    border:1px solid #1A3320; border-radius:14px; padding:24px 20px;
    height:100%; box-sizing:border-box;
}
.want-icon  { font-size:28px; margin-bottom:12px; display:block; }
.want-title { font-size:14px; font-weight:700; color:#57C878; margin:0 0 8px; }
.want-desc  { font-size:12px; color:#3D6B4A; line-height:1.65; margin:0 0 18px; }
.want-num   { font-size:32px; font-weight:800; color:#1DB954; margin:0; line-height:1; }
.want-sub   { font-size:11px; color:#2D5236; margin:4px 0 0; }

/* ── Quote cards ── */
.quote-card {
    background:#0F0F0F; border:1px solid #1C1C1C; border-radius:12px;
    padding:22px 24px 18px; margin-bottom:10px; position:relative;
}
.quote-mark {
    font-size:64px; font-family:Georgia,serif; color:#1DB95428;
    line-height:1; position:absolute; top:10px; left:16px; margin:0;
}
.quote-text {
    font-size:14px; color:#C8C8C8; line-height:1.75; font-style:italic;
    margin:0 0 14px; padding-left:44px;
}
.quote-pills { display:flex; gap:7px; align-items:center; padding-left:44px; flex-wrap:wrap; }
.qpill {
    font-size:10px; font-weight:600; letter-spacing:0.4px;
    padding:3px 10px; border-radius:12px;
}
.qpill.src    { background:#1A2E1A; color:#57C878; }
.qpill.seg    { background:#1C1C1C; color:#777; }
.qpill.tier   { background:#1A1A2E; color:#A08FFF; }

/* ── Callout card ── */
.callout {
    background:linear-gradient(135deg,#0A1E0F,#0F2214);
    border:1px solid #1DB95430; border-radius:16px; padding:30px 32px;
    position:relative; overflow:hidden;
}
.callout::after {
    content:""; position:absolute; bottom:-40px; right:-40px;
    width:140px; height:140px; border-radius:50%; background:#1DB95412;
}
.callout-badge {
    display:inline-block; font-size:10px; font-weight:700; letter-spacing:1.5px;
    text-transform:uppercase; color:#1DB954; background:#1DB95418;
    padding:4px 12px; border-radius:20px; margin-bottom:16px;
}
.callout-name  { font-size:24px; font-weight:700; margin:0 0 8px; }
.callout-desc  { font-size:13px; color:#4E7A58; margin:0 0 22px; line-height:1.55; }
.callout-stats { display:flex; gap:32px; flex-wrap:wrap; margin-bottom:20px; }
.cs-val   { font-size:30px; font-weight:700; color:#1DB954; margin:0; line-height:1; }
.cs-lbl   { font-size:11px; color:#3A5E42; margin:5px 0 0; }
.cs-str   { font-size:16px; font-weight:600; color:#1DB954; padding-top:7px; }
.callout-q {
    background:#0A160C; border-left:3px solid #1DB95450;
    border-radius:0 8px 8px 0; padding:14px 18px;
    font-size:13px; color:#5E8A68; font-style:italic; line-height:1.65;
}

/* ── Expander override ── */
details[data-baseweb="accordion"] {
    background:#111 !important; border:1px solid #222 !important;
    border-radius:12px !important;
}
</style>
""", unsafe_allow_html=True)

# ── Session defaults ───────────────────────────────────────────────────────────
for _k, _v in (("raw_data", pd.DataFrame()), ("analyzed_data", pd.DataFrame()),
                ("topics", []), ("insights", [])):
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Header ─────────────────────────────────────────────────────────────────────
h_title, h_reset, h_export = st.columns([5, 0.85, 0.85])
with h_title:
    st.markdown("""
    <h1 style="margin:0 0 8px;font-size:26px;font-weight:800;color:#F2F2F2;">
        What Spotify users in India are saying about music discovery
    </h1>
    <p style="color:#555;font-size:13px;margin:0;">
        Play Store · App Store · Reddit · Community forums — analyzed for discovery &amp; listening pain points
    </p>
    """, unsafe_allow_html=True)
with h_reset:
    st.markdown("<div style='margin-top:18px'></div>", unsafe_allow_html=True)
    if st.button("↺  Reset", use_container_width=True,
                 help="Clears all data and starts fresh."):
        reset_app_state()
        st.rerun()

# ── Guard: no data ─────────────────────────────────────────────────────────────
has_data = "analyzed_data" in st.session_state and not st.session_state.analyzed_data.empty
if not has_data:
    st.markdown("<div style='margin-top:40px'></div>", unsafe_allow_html=True)
    st.warning("No data yet. Run a scrape from the home page, or load a saved export.")
    st.stop()

# ── Load & filter ──────────────────────────────────────────────────────────────
df_full = restore_analyzed_dataframe(st.session_state.analyzed_data.copy())
topics  = st.session_state.get("topics", [])

tier_filter = render_tier_toggle()
counts = tier_counts(df_full)
st.caption(
    f"Tier inferred from review text — not Spotify account data: "
    f"**{counts['free']:,}** likely Free · **{counts['premium']:,}** likely Premium · "
    f"**{counts['unclassified']:,}** unclear"
)

df = prepare_dashboard_df(df_full, tier_filter)
if tier_filter != TIER_ALL and df.empty:
    st.warning(
        f"No reviews matched **{TIER_LABELS[tier_filter]}**. "
        "Switch to **All users** or scrape more feedback mentioning free/premium."
    )
    st.stop()

view_label = TIER_LABELS[tier_filter]

# Export button (needs df)
with h_export:
    st.markdown("<div style='margin-top:18px'></div>", unsafe_allow_html=True)
    st.download_button(
        label="⬇  Export",
        data=export_analyzed_dataframe_to_excel(df),
        file_name="spotify_analyzed_reviews.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# ── Exec summary ───────────────────────────────────────────────────────────────
exec_summary     = get_exec_summary(df, tier_filter)
segment_profiles = exec_summary.get("segment_profiles", [])
pain_themes      = exec_summary.get("pain_themes", [])
neg_count        = exec_summary.get("negative_review_count", 0)
top_pain         = pain_themes[0]["theme"] if pain_themes else "None identified"
total            = len(df)
neg_pct_val      = negative_pct(df)
src_count        = df["source"].nunique() if "source" in df.columns else 0

# ── KPI row ────────────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div class="kpi-row">
      <div class="kpi-card c-green">
        <p class="lbl">Reviews analyzed</p>
        <p class="val">{total:,}</p>
        <p class="sub">{view_label} · {src_count} source{"s" if src_count != 1 else ""}</p>
      </div>
      <div class="kpi-card c-red">
        <p class="lbl">Negative reviews</p>
        <p class="val">{neg_count:,}</p>
        <p class="sub">Primary signal for pain areas</p>
      </div>
      <div class="kpi-card c-amber">
        <p class="lbl">Share that is negative</p>
        <p class="val">{neg_pct_val:.1f}%</p>
        <p class="sub">Of all reviews in this view</p>
      </div>
      <div class="kpi-card c-purple">
        <p class="lbl">Biggest complaint</p>
        <p class="val">{escape_html(top_pain)}</p>
        <p class="sub">By volume of negative mentions</p>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

headline = exec_summary.get("headline", "")
if headline:
    st.markdown(
        f'<div class="headline-banner">{escape_html(headline)}</div>',
        unsafe_allow_html=True,
    )

# ── Theme count helper ─────────────────────────────────────────────────────────
def _tcnt(name: str) -> int:
    col = f"theme_{name}"
    if col not in df.columns:
        return 0
    base = df[df["sentiment_label"] == "Negative"] if "sentiment_label" in df.columns else df
    return int(base[col].astype(bool).sum())

_disc  = _tcnt("Discovery Frustrations")
_algo  = _tcnt("Algorithm Complaints")
_play  = _tcnt("Playlist Issues")
_div   = _tcnt("Content Diversity")
_feat  = _tcnt("Feature Requests")
_list  = _tcnt("Listening Behavior")
_loop  = _disc + _algo
_top_s = max(segment_profiles, key=lambda s: s["negative_review_count"], default=None) if segment_profiles else None

# ── Section header helper ──────────────────────────────────────────────────────
def _hdr(tag: str, color: str, title: str, sub: str = "") -> None:
    sub_html = f'<p class="sec-sub">{escape_html(sub)}</p>' if sub else ""
    st.markdown(
        f'<div class="sec-hdr">'
        f'<span class="sec-tag {color}">{escape_html(tag)}</span>'
        f'<h2 class="sec-title">{escape_html(title)}</h2>'
        f'{sub_html}</div>',
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════════════════════════════════════
# SECTION: Overview — 6 Q&As
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<hr class="divider">', unsafe_allow_html=True)
_hdr("Overview", "green",
     "What the data is saying",
     "Six questions about music discovery, answered from the feedback — grounded in review volume, not assumptions.")

_six = [
    ("Q1", "Why do users struggle to discover new music?",
     f"The algorithm keeps serving what users already know. {_disc:,} negative reviews mention feeling stuck "
     f"in the same rotation — users describe it as Spotify not taking risks on their behalf."
     if _disc > 0 else
     "Users report the app defaults to familiar artists and genres, leaving them unable to find music they haven't heard before."),

    ("Q2", "What frustrates them most about recommendations?",
     f"{_algo:,} reviews name the recommendation algorithm directly — Discover Weekly feels predictable, "
     f"Daily Mix recycles the same tracks, and Radio rarely surfaces anything genuinely new."
     if _algo > 0 else
     "Recommendation features feel repetitive and too safe, rarely introducing music outside a user's comfort zone."),

    ("Q3", "What are users actually trying to do when they listen?",
     f"{_list:,} reviews describe listening with a purpose — working, commuting, unwinding, exploring a genre. "
     f"They want music that fits the moment, not just their listening history."
     if _list > 0 else
     "Users want listening that matches their context — a study session, a workout, a mood — not a loop of songs they already know."),

    ("Q4", "What causes them to keep replaying the same content?",
     f"Discovery features aren't surfacing enough variety. Across {_loop:,} negative reviews, users describe "
     f"falling back on the same playlists not by choice, but because the alternatives feel worse."
     if _loop > 0 else
     "Users replay familiar content as a default — not because they prefer it, but because they can't find anything better."),

    ("Q5", "Which users feel this the most?",
     f"The loudest group is {_top_s.get('name','unknown')} — {_top_s.get('negative_review_count',0):,} negative reviews. "
     f"Main frustration: {_top_s.get('top_pain_area','discovery')}."
     if _top_s else
     "Users who engage most actively with discovery features — playlist listeners and app store reviewers — report the most frustration."),

    ("Q6", "What do they wish Spotify would do instead?",
     f"{_feat + _div:,} reviews point to specific gaps — better genre exploration, smarter context awareness, "
     f"and more control over what the algorithm considers new for them."
     if (_feat + _div) > 0 else
     "Users consistently ask for more variety, smarter context-matching, and tools that help them explore deliberately."),
]

col_l, col_r = st.columns(2)
for i, (qnum, question, answer) in enumerate(_six):
    with (col_l if i % 2 == 0 else col_r):
        st.markdown(
            f'<div class="qa-card">'
            f'  <div class="qa-num">{escape_html(qnum)}</div>'
            f'  <div>'
            f'    <p class="qa-q">{escape_html(question)}</p>'
            f'    <p class="qa-a">{escape_html(answer)}</p>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )

# ══════════════════════════════════════════════════════════════════════════════
# SECTION: Pain bars — where recommendations break down (Q1+Q2)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<hr class="divider">', unsafe_allow_html=True)
_hdr("Q1 · Q2", "red",
     "Where recommendations are breaking down",
     "Problems users name most when complaining about music discovery, ranked by volume of negative mentions.")

_all_theme_cols = [c for c in df.columns if c.startswith("theme_") and c != "theme_count"]
_bar_data = []
for col in _all_theme_cols:
    name = col.replace("theme_", "")
    if "sentiment_label" in df.columns:
        cnt = int((df[col].astype(bool) & (df["sentiment_label"] == "Negative")).sum())
    else:
        cnt = int(df[col].astype(bool).sum())
    if cnt > 0:
        _bar_data.append((name, cnt))
_bar_data.sort(key=lambda x: x[1], reverse=True)

_pain_meta = {p["theme"]: p for p in exec_summary.get("pain_themes", [])}
_max_bar   = _bar_data[0][1] if _bar_data else 1

if _bar_data:
    for name, cnt in _bar_data[:8]:
        w    = int(cnt / _max_bar * 100)
        meta = _pain_meta.get(name, {})
        desc = escape_html(meta.get("description", ""))
        pct  = meta.get("pct_of_negative", 0)
        pct_lbl = f"{pct:.0f}% of negative reviews" if pct else f"{cnt:,} mentions"
        desc_html = f'<p class="pain-desc">{desc}</p>' if desc else ""
        st.markdown(
            f'<div class="pain-row">'
            f'  <div class="pain-left">'
            f'    <p class="pain-name">{escape_html(name)}</p>'
            f'    {desc_html}'
            f'    <div class="pain-track"><div class="pain-fill" style="width:{w}%"></div></div>'
            f'  </div>'
            f'  <div class="pain-right">'
            f'    <p class="pain-num">{cnt:,}</p>'
            f'    <p class="pain-pct">{pct_lbl}</p>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )
else:
    st.info("No themed complaints found. Add more Reddit or community data.")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION: Stuck on repeat (Q4)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<hr class="divider">', unsafe_allow_html=True)
_hdr("Q4", "red",
     "What this leads to: users stuck on repeat",
     "The discovery gap has a behavioral outcome — users default to the familiar because the app doesn't offer a better path.")

_rpt_cfg = [
    ("🔁", "theme_Discovery Frustrations", "Same songs, every time",
     "Users say they keep hearing the same artists and tracks — not by choice, but because nothing genuinely new surfaces."),
    ("🎯", "theme_Algorithm Complaints", "The algorithm plays it safe",
     "Discover Weekly, Daily Mix, and Radio get flagged for being predictable. Users feel Spotify optimizes for comfort, not curiosity."),
    ("📋", "theme_Playlist Issues", "Playlists that never feel fresh",
     "Auto-generated playlists feel static. Users return week after week to find the same songs in the same order."),
]

_rpt_data = []
for icon, col, title, desc in _rpt_cfg:
    if col in df.columns:
        cnt = int(df[col].astype(bool).sum())
        neg = int((df[col].astype(bool) & (df["sentiment_label"] == "Negative")).sum()) \
              if "sentiment_label" in df.columns else 0
        if cnt > 0:
            _rpt_data.append((icon, title, desc, cnt, neg))

if _rpt_data:
    rcols = st.columns(len(_rpt_data))
    for i, (icon, title, desc, cnt, neg) in enumerate(_rpt_data):
        with rcols[i]:
            neg_html = f'<p class="rpt-neg">↑ {neg:,} in negative reviews</p>' if neg else ""
            st.markdown(
                f'<div class="rpt-card">'
                f'  <span class="rpt-icon">{icon}</span>'
                f'  <p class="rpt-title">{escape_html(title)}</p>'
                f'  <p class="rpt-desc">{escape_html(desc)}</p>'
                f'  <p class="rpt-num">{cnt:,}</p>'
                f'  <p class="rpt-sub">total mentions</p>'
                f'  {neg_html}'
                f'</div>',
                unsafe_allow_html=True,
            )
else:
    st.info("Add Reddit discussions to better quantify the repetitive listening pattern.")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION: User segments (Q5)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<hr class="divider">', unsafe_allow_html=True)
_hdr("Q5", "blue",
     "Who is feeling it most",
     "Four groups defined by where they post and what they complain about. One review can belong to multiple groups.")

_seg_icons = ["🔍", "📱", "⭐", "💬"]
max_neg = max((p["negative_review_count"] for p in segment_profiles), default=1)
scols   = st.columns(4)

for i, profile in enumerate(segment_profiles[:4]):
    with scols[i]:
        cnt  = profile["negative_review_count"]
        barw = int(cnt / max_neg * 100)
        dim  = "dim" if cnt == 0 else ""
        st.markdown(
            f'<div class="seg-card {dim}">'
            f'  <div class="seg-icon">{_seg_icons[i]}</div>'
            f'  <p class="seg-name">{escape_html(profile["name"])}</p>'
            f'  <p class="seg-desc">{escape_html(profile["description"])}</p>'
            f'  <p class="seg-num">{cnt:,}</p>'
            f'  <p class="seg-nlbl">negative reviews</p>'
            f'  <p class="seg-pct">{profile["pct_of_negative"]:.0f}% of all negative feedback</p>'
            f'  <div class="seg-track"><div class="seg-fill" style="width:{barw}%"></div></div>'
            f'  <p class="seg-pain">Main issue: <b>{escape_html(profile["top_pain_area"])}</b></p>'
            f'</div>',
            unsafe_allow_html=True,
        )

# ══════════════════════════════════════════════════════════════════════════════
# SECTION: What users want instead (Q3+Q6)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<hr class="divider">', unsafe_allow_html=True)
_hdr("Q3 · Q6", "amber",
     "What users actually want instead",
     "These aren't just complaints — users are describing gaps between what exists and what they need.")

_want_cfg = [
    ("🎭", "theme_Listening Behavior", "Music that fits the moment",
     "Users listen with a purpose — working, commuting, a mood, an activity. "
     "They want Spotify to understand the context, not just replay their history."),
    ("🌍", "theme_Content Diversity", "More variety, less echo chamber",
     "Users feel the app only plays what they already know. "
     "They want to be genuinely surprised — not served a safer version of the familiar."),
    ("✨", "theme_Feature Requests", "Specific things they're asking for",
     "Better genre controls, smarter autoplay, the ability to define what new means for them. "
     "These are gaps users have already articulated — in their own words."),
]

_want_data = []
for icon, col, title, desc in _want_cfg:
    if col in df.columns:
        cnt = int(df[col].astype(bool).sum())
        if cnt > 0:
            _want_data.append((icon, title, desc, cnt))

if _want_data:
    wcols = st.columns(len(_want_data))
    for i, (icon, title, desc, cnt) in enumerate(_want_data):
        with wcols[i]:
            st.markdown(
                f'<div class="want-card">'
                f'  <span class="want-icon">{icon}</span>'
                f'  <p class="want-title">{escape_html(title)}</p>'
                f'  <p class="want-desc">{escape_html(desc)}</p>'
                f'  <p class="want-num">{cnt:,}</p>'
                f'  <p class="want-sub">mentions across all sources</p>'
                f'</div>',
                unsafe_allow_html=True,
            )
else:
    st.info("Add Reddit and community forum data to surface what users are asking for.")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION: Quotes
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<hr class="divider">', unsafe_allow_html=True)
_hdr("Voices", "purple",
     "In their own words",
     "Verbatim from the feedback — selected for carrying multiple pain signals, not for being the most extreme.")

quotes = validation_quotes(df, n=5)
if quotes:
    for q in quotes:
        tier_pill = (
            f'<span class="qpill tier">{escape_html(q["tier"])}</span>'
            if q.get("tier") not in ("unclassified", None, "") else ""
        )
        st.markdown(
            f'<div class="quote-card">'
            f'  <div class="quote-mark">&ldquo;</div>'
            f'  <p class="quote-text">{escape_html(q["text"])}</p>'
            f'  <div class="quote-pills">'
            f'    <span class="qpill src">{escape_html(q["source"])}</span>'
            f'    <span class="qpill seg">{escape_html(q["segment"])}</span>'
            f'    {tier_pill}'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )
else:
    st.info("No negative quotes found in this run.")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION: Top segment focus
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<hr class="divider">', unsafe_allow_html=True)
_hdr("Focus", "green",
     "The group most worth understanding better",
     "Highest volume of negative feedback, clearest pain signal, most distinct complaint pattern.")

_active = [p for p in segment_profiles if p["negative_review_count"] > 0]
if _active:
    top = max(_active, key=lambda s: s["negative_review_count"])
    sq  = f'<div class="callout-q">&ldquo;{escape_html(top["sample_quote"])}&rdquo;</div>' \
          if top.get("sample_quote") else ""
    st.markdown(
        f'<div class="callout">'
        f'  <span class="callout-badge">Highest signal group</span>'
        f'  <h3 class="callout-name">{escape_html(top["name"])}</h3>'
        f'  <p class="callout-desc">{escape_html(top["description"])}</p>'
        f'  <div class="callout-stats">'
        f'    <div><p class="cs-val">{top["negative_review_count"]:,}</p><p class="cs-lbl">negative reviews</p></div>'
        f'    <div><p class="cs-val">{top["pct_of_negative"]:.0f}%</p><p class="cs-lbl">of all negative feedback</p></div>'
        f'    <div><p class="cs-str">{escape_html(top["top_pain_area"])}</p><p class="cs-lbl">main frustration</p></div>'
        f'  </div>'
        f'  {sq}'
        f'</div>',
        unsafe_allow_html=True,
    )
    others = [s for s in _active if s["id"] != top["id"]]
    if others:
        ru = others[0]
        st.caption(
            f"Runner-up: **{ru['name']}** — {ru['negative_review_count']:,} negative reviews, "
            f"main issue: {ru['top_pain_area']}."
        )
else:
    st.info("Scrape more feedback to identify which group has the clearest pain signal.")

st.markdown("<div style='margin-top:24px'></div>", unsafe_allow_html=True)
st.page_link("pages/4_💡_Strategic_Insights.py",
             label="See the full analysis behind each question →")

# ══════════════════════════════════════════════════════════════════════════════
# Supporting charts (collapsed)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<hr class="divider">', unsafe_allow_html=True)
with st.expander("Charts and supporting detail", expanded=False):
    charts     = ChartBuilder()
    wordclouds = WordCloudGenerator()

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(charts.sentiment_distribution(df), use_container_width=True)
    with c2:
        st.plotly_chart(charts.rating_distribution(df), use_container_width=True)

    c3, c4 = st.columns([3, 2])
    with c3:
        st.plotly_chart(charts.theme_prevalence(df, negative_only=True), use_container_width=True)
    with c4:
        st.plotly_chart(charts.source_comparison(df), use_container_width=True)

    c5, c6 = st.columns(2)
    with c5:
        st.markdown("**Most common words in the feedback**")
        all_text = " ".join(df["review_text"].dropna().astype(str).tolist())
        st.pyplot(wordclouds.generate(all_text, "Most common words"))
    with c6:
        st.plotly_chart(charts.rating_sentiment_scatter(df), use_container_width=True)

    st.markdown("**Discussion clusters**")
    st.caption("Groups of reviews sharing similar vocabulary — useful for spotting compound pain points.")
    if topics:
        st.plotly_chart(charts.topic_visualization(topics), use_container_width=True)
    else:
        st.caption("Not enough data to cluster into topics.")
