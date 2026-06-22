"""HTML escaping helpers for Streamlit unsafe_allow_html blocks."""

from __future__ import annotations

import html
from datetime import date, datetime
from typing import Any

import pandas as pd


def escape_html(value: Any) -> str:
    """Return a safe HTML-escaped string for embedding in markup."""
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return html.escape(value.isoformat(sep=" ", timespec="seconds"))
    return html.escape(str(value))
