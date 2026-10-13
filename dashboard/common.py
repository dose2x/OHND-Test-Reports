"""
Shared setup for every dashboard page: connect to Garage 61, show friendly
errors instead of stack traces, and load your statistics with car/track
names and seasons attached.
"""

from __future__ import annotations

import pandas as pd
import requests
import streamlit as st

from dashboard.analysis import enrich_stats
from dashboard.data import get_client, get_lookups, get_my_statistics
from garage61 import Garage61APIError, Garage61AuthError, Garage61Client

SETUP_HELP = """
**To connect this dashboard to Garage 61:**

1. Copy `.env.example` to `.env` in the project root.
2. Paste your personal access token from
   [garage61.net/developer/applications](https://garage61.net/developer/applications)
   into `.env` as `GARAGE61_TOKEN`.
3. Restart the dashboard (`python -m streamlit run app.py`).
"""


def page_header(title: str, caption: str | None = None) -> None:
    st.title(title)
    if caption:
        st.caption(caption)


def sidebar_refresh() -> None:
    with st.sidebar:
        st.markdown("### OHND Test Data App")
        st.caption("Data analysis for telemetry to improve in iRacing.")
        if st.button("Refresh data"):
            st.cache_data.clear()
            st.rerun()


def require_client() -> Garage61Client:
    """The Garage 61 client, or stop the page with setup instructions."""
    try:
        return get_client()
    except RuntimeError as exc:
        st.warning(str(exc))
        st.markdown(SETUP_HELP)
        st.stop()


def load_enriched_stats(client: Garage61Client) -> pd.DataFrame:
    """Your driving statistics with names, classes, sessions and seasons.
    Stops the page with a readable message if Garage 61 can't be reached."""
    try:
        stats = get_my_statistics(client)
    except Garage61AuthError:
        st.warning("Your GARAGE61_TOKEN was rejected. Double-check it in .env.")
        st.markdown(SETUP_HELP)
        st.stop()
    except (Garage61APIError, requests.exceptions.RequestException) as exc:
        st.error(f"Couldn't load driving statistics from Garage 61: {exc}")
        st.stop()

    try:
        lookups = get_lookups(client)
    except (Garage61APIError, requests.exceptions.RequestException) as exc:
        # Still useful without names: rows fall back to "Car #1" / "Track #31".
        st.warning(f"Couldn't load car/track names, showing ID numbers instead: {exc}")
        lookups = {}

    df = enrich_stats(stats, **lookups)
    if df.empty:
        st.info("No driving statistics yet. Drive a session with Garage 61 running and refresh.")
        st.stop()
    return df


def load_lookups_platforms() -> list[dict]:
    """Platforms (with season dates), or [] if they can't be loaded."""
    try:
        return get_lookups(get_client()).get("platforms", [])
    except (RuntimeError, Garage61APIError, requests.exceptions.RequestException):
        return []


def session_filter(df: pd.DataFrame, key: str, default: list[str] | None = None) -> pd.DataFrame:
    """Sidebar multiselect for session types; returns the filtered frame."""
    options = [s for s in ["Practice", "Qualifying", "Race"] if s in set(df["session"])]
    options += sorted(set(df["session"]) - set(options))
    chosen = st.sidebar.multiselect(
        "Session types", options, default=[o for o in (default or options) if o in options], key=key
    )
    return df[df["session"].isin(chosen)] if chosen else df.iloc[0:0]


def date_filter(df: pd.DataFrame, key: str) -> pd.DataFrame:
    """Sidebar time-range picker (all time / last 30 days / 90 days / year /
    latest iRacing season you drove in)."""
    ranges = ["All time", "Last 30 days", "Last 90 days", "Last 12 months"]
    current = df.dropna(subset=["season"]).sort_values("day")["season"].iloc[-1:] if "season" in df else []
    if len(current):
        ranges.insert(1, f"Latest season ({current.iloc[0]})")
    choice = st.sidebar.radio("Time range", ranges, key=key)
    end = pd.Timestamp.today().normalize() + pd.Timedelta(days=1)
    if choice.startswith("Latest season"):
        return df[df["season"] == current.iloc[0]]
    days = {"Last 30 days": 30, "Last 90 days": 90, "Last 12 months": 365}.get(choice)
    return df[df["day"] >= end - pd.Timedelta(days=days)] if days else df


def fmt_hours(hours: float) -> str:
    return f"{hours:,.1f} h" if hours >= 1 else f"{hours * 60:.0f} min"
