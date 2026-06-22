"""CSV persistence and DataFrame type restoration for analyzed reviews."""

from __future__ import annotations

import ast
import json
from io import BytesIO
from typing import Any, Dict, List, Optional

import pandas as pd

from config.settings import THEME_TAXONOMY

THEME_COLUMNS = [f"theme_{name}" for name in THEME_TAXONOMY]


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "t"}


def _serialize_list(value: Any) -> str:
    if isinstance(value, list):
        return json.dumps(value)
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "[]"
    return json.dumps(value) if not isinstance(value, str) else value


def _deserialize_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return parsed
    except (ValueError, SyntaxError):
        pass
    return [text]


def restore_analyzed_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Restore boolean and list columns after CSV load or session-state copy."""
    result = df.copy()

    for col in THEME_COLUMNS:
        if col in result.columns:
            result[col] = result[col].apply(_to_bool)

    if "themes" in result.columns:
        result["themes"] = result["themes"].apply(_deserialize_list)

    if "theme_count" in result.columns:
        result["theme_count"] = (
            pd.to_numeric(result["theme_count"], errors="coerce").fillna(0).astype(int)
        )

    if "topic_distribution" in result.columns:
        result["topic_distribution"] = result["topic_distribution"].apply(_deserialize_list)

    if "dominant_topic" in result.columns:
        result["dominant_topic"] = (
            pd.to_numeric(result["dominant_topic"], errors="coerce").fillna(0).astype(int)
        )

    for col in ("sentiment_compound", "sentiment_pos", "sentiment_neg", "sentiment_neu", "subjectivity"):
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")

    if "rating" in result.columns:
        result["rating"] = pd.to_numeric(result["rating"], errors="coerce")

    if "helpful_count" in result.columns:
        result["helpful_count"] = pd.to_numeric(result["helpful_count"], errors="coerce")

    return normalize_date_column(result)


def normalize_date_column(df: pd.DataFrame, column: str = "date") -> pd.DataFrame:
    """Parse mixed date formats from app stores, Reddit, and community posts."""
    if column not in df.columns:
        return df

    result = df.copy()

    def _clean(value: Any) -> Any:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return value
        text = str(value).replace("\u200e", "").replace("\u200f", "").strip()
        return text or None

    result[column] = result[column].apply(_clean)
    parsed = pd.to_datetime(result[column], errors="coerce", utc=True, format="mixed")
    if hasattr(parsed.dt, "tz_convert"):
        parsed = parsed.dt.tz_convert(None)
    result[column] = parsed
    return result


def save_analyzed_data(df: pd.DataFrame, path: str) -> None:
    """Persist an analyzed DataFrame to CSV with list columns serialized."""
    to_save = df.copy()
    if "themes" in to_save.columns:
        to_save["themes"] = to_save["themes"].apply(_serialize_list)
    if "topic_distribution" in to_save.columns:
        to_save["topic_distribution"] = to_save["topic_distribution"].apply(_serialize_list)
    to_save.to_csv(path, index=False)


def load_analyzed_data(path: str) -> pd.DataFrame:
    """Load an analyzed CSV and restore typed columns."""
    df = pd.read_csv(path)
    return restore_analyzed_dataframe(df)


def prepare_dataframe_for_export(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten list and boolean columns for spreadsheet-friendly export."""
    export_df = restore_analyzed_dataframe(df.copy())

    if "themes" in export_df.columns:
        export_df["themes"] = export_df["themes"].apply(
            lambda value: ", ".join(str(item) for item in value)
            if isinstance(value, list)
            else ("" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value))
        )

    if "topic_distribution" in export_df.columns:
        export_df["topic_distribution"] = export_df["topic_distribution"].apply(
            lambda value: ", ".join(f"{float(item):.4f}" for item in value)
            if isinstance(value, list)
            else ("" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value))
        )

    for col in THEME_COLUMNS:
        if col in export_df.columns:
            export_df[col] = export_df[col].apply(lambda value: "Yes" if value else "No")

    return export_df


def export_analyzed_dataframe_to_excel(df: pd.DataFrame, sheet_name: str = "Analyzed Reviews") -> bytes:
    """Serialize an analyzed DataFrame to an Excel (.xlsx) workbook."""
    export_df = prepare_dataframe_for_export(df)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name=sheet_name)
    return buffer.getvalue()


def export_dataframe_to_csv(df: pd.DataFrame) -> bytes:
    """Serialize a DataFrame to CSV bytes with export-friendly column formatting."""
    return prepare_dataframe_for_export(df).to_csv(index=False).encode("utf-8")


def export_insights_to_excel(
    df: pd.DataFrame,
    insights: List[Dict[str, Any]],
    exec_summary: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Build a workbook with strategic insight summaries and the full analyzed dataset."""
    summary_rows: List[Dict[str, Any]] = []
    for idx, item in enumerate(insights, start=1):
        stats = item.get("key_stats", {})
        segments = item.get("segment_breakdown", [])
        summary_rows.append(
            {
                "Question #": idx,
                "Question": item.get("question", ""),
                "Problem": item.get("problem_statement", ""),
                "Answer": item.get("llm_answer", item.get("summary", "")),
                "Summary": item.get("summary", ""),
                "AI Enhanced": "Yes" if item.get("llm_used") else "No",
                "Relevant Reviews": stats.get("total_relevant_reviews", 0),
                "% of Dataset": stats.get("pct_of_total", 0),
                "% of Negative Feedback": stats.get("pct_of_negative", 0),
                "Most Affected Segments": " | ".join(
                    seg.get("name", "") for seg in segments
                ),
            }
        )

    findings_rows = [
        {"Finding": finding}
        for finding in (exec_summary or {}).get("key_findings", [])
    ]

    segment_rows = [
        {
            "Segment": profile.get("name", ""),
            "Description": profile.get("description", ""),
            "Negative Reviews": profile.get("negative_review_count", 0),
            "% of Negative Feedback": profile.get("pct_of_negative", 0),
            "Top Pain Area": profile.get("top_pain_area", ""),
        }
        for profile in (exec_summary or {}).get("segment_profiles", [])
    ]

    pain_rows = [
        {
            "Pain Area": pain.get("theme", ""),
            "Negative Mentions": pain.get("count", 0),
            "% of Negative Feedback": pain.get("pct_of_negative", 0),
            "Description": pain.get("description", ""),
        }
        for pain in (exec_summary or {}).get("pain_themes", [])
    ]

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame(summary_rows).to_excel(writer, index=False, sheet_name="Validation Checklist")
        if segment_rows:
            pd.DataFrame(segment_rows).to_excel(writer, index=False, sheet_name="User Segments")
        if pain_rows:
            pd.DataFrame(pain_rows).to_excel(writer, index=False, sheet_name="Pain Areas")
        if findings_rows:
            pd.DataFrame(findings_rows).to_excel(writer, index=False, sheet_name="Key Findings")
        prepare_dataframe_for_export(df).to_excel(writer, index=False, sheet_name="Analyzed Reviews")
    return buffer.getvalue()
