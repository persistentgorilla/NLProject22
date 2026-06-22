"""
LLM-powered plain-language answers for strategic discovery questions.

API keys are read from the environment (``OPENAI_API_KEY``) or Streamlit
secrets — never hard-coded or committed to the repository.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[misc, assignment]


class LLMAnalyzer:
    """Generate PM-readable answers from review evidence using OpenAI."""

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.api_key = self._resolve_api_key()
        self._client: Any = None
        if self.api_key and OpenAI is not None:
            self._client = OpenAI(api_key=self.api_key)

    @staticmethod
    def _resolve_api_key() -> Optional[str]:
        key = os.getenv("OPENAI_API_KEY", "").strip()
        if key:
            return key
        try:
            import streamlit as st

            if hasattr(st, "secrets") and "OPENAI_API_KEY" in st.secrets:
                return str(st.secrets["OPENAI_API_KEY"]).strip()
        except Exception:
            pass
        return None

    def is_available(self) -> bool:
        return self._client is not None

    def explain_question(self, answer: Dict[str, Any]) -> Optional[str]:
        """Return a short PM-style answer, or ``None`` if LLM is unavailable."""
        if not self.is_available():
            return None

        stats = answer.get("key_stats", {})
        quotes = answer.get("quotes", [])
        segments = answer.get("segment_breakdown", [])
        themes = answer.get("themes_data", {})

        quote_lines = [
            f'- "{q.get("text", "")}" ({q.get("source", "unknown")})'
            for q in quotes[:4]
        ]
        segment_lines = [
            f"- {s.get('name')}: {s.get('negative_review_count', 0)} negative reviews"
            for s in segments
        ]
        theme_lines = [
            f"- {name}: {info.get('count', 0)} negative mentions"
            for name, info in themes.items()
        ]

        user_prompt = f"""Question: {answer.get('question', '')}

Problem area: {answer.get('problem_statement', '')}

Evidence:
- Negative reviews matched: {stats.get('total_relevant_reviews', 0)} ({stats.get('pct_of_total', 0)}% of all feedback)
- Share of all negative feedback: {stats.get('pct_of_negative', 0)}%

User segments most affected:
{chr(10).join(segment_lines) or '- None identified'}

Related pain themes:
{chr(10).join(theme_lines) or '- None identified'}

Sample user quotes:
{chr(10).join(quote_lines) or '- No quotes available'}

Write a clear answer for a Spotify product manager who will validate these findings with users.
Use 3-5 short sentences. Lead with what the problem is, who is affected, and how strong the signal is.
Do not recommend product solutions. Do not use bullet points."""

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                temperature=0.3,
                max_tokens=320,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You summarize user feedback for product managers. "
                            "Be direct, plain, and evidence-based. No jargon, no hype."
                        ),
                    },
                    {"role": "user", "content": user_prompt},
                ],
            )
            text = (response.choices[0].message.content or "").strip()
            return text or None
        except Exception as exc:
            logger.warning("LLM answer failed: %s", exc)
            return None

    def enrich_insights(self, insights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add ``llm_answer`` and ``llm_used`` to each insight dict."""
        enriched: List[Dict[str, Any]] = []
        for item in insights:
            copy = dict(item)
            llm_text = self.explain_question(copy)
            copy["llm_answer"] = llm_text if llm_text else copy.get("summary", "")
            copy["llm_used"] = bool(llm_text)
            enriched.append(copy)
        return enriched

    @staticmethod
    def build_context_preview(answer: Dict[str, Any]) -> str:
        """Debug-friendly JSON preview of evidence sent to the model."""
        payload = {
            "question": answer.get("question"),
            "problem_statement": answer.get("problem_statement"),
            "key_stats": answer.get("key_stats"),
            "segments": answer.get("segment_breakdown"),
            "themes": answer.get("themes_data"),
            "quote_count": len(answer.get("quotes", [])),
        }
        return json.dumps(payload, indent=2)
