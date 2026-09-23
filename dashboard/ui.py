"""Small reusable display helpers for the dashboard pages."""

from __future__ import annotations

import streamlit as st

# /me/statistics and /teams/{team}/statistics return
# {"drivingStatistics": [...]}, one row per day/track/car/session type
# (https://garage61.net/developer/endpoints/v1/getStatistics). The tiles
# show these fields summed across all rows: field -> (label, format).
_STAT_TOTALS: dict[str, tuple[str, str]] = {
    "lapsDriven": ("Laps driven", "int"),
    "cleanLapsDriven": ("Clean laps", "int"),
    "timeOnTrack": ("Time on track", "duration"),
    "events": ("Events", "int"),
}


def format_duration(seconds: float) -> str:
    """Format a duration in seconds as e.g. '12h 34m' or '3m 05s'."""
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def format_lap_time(seconds: float) -> str:
    """Format a lap time in seconds as e.g. '1:23.456'."""
    minutes, secs = divmod(seconds, 60)
    return f"{int(minutes)}:{secs:06.3f}"


def render_stat_tiles(stats: dict, columns: int = 4) -> None:
    """Render driving statistics totals as metric tiles."""
    rows = (stats or {}).get("drivingStatistics") or []
    if not rows:
        st.info("No statistics available yet.")
        return

    cols = st.columns(columns)
    for i, (field, (label, kind)) in enumerate(_STAT_TOTALS.items()):
        total = sum(row.get(field) or 0 for row in rows)
        display = format_duration(total) if kind == "duration" else f"{int(total):,}"
        cols[i % columns].metric(label, display)

    with st.expander("Raw statistics data"):
        st.json(stats)


def display_name(user: dict) -> str:
    """/me has firstName, lastName and an optional nickName (no single name field)."""
    full = " ".join(part for part in (user.get("firstName"), user.get("lastName")) if part)
    return user.get("nickName") or full or "Unknown driver"


def render_account_card(me: dict) -> None:
    st.subheader(display_name(me))
    if me.get("slug"):
        st.caption(f"garage61.net/@{me['slug']}")
    if me.get("subscriptionPlan"):
        st.caption(f"Plan: {me['subscriptionPlan']}")


def render_linked_accounts(accounts: list[dict]) -> None:
    if not accounts:
        st.info("No linked accounts (e.g. iRacing) found.")
        return
    for account in accounts:
        with st.container(border=True):
            cols = st.columns([3, 2, 3])
            cols[0].markdown(f"**{account.get('name') or 'Unknown'}**")
            cols[1].caption(account.get("platform") or "Unknown platform")
            # e.g. "Road iRating 2345 · Road Safety rating A 3.45"
            ratings = [
                " ".join(str(part) for part in (r.get("category"), r.get("type"), r.get("ratingDisplayAs") or r.get("rating")) if part)
                for r in account.get("ratings") or []
            ]
            if ratings:
                cols[2].caption(" · ".join(ratings))


def render_teams(teams: list[dict]) -> None:
    if not teams:
        st.info("You haven't joined any teams yet.")
        return
    for team in teams:
        with st.container(border=True):
            owner = " · owner" if team.get("isOwner") else ""
            st.markdown(f"**{team.get('name') or 'Unnamed team'}**")
            st.caption(f"{team.get('slug', '')}{owner}")
