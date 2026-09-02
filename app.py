"""
OHND Test Data App — Streamlit dashboard.

Overview page: account info, linked accounts, driving statistics, and
teams, pulled live from the Garage 61 API.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import requests
import streamlit as st

from dashboard.data import get_client, get_me, get_my_accounts, get_my_statistics, get_teams, get_team_statistics
from dashboard.ui import render_account_card, render_linked_accounts, render_stat_tiles, render_teams
from garage61 import Garage61APIError, Garage61AuthError

st.set_page_config(
    page_title="OHND Test Data App",
    page_icon="🏁",
    layout="wide",
)


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
        3. Restart the dashboard (`streamlit run app.py`).
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
        render_stat_tiles(stats)
    except Garage61APIError as exc:
        st.error(f"Couldn't load statistics: {exc}")

    st.divider()
    st.subheader("Linked accounts")
    try:
        accounts = get_my_accounts(client)
        render_linked_accounts(accounts)
    except Garage61APIError as exc:
        st.error(f"Couldn't load linked accounts: {exc}")

    st.divider()
    st.subheader("Teams")
    try:
        teams = get_teams(client)
        render_teams(teams)

        if teams:
            st.markdown("#### Team statistics")
            team_names = {t["slug"]: t.get("name", t["slug"]) for t in teams if t.get("slug")}
            if team_names:
                selected_slug = st.selectbox(
                    "Choose a team",
                    options=list(team_names.keys()),
                    format_func=lambda slug: team_names[slug],
                )
                team_stats = get_team_statistics(client, selected_slug)
                render_stat_tiles(team_stats)
    except Garage61APIError as exc:
        st.error(f"Couldn't load teams: {exc}")

    with st.sidebar:
        st.markdown("### OHND Test Data App")
        st.caption("Data analysis for telemetry to improve in iRacing.")
        if st.button("Refresh data"):
            st.cache_data.clear()
            st.rerun()


if __name__ == "__main__":
    main()
