"""
Spotify Review Discovery Engine - Strategic Insights Page
Plain-language answers for business validation.
"""

import sys
import streamlit as st

sys.path.insert(0, ".")

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from analysis import LLMAnalyzer
from utils.html import escape_html
from utils.data_io import restore_analyzed_dataframe, export_insights_to_excel
from utils.dashboard_context import (
    get_exec_summary,
    get_insights,
    validation_quotes,
    negative_pct,
    prepare_dashboard_df,
    render_tier_toggle,
)
from utils.tier_inference import TIER_ALL, TIER_LABELS, tier_counts

st.set_page_config(
    page_title="Strategic Insights - Spotify Review Engine",
    page_icon="💡",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp { background-color: #121212; color: #FFFFFF; }
    .segment-card, .theme-metric {
        background-color: #1E1E1E;
        border: 1px solid #282828;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .finding-card {
        background-color: #1A1A1A;
        border-left: 4px solid #1DB954;
        padding: 12px 15px;
        margin-bottom: 10px;
        border-radius: 0 8px 8px 0;
        line-height: 1.55;
    }
    .answer-card {
        background-color: #142818;
        border-left: 4px solid #1DB954;
        padding: 14px 16px;
        margin: 12px 0 16px 0;
        border-radius: 0 8px 8px 0;
        line-height: 1.6;
        font-size: 15px;
    }
    .problem-card {
        background-color: #241818;
        border-left: 4px solid #E91429;
        padding: 10px 14px;
        margin-bottom: 10px;
        border-radius: 0 8px 8px 0;
    }
    .quote-box {
        background-color: #282828;
        border-left: 3px solid #B3B3B3;
        font-style: italic;
        padding: 10px 15px;
        margin-bottom: 10px;
        border-radius: 0 4px 4px 0;
        font-size: 13px;
        line-height: 1.5;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "analyzed_data" not in st.session_state or st.session_state.analyzed_data.empty:
    st.warning("No data yet. Run a scrape from the home page, or load a saved export.")
    st.stop()

df_full = restore_analyzed_dataframe(st.session_state.analyzed_data.copy())
llm = LLMAnalyzer()

tier_filter = render_tier_toggle()
df = prepare_dashboard_df(df_full, tier_filter)
if tier_filter != TIER_ALL and df.empty:
    st.warning(
        f"No reviews matched **{TIER_LABELS[tier_filter]}** in this run. "
        "Switch to **All users** on the Dashboard or scrape more tier-related feedback."
    )
    st.stop()

exec_summary = get_exec_summary(df, tier_filter)
insights = get_insights(df, tier_filter, use_llm=llm.is_available())

segment_profiles = exec_summary.get("segment_profiles", [])
pain_themes = exec_summary.get("pain_themes", [])

title_col, export_col = st.columns([5, 1])
with title_col:
    st.title("Problems to validate")
    st.markdown(
        "Six questions about music discovery and repetitive listening — answered from the review data."
    )
    if exec_summary.get("headline"):
        st.markdown(exec_summary["headline"])
with export_col:
    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
    st.download_button(
        label="Export Excel",
        data=export_insights_to_excel(df, insights, exec_summary),
        file_name="spotify_strategic_insights.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

if llm.is_available():
    st.caption("Answers use your OpenAI API key. Evidence (counts, segments, quotes) comes from the scraped data.")
else:
    st.info("Add `OPENAI_API_KEY` to `.env` for AI-written answers. Rule-based summaries are shown until then.")

st.markdown("---")

neg_count = exec_summary.get("negative_review_count", 0)
total_reviews = exec_summary.get("total_reviews", len(df))
g1, g2, g3 = st.columns(3)
with g1:
    st.metric("Negative reviews", f"{neg_count:,}")
with g2:
    pct_neg = (neg_count / total_reviews * 100) if total_reviews else 0
    st.metric("% of all feedback", f"{pct_neg:.1f}%")
with g3:
    st.metric("Top pain area", pain_themes[0]["theme"] if pain_themes else "—")

st.markdown("#### Key takeaways")
for finding in exec_summary.get("key_findings", []):
    st.markdown(f'<div class="finding-card">{escape_html(finding)}</div>', unsafe_allow_html=True)

st.markdown("---")
st.subheader("Four user segments")
st.caption("Segments overlap — one review can count in more than one group.")

seg_cols = st.columns(4)
for idx, profile in enumerate(segment_profiles[:4]):
    with seg_cols[idx]:
        count = profile["negative_review_count"]
        dim = "opacity: 0.55;" if count == 0 else ""
        st.markdown(
            f"""
            <div class="segment-card" style="{dim}">
                <strong style="color: #1DB954;">{escape_html(profile['name'])}</strong>
                <p style="font-size: 12px; color: #B3B3B3; margin: 8px 0;">{escape_html(profile['description'])}</p>
                <p style="font-size: 22px; font-weight: bold; margin: 0;">{count:,}
                <span style="font-size: 12px; color: #B3B3B3; font-weight: normal;"> negatives</span></p>
                <p style="font-size: 12px; color: #B3B3B3; margin: 6px 0 0 0;">
                    {profile['pct_of_negative']:.0f}% of negative feedback
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("---")
st.subheader("Answers by discovery question")

for q_idx, q_ans in enumerate(insights):
    question = q_ans["question"]
    icon = q_ans.get("icon", "")
    problem = q_ans.get("problem_statement", "")
    answer = q_ans.get("llm_answer", q_ans.get("summary", ""))
    stats = q_ans.get("key_stats", {})
    quotes = q_ans.get("quotes", [])
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
        with e1:
            st.metric("Negative reviews matched", f"{stats.get('total_relevant_reviews', 0):,}")
        with e2:
            st.metric("% of all feedback", f"{stats.get('pct_of_total', 0):.1f}%")
        with e3:
            st.metric("% of negatives", f"{stats.get('pct_of_negative', 0):.1f}%")

        if quotes:
            st.markdown("**Quotes to validate**")
            for quote in quotes[:3]:
                st.markdown(
                    f"""
                    <div class="quote-box">
                        "{escape_html(quote['text'])}"<br/>
                        <span style="font-size: 10px; color: #888; font-style: normal;">
                            {escape_html(quote['source'])}
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No matching quotes in this run.")
