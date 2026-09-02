"""
Cached data-access helpers for the Streamlit dashboard.

Keeping these separate from the UI code means the dashboard pages can stay
focused on layout, and API calls get cached (and reused across page
reruns) in one place.
"""

from __future__ import annotations

import streamlit as st

from garage61 import Config, Garage61Client

# How long fetched data stays fresh before Streamlit re-fetches it.
_TTL_SECONDS = 5 * 60


@st.cache_resource(show_spinner=False)
def get_client() -> Garage61Client:
    """Build the Garage 61 client once per session.

    Raises RuntimeError if GARAGE61_TOKEN isn't configured — callers
    should catch this and show setup instructions instead of a stack trace.
    """
    return Garage61Client(Config.from_env())


@st.cache_data(show_spinner="Loading account info…", ttl=_TTL_SECONDS)
def get_me(_client: Garage61Client) -> dict:
    return _client.get_me()


@st.cache_data(show_spinner="Loading linked accounts…", ttl=_TTL_SECONDS)
def get_my_accounts(_client: Garage61Client) -> list[dict]:
    return _client.get_my_accounts()


@st.cache_data(show_spinner="Loading driving statistics…", ttl=_TTL_SECONDS)
def get_my_statistics(_client: Garage61Client) -> dict:
    return _client.get_my_statistics()


@st.cache_data(show_spinner="Loading teams…", ttl=_TTL_SECONDS)
def get_teams(_client: Garage61Client) -> list[dict]:
    return _client.find_teams()


@st.cache_data(show_spinner=False, ttl=_TTL_SECONDS)
def get_team_statistics(_client: Garage61Client, team_id: str) -> dict:
    return _client.get_team_statistics(team_id)
