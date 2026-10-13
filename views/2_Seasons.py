"""Seasons: your driving per iRacing season, week by week."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.analysis import MUTED_COLOR, SERIES_COLOR, iracing_seasons, summarize, totals
from dashboard.common import (
    fmt_hours,
    load_enriched_stats,
    load_lookups_platforms,
    page_header,
    require_client,
    session_filter,
    sidebar_refresh,
)

sidebar_refresh()
page_header("Seasons", "Your driving in each iRacing season, compared with the season before.")

df = load_enriched_stats(require_client())
df = session_filter(df, key="season_sessions")
in_season = df.dropna(subset=["season"])
if in_season.empty:
    st.info("Couldn't match your driving days to iRacing seasons (season dates didn't load).")
    st.stop()

# Seasons you actually drove in, newest first.
order = in_season.groupby("season")["day"].min().sort_values(ascending=False).index.tolist()
season = st.selectbox("Season", order, index=0)
current = in_season[in_season["season"] == season]
previous_name = order[order.index(season) + 1] if order.index(season) + 1 < len(order) else None
previous = in_season[in_season["season"] == previous_name] if previous_name else None

# A season still in progress is compared with the same number of weeks of
# the previous one, so a half-finished season doesn't look like a slump.
season_info = next((s for s in iracing_seasons(load_lookups_platforms()) if s["name"] == season), None)
today = pd.Timestamp.today().normalize()
weeks_so_far = None
if season_info and season_info["start"] <= today < season_info["end"]:
    weeks_so_far = (today - season_info["start"]).days // 7 + 1
    if previous is not None:
        previous = previous[previous["season_week"] <= weeks_so_far]

t = totals(current)
p = totals(previous) if previous is not None else None


def delta(key: str, fmt: str = "{:+,.0f}"):
    return fmt.format(t[key] - p[key]) if p else None


cols = st.columns(5)
cols[0].metric("Laps", f"{t['laps']:,}", delta("laps"))
cols[1].metric("Clean laps", f"{t['clean_pct']:.0f}%", delta("clean_pct", "{:+.0f} pts"))
cols[2].metric("Time on track", fmt_hours(t["hours"]), delta("hours", "{:+,.1f} h"))
cols[3].metric("Events", f"{t['events']:,}", delta("events"))
cols[4].metric("Days driven", f"{t['days']:,}", delta("days"))
if previous_name and weeks_so_far:
    st.caption(
        f"{season} is in progress (week {weeks_so_far}), so changes are compared with "
        f"the first {weeks_so_far} weeks of {previous_name}."
    )
elif previous_name:
    st.caption(f"Changes are compared with {previous_name}.")

# Week-by-week: laps (bars), clean laps overlaid in the same unit.
weekly = (
    current.groupby("season_week")[["lapsDriven", "cleanLapsDriven"]]
    .sum()
    .reindex(range(1, int(current["season_week"].max()) + 1), fill_value=0)
    .reset_index()
    .rename(columns={"season_week": "Week", "lapsDriven": "All laps", "cleanLapsDriven": "Clean laps"})
)
long = weekly.melt(id_vars="Week", var_name="Laps", value_name="Count")
fig = px.bar(
    long,
    x="Week",
    y="Count",
    color="Laps",
    barmode="group",
    color_discrete_map={"All laps": MUTED_COLOR, "Clean laps": SERIES_COLOR},
    labels={"Count": "Laps", "Laps": ""},
)
fig.update_traces(marker_line_width=0, hovertemplate="Week %{x}: %{y:,} laps<extra>%{fullData.name}</extra>")
fig.update_layout(
    height=320,
    margin=dict(l=0, r=10, t=10, b=0),
    bargap=0.25,
    bargroupgap=0.08,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    xaxis=dict(dtick=1),
    yaxis=dict(gridcolor="rgba(128,128,128,0.15)"),
)
st.markdown("##### Laps by week")
st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

st.markdown("##### Week by week")
week_rows = []
for week, rows in current.groupby("season_week"):
    w = totals(rows)
    top_tracks = rows.groupby("track_name")["timeOnTrack"].sum().sort_values(ascending=False).index[:2]
    week_rows.append(
        {
            "Week": int(week),
            "Tracks": ", ".join(top_tracks),
            "Cars": ", ".join(rows.groupby("car_name")["timeOnTrack"].sum().sort_values(ascending=False).index[:2]),
            "Laps": w["laps"],
            "Clean %": w["clean_pct"],
            "Hours": w["hours"],
        }
    )
st.dataframe(
    week_rows,
    column_config={
        "Clean %": st.column_config.ProgressColumn("Clean %", format="%.0f%%", min_value=0, max_value=100),
        "Hours": st.column_config.NumberColumn("Hours", format="%.1f"),
    },
    hide_index=True,
    width="stretch",
)

st.divider()
st.markdown("##### All seasons")
all_seasons = summarize(in_season, "season").set_index("season").loc[order].reset_index()
st.dataframe(
    all_seasons[["season", "laps", "clean_pct", "hours", "events", "days"]],
    column_config={
        "season": st.column_config.TextColumn("Season"),
        "laps": st.column_config.NumberColumn("Laps", format="%d"),
        "clean_pct": st.column_config.ProgressColumn("Clean %", format="%.0f%%", min_value=0, max_value=100),
        "hours": st.column_config.NumberColumn("Hours", format="%.1f"),
        "events": st.column_config.NumberColumn("Events", format="%d"),
        "days": st.column_config.NumberColumn("Days", format="%d"),
    },
    hide_index=True,
    width="stretch",
)
