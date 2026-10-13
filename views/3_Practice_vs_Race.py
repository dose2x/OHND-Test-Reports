"""Practice vs Race: how clean you are in each kind of session, and where
your racing falls off compared with practice."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from dashboard.analysis import SESSION_COLORS, SESSION_ORDER, monthly_clean_pct, practice_race_gap, summarize
from dashboard.common import date_filter, fmt_hours, load_enriched_stats, page_header, require_client, sidebar_refresh

sidebar_refresh()
page_header("Practice vs Race", "Clean-lap rate by session type, how it's trending, and the tracks where race-day costs you the most.")

df = load_enriched_stats(require_client())
df = date_filter(df, key="pvr_range")
if df.empty:
    st.info("No driving in this time range.")
    st.stop()

by_session = summarize(df, "session")
by_session["order"] = by_session["session"].map({s: i for i, s in enumerate(SESSION_ORDER)}).fillna(99)
by_session = by_session.sort_values("order")

cols = st.columns(max(len(by_session), 1))
for col, (_, row) in zip(cols, by_session.iterrows()):
    with col.container(border=True):
        st.markdown(f"**{row['session']}**")
        st.metric("Clean laps", f"{row['clean_pct']:.0f}%")
        st.caption(f"{int(row['laps']):,} laps · {fmt_hours(row['hours'])} · {int(row['events']):,} events")

practice = by_session.set_index("session")["clean_pct"].get("Practice")
race = by_session.set_index("session")["clean_pct"].get("Race")
if practice is not None and race is not None:
    diff = practice - race
    if diff > 0:
        st.markdown(f"Your race laps are **{diff:.0f} points less clean** than your practice laps.")
    else:
        st.markdown(f"Your race laps are **{-diff:.0f} points cleaner** than your practice laps.")

# Monthly trend: one line per session type, fixed color per session.
monthly = monthly_clean_pct(df, "session")
if not monthly.empty:
    sessions = [s for s in SESSION_ORDER if s in set(monthly["session"])]
    sessions += sorted(set(monthly["session"]) - set(sessions))
    fig = px.line(
        monthly,
        x="month",
        y="clean_pct",
        color="session",
        markers=True,
        category_orders={"session": sessions},
        color_discrete_map=SESSION_COLORS,
        custom_data=["lapsDriven"],
        labels={"month": "", "clean_pct": "Clean laps (%)", "session": ""},
    )
    fig.update_traces(
        line_width=2,
        marker_size=8,
        hovertemplate="%{x|%b %Y}: %{y:.0f}% clean over %{customdata[0]:,} laps<extra>%{fullData.name}</extra>",
    )
    fig.update_layout(
        height=340,
        margin=dict(l=0, r=10, t=10, b=0),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        yaxis=dict(range=[0, 100], gridcolor="rgba(128,128,128,0.15)"),
    )
    st.markdown("##### Clean-lap rate by month")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption("Months with fewer than 20 laps in a session type are left out, so a handful of laps can't swing the line.")

st.markdown("##### Tracks where racing costs you the most")
gap = practice_race_gap(df)
if gap.empty:
    st.info("Not enough tracks with both practice and race laps (20+ of each) in this time range.")
else:
    st.caption("Tracks with 20+ practice laps and 20+ race laps. Gap = practice clean % minus race clean %.")
    st.dataframe(
        gap,
        column_config={
            "track_name": st.column_config.TextColumn("Track"),
            "practice_laps": st.column_config.NumberColumn("Practice laps", format="%d"),
            "race_laps": st.column_config.NumberColumn("Race laps", format="%d"),
            "practice_clean_pct": st.column_config.ProgressColumn("Practice clean %", format="%.0f%%", min_value=0, max_value=100),
            "race_clean_pct": st.column_config.ProgressColumn("Race clean %", format="%.0f%%", min_value=0, max_value=100),
            "gap": st.column_config.NumberColumn("Gap (pts)", format="%+.0f"),
        },
        hide_index=True,
        width="stretch",
    )

with st.expander("About session types"):
    st.markdown(
        "Garage 61 labels each session with a number. This page reads **1 as Practice, "
        "2 as Qualifying and 3 as Race**; any other number shows as \"Session N\". "
        "If a day you know you raced shows up as practice, the labels in "
        "`dashboard/analysis.py` (`SESSION_TYPES`) need adjusting."
    )
