"""Clear in-memory session state and optional on-disk data cache."""

from __future__ import annotations

import os
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from config import settings

try:
    from utils.dashboard_context import clear_dashboard_cache
except ImportError:  # pragma: no cover
    def clear_dashboard_cache() -> None:
        pass

SESSION_DEFAULTS: Dict[str, Any] = {
    "raw_data": pd.DataFrame(),
    "analyzed_data": pd.DataFrame(),
    "topics": [],
    "insights": [],
}

EXTRA_SESSION_KEYS: List[str] = ["current_page", "filter_key"]


def clear_data_cache() -> None:
    """Remove scraped and analyzed CSV files from the local data folder."""
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    for filename in (settings.SCRAPED_DATA_FILE, settings.ANALYZED_DATA_FILE):
        path = os.path.join(settings.DATA_DIR, filename)
        if os.path.exists(path):
            os.remove(path)


def reset_app_state(clear_disk_cache: bool = True) -> None:
    """Reset scraped data, analysis results, and Deep Dive filters for a fresh run."""
    for key, default in SESSION_DEFAULTS.items():
        st.session_state[key] = default

    for key in EXTRA_SESSION_KEYS:
        st.session_state.pop(key, None)

    if clear_disk_cache:
        clear_data_cache()

    clear_dashboard_cache()
