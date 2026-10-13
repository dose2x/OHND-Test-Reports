"""Tracks & Cars: where you spend your time, and how clean you are there."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from dashboard.analysis import SERIES_COLOR, needs_work, summarize, totals
from dashboard.common import (
    date_filter,
    fmt_hours,
    load_enriched_stats,
    page_header,
    require_client,
    session_filter,
    sidebar_refresh,
)

sidebar_refresh()
page_header("Tracks & Cars", "Where you spend your seat time, and how clean your laps are at each track and in each car.")

df = load_enriched_stats(require_client())
df = date_filter(df, key="tc_range")
df = session_filter(df, key="tc_sessions")
if df.empty:
    st.info("No driving in this time range / session selection.")
    st.stop()

t = totals(df)
cols = st.columns(5)
cols[0].metric("Laps", f"{t['laps']:,}")
cols[1].metric("Clean laps", f"{t['clean_pct']:.0f}%", help=f"{t['clean_laps']:,} clean laps")
cols[2].metric("Time on track", fmt_hours(t["hours"]))
cols[3].metric("Tracks", f"{t['tracks']:,}")
cols[4].metric("Cars", f"{t['cars']:,}")

TABLE_COLUMNS = {
    "laps": st.column_config.NumberColumn("Laps", format="%d"),
    "clean_pct": st.column_config.ProgressColumn("Clean %", format="%.0f%%", min_value=0, max_value=100),
    "hours": st.column_config.NumberColumn("Hours", format="%.1f"),
    "events": st.column_config.NumberColumn("Events", format="%d"),
    "days": st.column_config.NumberColumn("Days", format="%d"),
    "last_driven": st.column_config.DateColumn("Last driven", format="MMM D, YYYY"),
}


def time_chart(summary, name_col: str, label: str, top: int = 12):
    """Horizontal bars: hours on track for the top N, biggest at the top."""
    top_rows = summary.head(top).iloc[::-1]
    fig = px.bar(
        top_rows,
        x="hours",
        y=name_col,
        orientation="h",
        custom_data=["laps", "clean_pct"],
        labels={"hours": "Hours on track", name_col: ""},
        color_discrete_sequence=[SERIES_COLOR],
    )
    fig.update_traces(
        hovertemplate=f"<b>%{{y}}</b><br>%{{x:.1f}} h · %{{customdata[0]:,}} laps · %{{customdata[1]:.0f}}% clean<extra></extra>",
        marker_line_width=0,
    )
    fig.update_layout(
        height=max(260, 28 * len(top_rows) + 60),
        margin=dict(l=0, r=10, t=10, b=0),
        bargap=0.25,
        xaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.15)", zeroline=False),
    )
    st.markdown(f"##### Most time on track — top {min(top, len(summary))} {label}")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def needs_work_callout(summary, name_col: str, label: str) -> None:
    worst = needs_work(summary, name_col)
    if worst.empty:
        return
    lines = [f"**{r[name_col]}** — {r['clean_pct']:.0f}% clean over {int(r['laps']):,} laps" for _, r in worst.iterrows()]
    st.markdown(f"**Least clean {label}** (with 50+ laps):  \n" + "  \n".join(lines))


tab_tracks, tab_cars, tab_classes = st.tabs(["Tracks", "Cars", "Car classes"])

with tab_tracks:
    tracks = summarize(df, "track_name")
    left, right = st.columns([3, 2])
    with left:
        time_chart(tracks, "track_name", "tracks")
    with right:
        needs_work_callout(tracks, "track_name", "tracks")
    st.dataframe(
        tracks[["track_name", "laps", "clean_pct", "hours", "events", "days", "last_driven"]],
        column_config={"track_name": st.column_config.TextColumn("Track"), **TABLE_COLUMNS},
        hide_index=True,
        width="stretch",
    )

with tab_cars:
    cars = summarize(df, ["car_name", "car_class"])
    left, right = st.columns([3, 2])
    with left:
        time_chart(cars, "car_name", "cars")
    with right:
        needs_work_callout(cars, "car_name", "cars")
    st.dataframe(
        cars[["car_name", "car_class", "laps", "clean_pct", "hours", "events", "days", "last_driven"]],
        column_config={
            "car_name": st.column_config.TextColumn("Car"),
            "car_class": st.column_config.TextColumn("Class"),
            **TABLE_COLUMNS,
        },
        hide_index=True,
        width="stretch",
    )

with tab_classes:
    st.caption("A car in more than one class (e.g. GT3 and an endurance group) counts toward each.")
    exploded = df.assign(car_class=df["car_class"].str.split(", ")).explode("car_class")
    classes = summarize(exploded, "car_class")
    st.dataframe(
        classes[["car_class", "laps", "clean_pct", "hours", "events", "days", "last_driven"]],
        column_config={"car_class": st.column_config.TextColumn("Class"), **TABLE_COLUMNS},
        hide_index=True,
        width="stretch",
    )

unnamed = df[df["track_name"].str.startswith("Track #") | df["car_name"].str.startswith("Car #")]
if not unnamed.empty:
    st.caption(f"{len(unnamed):,} rows use a car or track Garage 61 didn't return a name for; they're shown by ID number.")
