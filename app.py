"""
OHND Test Data App — Streamlit dashboard.

Overview page (account info, linked accounts, driving statistics, teams)
plus the Tracks & Cars, Seasons and Practice vs Race pages in views/,
all pulled live from the Garage 61 API.

Run with:
    python -m streamlit run app.py
"""

from __future__ import annotations

import requests
import streamlit as st

from dashboard.data import get_client, get_me, get_my_accounts, get_my_statistics, get_teams, get_team_statistics
from dashboard.ui import render_account_card, render_driving_stats, render_linked_accounts, render_teams
from dashboard.common import sidebar_refresh
from garage61 import Garage61APIError, Garage61AuthError

# One section failing (API error or dropped connection) shouldn't take down the page.
_SECTION_ERRORS = (Garage61APIError, requests.exceptions.RequestException)

# Each page's title (Overview, Seasons, ...) becomes the browser tab title.
st.set_page_config(page_icon="🏁", layout="wide")


def render_setup_instructions(detail: str) -> None:
    st.title("🏁 OHND Test Data App")
    st.warning(detail)
    st.markdown(
        """
        **To connect this dashboard to Garage 61:**

        1. Copy `.env.example` to `.env` in the project root.
        2. Request a personal access token at
           [garage61.net/developer/applications](https://garage61.net/developer/applications)
           (owned by the OHND Racing team), and paste it into `.env` as
           `GARAGE61_TOKEN`.
        3. Restart the dashboard (`python -m streamlit run app.py`).
        """
    )


def main() -> None:
    try:
        client = get_client()
    except RuntimeError as exc:
        render_setup_instructions(str(exc))
        st.stop()

    try:
        me = get_me(client)
    except Garage61AuthError:
        render_setup_instructions(
            "Your GARAGE61_TOKEN was rejected. Double-check it in .env, or "
            "request a new token if it may have been revoked."
        )
        st.stop()
    except Garage61APIError as exc:
        st.title("🏁 OHND Test Data App")
        st.error(f"Garage 61 API error: {exc}")
        st.stop()
    except requests.exceptions.RequestException as exc:
        st.title("🏁 OHND Test Data App")
        st.error(f"Couldn't reach garage61.net: {exc}")
        st.stop()

    st.title("🏁 OHND Test Data App")
    st.caption("Live overview from your Garage 61 account.")

    render_account_card(me)

    st.divider()
    st.subheader("Driving statistics")
    try:
        stats = get_my_statistics(client)
        render_driving_stats(stats)
    except _SECTION_ERRORS as exc:
        st.error(f"Couldn't load statistics: {exc}")

    st.divider()
    st.subheader("Linked accounts")
    try:
        accounts = get_my_accounts(client)
        render_linked_accounts(accounts)
    except _SECTION_ERRORS as exc:
        st.error(f"Couldn't load linked accounts: {exc}")

    st.divider()
    st.subheader("Teams")
    try:
        teams = get_teams(client)
        render_teams(teams)

        if teams:
            st.markdown("#### Team statistics")
            # Teams you own (e.g. OHND Racing) first in the picker.
            ordered = sorted(teams, key=lambda t: not t.get("isOwner"))
            team_names = {t["id"]: t.get("name", t["id"]) for t in ordered if t.get("id")}
            if team_names:
                selected_id = st.selectbox(
                    "Choose a team",
                    options=list(team_names.keys()),
                    format_func=lambda team_id: team_names[team_id],
                )
                # One team's stats failing (e.g. no access) shouldn't hide the team list.
                try:
                    render_driving_stats(get_team_statistics(client, selected_id))
                except _SECTION_ERRORS as exc:
                    st.warning(f"Couldn't load statistics for this team: {exc}")
    except _SECTION_ERRORS as exc:
        st.error(f"Couldn't load teams: {exc}")

    sidebar_refresh()


navigation = st.navigation(
    [
        st.Page(main, title="Overview", icon="🏠", default=True),
        st.Page("views/1_Tracks_and_Cars.py", title="Tracks & Cars", icon="🛣️"),
        st.Page("views/2_Seasons.py", title="Seasons", icon="📅"),
        st.Page("views/3_Practice_vs_Race.py", title="Practice vs Race", icon="🏁"),
    ]
)
navigation.run()
