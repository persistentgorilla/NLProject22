"""
Spotify Review Discovery Engine — Insights Engine

Orchestrates SentimentAnalyzer, TopicModeler, and ThemeClassifier to
produce enriched DataFrames and data-backed answers to the strategic
questions defined in ``config.settings``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from config.settings import STRATEGIC_QUESTIONS, THEME_TAXONOMY
from analysis.sentiment import SentimentAnalyzer
from analysis.topic_modeling import TopicModeler
from analysis.theme_classifier import ThemeClassifier
from analysis.user_segments import UserSegmentAnalyzer
from analysis.llm_analyzer import LLMAnalyzer
from utils.tier_inference import assign_inferred_tier

logger = logging.getLogger(__name__)


class InsightsEngine:
    """High-level orchestration layer that ties every analyser together.

    Attributes
    ----------
    sentiment_analyzer : SentimentAnalyzer
    topic_modeler : TopicModeler
    theme_classifier : ThemeClassifier
    topic_data : list[dict]
        Stored after topic modelling for later reference.
    """

    def __init__(self) -> None:
        """Initialise all three analysis sub-modules."""
        logger.info("Initialising InsightsEngine …")
        self.sentiment_analyzer = SentimentAnalyzer()
        self.topic_modeler = TopicModeler()
        self.theme_classifier = ThemeClassifier()
        self.segment_analyzer = UserSegmentAnalyzer()
        self.llm_analyzer = LLMAnalyzer()
        self.topic_data: List[Dict[str, Any]] = []
        logger.info("InsightsEngine ready.")

    # ------------------------------------------------------------------
    # Full analysis pipeline
    # ------------------------------------------------------------------

    def run_full_analysis(self, df: pd.DataFrame) -> pd.DataFrame:
        """Run sentiment → topic modelling → theme classification.

        Parameters
        ----------
        df : pd.DataFrame
            Raw reviews with at least a ``review_text`` column.

        Returns
        -------
        pd.DataFrame
            Fully enriched DataFrame with all analysis columns.
        """
        if "review_text" not in df.columns:
            raise ValueError("DataFrame must contain a 'review_text' column.")

        logger.info("▸ Running full analysis pipeline on %d reviews …", len(df))

        # 1. Sentiment
        try:
            result = self.sentiment_analyzer.analyze(df)
            logger.info("  ✓ Sentiment analysis complete.")
        except Exception as exc:
            logger.error("  ✗ Sentiment analysis failed: %s", exc)
            result = df.copy()

        # 2. Topic modelling
        try:
            result, self.topic_data = self.topic_modeler.analyze(result)
            logger.info("  ✓ Topic modelling complete.")
        except Exception as exc:
            logger.error("  ✗ Topic modelling failed: %s", exc)
            self.topic_data = []

        # 3. Theme classification
        try:
            result = self.theme_classifier.analyze(result)
            logger.info("  ✓ Theme classification complete.")
        except Exception as exc:
            logger.error("  ✗ Theme classification failed: %s", exc)

        # 4. Primary user segment labels
        try:
            result = self.segment_analyzer.assign_primary_segments(result)
            logger.info("  ✓ User segment labels assigned.")
        except Exception as exc:
            logger.error("  ✗ User segment labelling failed: %s", exc)

        # 5. Inferred Free / Premium tier (from review text)
        try:
            result = assign_inferred_tier(result)
            logger.info("  ✓ Inferred user tier labels assigned.")
        except Exception as exc:
            logger.error("  ✗ Tier inference failed: %s", exc)

        logger.info("▸ Full analysis pipeline finished.")
        return result

    # ------------------------------------------------------------------
    # Strategic questions
    # ------------------------------------------------------------------

    def answer_strategic_questions(
        self, df: pd.DataFrame, use_llm: bool = True
    ) -> List[Dict[str, Any]]:
        """Produce data-backed answers to each strategic question.

        Parameters
        ----------
        df : pd.DataFrame
            Fully enriched DataFrame (output of :meth:`run_full_analysis`).

        Returns
        -------
        list[dict]
            One dict per question with keys:
            ``question``, ``icon``, ``summary``, ``key_stats``,
            ``quotes``, ``themes_data``, ``segment_breakdown``, ``problem_statement``.
        """
        answers: List[Dict[str, Any]] = []

        for sq in STRATEGIC_QUESTIONS:
            qid: str = sq["id"]
            question: str = sq["question"]
            icon: str = sq["icon"]
            relevant_themes: List[str] = sq["relevant_themes"]

            logger.info("Answering %s: %s", qid, question)

            try:
                answer = self._answer_single_question(
                    df, question, icon, relevant_themes
                )
            except Exception as exc:
                logger.error("Failed to answer %s: %s", qid, exc)
                answer = {
                    "question": question,
                    "icon": icon,
                    "problem_statement": "Analysis could not be completed for this question.",
                    "summary": "Analysis could not be completed for this question.",
                    "key_stats": {},
                    "quotes": [],
                    "themes_data": {},
                    "segment_breakdown": [],
                }
            answers.append(answer)

        if use_llm:
            answers = self.llm_analyzer.enrich_insights(answers)
        else:
            for item in answers:
                item["llm_answer"] = item.get("summary", "")
                item["llm_used"] = False

        return answers

    def _answer_single_question(
        self,
        df: pd.DataFrame,
        question: str,
        icon: str,
        relevant_themes: List[str],
    ) -> Dict[str, Any]:
        """Build an answer dict for one strategic question.

        Parameters
        ----------
        df : pd.DataFrame
            Enriched DataFrame.
        question : str
            The strategic question text.
        icon : str
            Emoji icon for display.
        relevant_themes : list[str]
            Theme names to filter on.

        Returns
        -------
        dict
        """
        # --- 1. Filter reviews matching ANY relevant theme ---
        theme_cols = [f"theme_{tn}" for tn in relevant_themes if f"theme_{tn}" in df.columns]
        if theme_cols:
            mask = df[theme_cols].any(axis=1)
            filtered = df[mask].copy()
        else:
            filtered = df.copy()

        # Focus on negative reviews — these carry actionable pain signals.
        filtered = self.segment_analyzer.negative_reviews(filtered)

        total_relevant = len(filtered)
        total_all = max(len(df), 1)
        total_negative_all = len(self.segment_analyzer.negative_reviews(df))

        # --- 2. Sentiment stats for the filtered set ---
        key_stats: Dict[str, Any] = {
            "total_relevant_reviews": total_relevant,
            "pct_of_total": round(total_relevant / total_all * 100, 1),
            "pct_of_negative": round(
                total_relevant / max(total_negative_all, 1) * 100, 1
            ),
        }
        if "sentiment_compound" in filtered.columns and total_relevant > 0:
            key_stats["avg_sentiment"] = round(
                float(filtered["sentiment_compound"].mean()), 3
            )
            key_stats["pct_negative"] = round(
                float((filtered["sentiment_label"] == "Negative").mean() * 100), 1
            ) if "sentiment_label" in filtered.columns else 0.0
            key_stats["pct_positive"] = round(
                float((filtered["sentiment_label"] == "Positive").mean() * 100), 1
            ) if "sentiment_label" in filtered.columns else 0.0
        else:
            key_stats["avg_sentiment"] = 0.0
            key_stats["pct_negative"] = 0.0
            key_stats["pct_positive"] = 0.0

        # --- 3. Theme-level data ---
        themes_data: Dict[str, Any] = {}
        for tn in relevant_themes:
            col = f"theme_{tn}"
            if col in df.columns:
                theme_reviews = self.segment_analyzer.negative_reviews(df[df[col].astype(bool)])
                theme_count = len(theme_reviews)
                avg_sent = (
                    float(theme_reviews["sentiment_compound"].mean())
                    if "sentiment_compound" in theme_reviews.columns and len(theme_reviews) > 0
                    else 0.0
                )
                themes_data[tn] = {
                    "count": theme_count,
                    "avg_sentiment": round(avg_sent, 3),
                    "icon": THEME_TAXONOMY.get(tn, {}).get("icon", ""),
                }

        # --- 4. Top keywords (from TF-IDF if available) ---
        top_keywords = self.topic_modeler.get_top_tfidf_terms(n_terms=10)

        # --- 5. Representative quotes ---
        quotes = self._select_quotes(filtered, n=5, negative_only=True)

        segment_breakdown = self.segment_analyzer.segment_breakdown_for_subset(
            df, filtered, top_n=4
        )
        problem_statement = self._problem_statement(question, themes_data, relevant_themes)

        summary = self._build_narrative(
            question,
            key_stats,
            themes_data,
            top_keywords,
            total_relevant,
            segment_breakdown,
            problem_statement,
        )

        return {
            "question": question,
            "icon": icon,
            "problem_statement": problem_statement,
            "summary": summary,
            "key_stats": key_stats,
            "quotes": quotes,
            "themes_data": themes_data,
            "segment_breakdown": segment_breakdown,
        }

    # ------------------------------------------------------------------
    # Helper: quote selection
    # ------------------------------------------------------------------

    def _select_quotes(
        self, df: pd.DataFrame, n: int = 5, negative_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Pick the most representative review quotes.

        Selection priority:
        1. Reviews with highest ``helpful_count`` (if column exists).
        2. Fall back to most extreme sentiment (mix of positive & negative).
        3. Trim very long reviews to 300 chars.

        Parameters
        ----------
        df : pd.DataFrame
            Filtered subset of enriched reviews.
        n : int
            Number of quotes to return.

        Returns
        -------
        list[dict]
            Each dict has ``text``, ``sentiment``, ``source``.
        """
        if df.empty or "review_text" not in df.columns:
            return []

        candidates = df.dropna(subset=["review_text"]).copy()
        if negative_only and "sentiment_label" in candidates.columns:
            candidates = candidates[candidates["sentiment_label"] == "Negative"]
        elif negative_only and "sentiment_compound" in candidates.columns:
            from config.settings import SENTIMENT_NEGATIVE_THRESHOLD
            candidates = candidates[candidates["sentiment_compound"] < SENTIMENT_NEGATIVE_THRESHOLD]

        if candidates.empty:
            return []

        # Sort by helpfulness first, then sentiment extremity
        if "helpful_count" in candidates.columns:
            candidates["_sort_key"] = (
                candidates["helpful_count"].fillna(0).astype(float)
            )
        elif "sentiment_compound" in candidates.columns:
            candidates["_sort_key"] = candidates["sentiment_compound"].abs()
        else:
            candidates["_sort_key"] = 0

        candidates = candidates.sort_values("_sort_key", ascending=False)

        selected: List[pd.Series] = []
        if negative_only:
            selected = [row for _, row in candidates.head(n).iterrows()]
        elif "sentiment_label" in candidates.columns:
            for label in ["Negative", "Positive", "Neutral"]:
                subset = candidates[candidates["sentiment_label"] == label]
                take = max(1, n // 3)
                selected.extend(
                    row for _, row in subset.head(take).iterrows()
                )
        else:
            selected = [row for _, row in candidates.head(n).iterrows()]

        # De-duplicate and cap at n
        seen_texts: set[str] = set()
        quotes: List[Dict[str, Any]] = []
        for row in selected:
            text = str(row["review_text"]).strip()
            if not text or text in seen_texts:
                continue
            seen_texts.add(text)
            display = text[:300] + ("…" if len(text) > 300 else "")
            quotes.append(
                {
                    "text": display,
                    "sentiment": (
                        float(row.get("sentiment_compound", 0.0))
                    ),
                    "source": str(row.get("source", "unknown")),
                }
            )
            if len(quotes) >= n:
                break

        return quotes

    # ------------------------------------------------------------------
    # Helper: narrative builder
    # ------------------------------------------------------------------

    def _problem_statement(
        self,
        question: str,
        themes_data: Dict[str, Any],
        relevant_themes: List[str],
    ) -> str:
        """One-line problem statement for business readers."""
        if themes_data:
            top_theme = max(themes_data.items(), key=lambda kv: kv[1]["count"])
            if top_theme[1]["count"] > 0:
                meta = THEME_TAXONOMY.get(top_theme[0], {})
                if meta.get("description"):
                    return str(meta["description"])

        fallback = {
            "Why do users struggle to discover new music?": (
                "Users feel they are not discovering enough new music."
            ),
            "What are the most common frustrations with recommendations?": (
                "Users are unhappy with how Spotify recommends music."
            ),
            "What listening behaviors are users trying to achieve?": (
                "Users describe habits and moods the product is not supporting well."
            ),
            "What causes users to repeatedly listen to the same content?": (
                "Users keep replaying the same tracks instead of finding new ones."
            ),
            "Which user segments experience different discovery challenges?": (
                "Different groups of users hit different discovery blockers."
            ),
            "What unmet needs emerge consistently across reviews?": (
                "Users repeatedly ask for capabilities Spotify does not provide today."
            ),
        }
        return fallback.get(question, "Users report a recurring product problem in this area.")

    def _build_narrative(
        self,
        question: str,
        key_stats: Dict[str, Any],
        themes_data: Dict[str, Any],
        top_keywords: List[str],
        total_relevant: int,
        segment_breakdown: List[Dict[str, Any]],
        problem_statement: str,
    ) -> str:
        """Compose a short, data-backed narrative summary.

        Parameters
        ----------
        question : str
            The strategic question being answered.
        key_stats : dict
            Computed key statistics.
        themes_data : dict
            Per-theme counts and sentiment.
        top_keywords : list[str]
            Extracted TF-IDF keywords.
        total_relevant : int
            Number of reviews matching the question's themes.

        Returns
        -------
        str
            A 2–4 sentence summary paragraph.
        """
        parts: List[str] = []
        pct_total = key_stats.get("pct_of_total", 0.0)

        if total_relevant == 0:
            return (
                "No negative reviews matched this question in the current run. "
                "Try adding more sources or increasing the app store review target."
            )

        parts.append(
            f"{total_relevant} negative reviews ({pct_total}% of all feedback) relate to this question. "
        )

        parts.append(f"In plain terms: {problem_statement} ")

        if segment_breakdown:
            seg_names = ", ".join(item["name"] for item in segment_breakdown[:2])
            parts.append(f"Most affected groups: {seg_names}. ")

        if themes_data:
            sorted_themes = sorted(
                themes_data.items(), key=lambda kv: kv[1]["count"], reverse=True
            )
            top_theme_name, top_theme_info = sorted_themes[0]
            if top_theme_info["count"] > 0:
                parts.append(
                    f"Top pain area: {top_theme_name} "
                    f"({top_theme_info['count']} negative mentions). "
                )

        if top_keywords:
            kw_str = ", ".join(top_keywords[:5])
            parts.append(f"Common words in these reviews: {kw_str}.")

        return "".join(parts).strip()

    # ------------------------------------------------------------------
    # Executive summary
    # ------------------------------------------------------------------

    def get_executive_summary(
        self,
        df: pd.DataFrame,
        segment_profiles: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Produce a high-level executive summary of all analysis.

        Parameters
        ----------
        df : pd.DataFrame
            Fully enriched DataFrame (output of :meth:`run_full_analysis`).

        Returns
        -------
        dict
            Keys:
            * ``total_reviews`` — int
            * ``source_breakdown`` — dict[str, int]
            * ``overall_sentiment`` — dict with avg, distribution
            * ``top_themes`` — list of (name, count) tuples (top 5)
            * ``topic_summary`` — output of TopicModeler.get_topic_summary()
            * ``key_findings`` — list[str] of 3–5 bullet-point findings
        """
        summary: Dict[str, Any] = {}
        summary["total_reviews"] = len(df)

        # Source breakdown
        if "source" in df.columns:
            summary["source_breakdown"] = (
                df["source"].value_counts().to_dict()
            )
        else:
            summary["source_breakdown"] = {"unknown": len(df)}

        # Overall sentiment
        sentiment_stats = self.sentiment_analyzer.get_summary_stats(df)
        summary["overall_sentiment"] = {
            "avg_compound": sentiment_stats.get("avg_sentiment", 0.0),
            "median_compound": sentiment_stats.get("median_sentiment", 0.0),
            "distribution": sentiment_stats.get("distribution", {}),
            "distribution_pct": sentiment_stats.get("distribution_pct", {}),
            "avg_subjectivity": sentiment_stats.get("avg_subjectivity", 0.0),
        }

        # Top themes
        theme_dist = self.theme_classifier.get_theme_distribution(df)
        summary["top_themes"] = list(theme_dist.items())[:5]

        # Topic summary
        summary["topic_summary"] = self.topic_modeler.get_topic_summary()

        # Key findings (auto-generated)
        summary["key_findings"] = self._extract_key_findings(
            df, sentiment_stats, theme_dist, segment_profiles=segment_profiles
        )

        profiles = segment_profiles
        if profiles is None:
            profiles = self.segment_analyzer.build_profiles(df)
        summary["segment_profiles"] = profiles
        summary["pain_themes"] = self.segment_analyzer.pain_theme_summary(df, top_n=3)
        summary["negative_review_count"] = len(self.segment_analyzer.negative_reviews(df))
        summary["headline"] = self.segment_analyzer.headline(
            df, summary["pain_themes"], profiles
        )

        return summary

    def _extract_key_findings(
        self,
        df: pd.DataFrame,
        sentiment_stats: Dict[str, Any],
        theme_dist: Dict[str, int],
        segment_profiles: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        """Derive 3-5 key findings from aggregate data.

        Parameters
        ----------
        df : pd.DataFrame
            Enriched DataFrame.
        sentiment_stats : dict
            Output of SentimentAnalyzer.get_summary_stats.
        theme_dist : dict
            Theme → count mapping.

        Returns
        -------
        list[str]
        """
        findings: List[str] = []
        n = len(df)
        negatives = self.segment_analyzer.negative_reviews(df)
        neg_count = len(negatives)

        if n == 0:
            return ["No reviews available for analysis."]

        findings.append(
            f"{neg_count} of {n} reviews ({neg_count / n * 100:.0f}%) are negative — "
            "these are the primary signal for pain-area validation."
        )

        profiles = segment_profiles or self.segment_analyzer.build_profiles(df)
        if profiles:
            top_segment = profiles[0]
            findings.append(
                f"Most affected group: {top_segment['name']} "
                f"({top_segment['negative_review_count']} negative reviews, "
                f"{top_segment['pct_of_negative']:.0f}% of all negatives). "
                f"Main issue: {top_segment['top_pain_area']}."
            )

        pain_themes = self.segment_analyzer.pain_theme_summary(df, top_n=1)
        if pain_themes:
            top = pain_themes[0]
            findings.append(
                f"Top pain area: {top['theme']} "
                f"({top['count']} negative mentions — {top.get('description', '').lower()})."
            )

        return findings[:3]
