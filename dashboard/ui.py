"""Small reusable display helpers for the dashboard pages.

Shapes here match what the Garage 61 API actually returns (checked against
real responses via scripts/dump_api_samples.py).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def format_duration(seconds: float) -> str:
    """Format a duration in seconds as e.g. '12h 34m' or '3m 05s'."""
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:,}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def format_lap_time(seconds: float) -> str:
    """Format a lap time in seconds as e.g. '1:23.456'."""
    minutes, secs = divmod(seconds, 60)
    return f"{int(minutes)}:{secs:06.3f}"


def _full_name(user: dict) -> str:
    return " ".join(p for p in (user.get("firstName"), user.get("lastName")) if p)


def display_name(user: dict) -> str:
    """/me has firstName, lastName and an optional nickName (no single name field)."""
    return user.get("nickName") or _full_name(user) or user.get("slug") or "Unknown driver"


# ----------------------------------------------------------------------
# Driving statistics
# ----------------------------------------------------------------------


def driving_stats_frame(stats: dict) -> pd.DataFrame:
    """Turn {"drivingStatistics": [...]} into a DataFrame (one row per
    day/car/track/session type). Empty if the shape isn't recognized."""
    rows = (stats or {}).get("drivingStatistics")
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame()
    df = pd.DataFrame([r for r in rows if isinstance(r, dict)])
    if "day" in df:
        df["day"] = pd.to_datetime(df["day"], errors="coerce")
    for col in ("events", "timeOnTrack", "lapsDriven", "cleanLapsDriven"):
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        else:
            df[col] = 0
    return df


def summarize_driving_stats(df: pd.DataFrame) -> dict:
    """Headline totals from a driving_stats_frame."""
    laps = int(df["lapsDriven"].sum())
    clean = int(df["cleanLapsDriven"].sum())
    return {
        "laps": laps,
        "clean_laps": clean,
        "clean_pct": (clean / laps * 100) if laps else 0.0,
        "time_on_track": float(df["timeOnTrack"].sum()),
        "events": int(df["events"].sum()),
        "days": int(df["day"].dt.date.nunique()) if "day" in df else 0,
        "first_day": df["day"].min() if "day" in df else None,
    }


def render_driving_stats(stats: dict) -> None:
    """Metric tiles + a monthly laps chart for a statistics response."""
    df = driving_stats_frame(stats)
    if df.empty:
        st.info("No driving statistics available yet.")
        if stats:
            with st.expander("Raw statistics data"):
                st.json(stats)
        return

    s = summarize_driving_stats(df)
    cols = st.columns(5)
    cols[0].metric("Laps driven", f"{s['laps']:,}")
    cols[1].metric("Clean laps", f"{s['clean_pct']:.0f}%", help=f"{s['clean_laps']:,} clean laps")
    cols[2].metric("Time on track", format_duration(s["time_on_track"]))
    cols[3].metric("Events", f"{s['events']:,}")
    cols[4].metric("Days driven", f"{s['days']:,}")
    if s["first_day"] is not None and not pd.isna(s["first_day"]):
        st.caption(f"Since {s['first_day']:%b %d, %Y}")

    if "day" in df and df["day"].notna().any():
        monthly = (
            df.dropna(subset=["day"])
            .assign(month=lambda d: d["day"].dt.to_period("M").dt.to_timestamp())
            .groupby("month")[["lapsDriven", "cleanLapsDriven"]]
            .sum()
            .rename(columns={"lapsDriven": "All laps", "cleanLapsDriven": "Clean laps"})
        )
        st.markdown("##### Laps per month")
        st.line_chart(monthly)


# ----------------------------------------------------------------------
# Account, linked accounts, teams
# ----------------------------------------------------------------------


def render_account_card(me: dict) -> None:
    st.subheader(display_name(me))
    details = []
    if me.get("nickName") and _full_name(me):
        details.append(_full_name(me))
    if me.get("slug"):
        details.append(f"garage61.net/@{me['slug']}")
    if me.get("subscriptionPlan"):
        details.append(f"{me['subscriptionPlan'].title()} plan")
    if details:
        st.caption(" · ".join(details))


def _ratings_table(ratings: list) -> pd.DataFrame:
    """Pivot [{category, type, ratingDisplayAs, rating}, ...] into
    category rows x rating-type columns (e.g. road: iRating, Safety)."""
    rows = []
    for r in ratings or []:
        if not isinstance(r, dict):
            continue
        value = r.get("ratingDisplayAs", r.get("rating"))
        if r.get("rating") == -1:
            value = "—"  # -1 means no rating in that category yet
        rows.append(
            {
                "Category": str(r.get("category", "")).replace("_", " ").title(),
                "Type": str(r.get("type", "")).replace("_", " ").title().replace("Irating", "iRating"),
                "Value": value,
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).pivot_table(
        index="Category", columns="Type", values="Value", aggfunc="first"
    )


def render_linked_accounts(accounts: list[dict]) -> None:
    if not accounts:
        st.info("No linked accounts (e.g. iRacing) found.")
        return
    for account in accounts:
        platform = account.get("platform", "")
        if isinstance(platform, dict):
            platform = platform.get("name", "")
        with st.container(border=True):
            st.markdown(f"**{account.get('name', 'Unknown')}**")
            label = {"iracing": "iRacing"}.get(str(platform).lower(), str(platform).title())
            st.caption(f"{label or 'Unknown platform'} · ID {account.get('id', '?')}")
            table = _ratings_table(account.get("ratings"))
            if not table.empty:
                st.dataframe(table, width="stretch")


def render_teams(teams: list[dict]) -> None:
    if not teams:
        st.info("You haven't joined any teams yet.")
        return
    for team in teams:
        with st.container(border=True):
            owner = " · Owner" if team.get("isOwner") else ""
            st.markdown(f"**{team.get('name', 'Unnamed team')}**")
            st.caption(f"{team.get('slug', '')}{owner}")


# Older name for render_driving_stats, kept so existing imports still work.
render_stat_tiles = render_driving_stats
