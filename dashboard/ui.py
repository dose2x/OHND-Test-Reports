"""Small reusable display helpers for the dashboard pages."""

from __future__ import annotations

import streamlit as st

# Common statistics field names -> (display label, formatter).
# The exact shape of /me/statistics and /teams/{id}/statistics isn't fully
# documented, so we render any of these keys we recognize as metric tiles,
# and fall back to a raw JSON view for everything else so nothing is lost.
_KNOWN_STAT_FIELDS: dict[str, tuple[str, str]] = {
    "totalLaps": ("Total laps", "int"),
    "lapCount": ("Total laps", "int"),
    "totalDistance": ("Total distance (km)", "km"),
    "totalDistanceDriven": ("Total distance (km)", "km"),
    "totalTime": ("Total time on track", "duration"),
    "totalTimeDriven": ("Total time on track", "duration"),
    "totalDrivingTime": ("Total time on track", "duration"),
    "totalEvents": ("Events", "int"),
    "eventCount": ("Events", "int"),
    "totalSessions": ("Sessions", "int"),
    "sessionCount": ("Sessions", "int"),
    "memberCount": ("Team members", "int"),
    "driverCount": ("Drivers", "int"),
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
    """Render any recognized statistics fields as metric tiles."""
    if not stats:
        st.info("No statistics available yet.")
        return

    tiles = []
    for key, (label, kind) in _KNOWN_STAT_FIELDS.items():
        if key not in stats or stats[key] is None:
            continue
        value = stats[key]
        if kind == "duration":
            display = format_duration(value)
        elif kind == "km":
            display = f"{value:,.0f}"
        else:
            display = f"{value:,}"
        tiles.append((label, display))

    if tiles:
        cols = st.columns(columns)
        for i, (label, display) in enumerate(tiles):
            cols[i % columns].metric(label, display)
    else:
        st.caption("No recognized statistics fields — showing raw data below.")

    with st.expander("Raw statistics data"):
        st.json(stats)


def render_account_card(me: dict) -> None:
    cols = st.columns([1, 3])
    with cols[0]:
        avatar = me.get("avatarUrl") or me.get("avatar")
        if avatar:
            st.image(avatar, width=96)
    with cols[1]:
        st.subheader(me.get("name") or "Unknown driver")
        st.caption(me.get("email", ""))
        if me.get("slug"):
            st.caption(f"garage61.net/@{me['slug']}")


def render_linked_accounts(accounts: list[dict]) -> None:
    if not accounts:
        st.info("No linked accounts (e.g. iRacing) found.")
        return
    for account in accounts:
        platform = account.get("platform", {})
        name = platform.get("name") if isinstance(platform, dict) else platform
        with st.container(border=True):
            cols = st.columns([3, 2, 2])
            cols[0].markdown(f"**{account.get('name', 'Unknown')}**")
            cols[1].caption(name or "Unknown platform")
            rating = account.get("rating") or account.get("iRating")
            if rating:
                cols[2].caption(f"Rating: {rating}")


def render_teams(teams: list[dict]) -> None:
    if not teams:
        st.info("You haven't joined any teams yet.")
        return
    for team in teams:
        with st.container(border=True):
            cols = st.columns([1, 4])
            with cols[0]:
                logo = team.get("logoUrl") or team.get("logo")
                if logo:
                    st.image(logo, width=56)
            with cols[1]:
                st.markdown(f"**{team.get('name', 'Unnamed team')}**")
                st.caption(team.get("slug", ""))
