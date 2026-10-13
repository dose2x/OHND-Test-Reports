"""
Turn Garage 61 driving statistics into named, season-tagged tables.

Everything here is plain pandas (no Streamlit), so it can be tested on its
own. Works with the permissions the current token has (profile / analyses):
driving statistics, cars, tracks, car groups and platforms/seasons. No lap
or telemetry data is needed.

A statistics row looks like:
    {"day": "2024-11-12", "car": 1, "track": 31, "sessionType": 1,
     "events": 1, "timeOnTrack": 2396.6, "lapsDriven": 21, "cleanLapsDriven": 10}
Team statistics rows also carry "user" (the driver's slug).
"""

from __future__ import annotations

import pandas as pd

# Garage 61's numeric session types. Not documented in the API reference,
# so these are best-understood labels; unknown codes show as "Session N".
SESSION_TYPES: dict[int, str] = {1: "Practice", 2: "Qualifying", 3: "Race"}
SESSION_ORDER = ["Practice", "Qualifying", "Race"]

# Fixed colors per session type (color follows the session, never its rank).
SESSION_COLORS = {"Practice": "#2a78d6", "Qualifying": "#eb6834", "Race": "#1baf7a"}
SERIES_COLOR = "#2a78d6"   # single-series charts
MUTED_COLOR = "#9a9a94"    # secondary series, e.g. "all laps" behind "clean laps"

_NUMERIC = ("events", "timeOnTrack", "lapsDriven", "cleanLapsDriven")


def session_label(code) -> str:
    try:
        code = int(code)
    except (TypeError, ValueError):
        return "Unknown"
    return SESSION_TYPES.get(code, f"Session {code}")


def track_label(track: dict) -> str:
    name = track.get("name") or f"Track #{track.get('id')}"
    variant = (track.get("variant") or "").strip()
    return f"{name} – {variant}" if variant else name


def enrich_stats(
    stats: dict,
    cars: list[dict] | None = None,
    tracks: list[dict] | None = None,
    car_groups: list[dict] | None = None,
    platforms: list[dict] | None = None,
) -> pd.DataFrame:
    """One row per day/car/track/session type, with names, class, session
    label, and iRacing season + week added. Empty DataFrame if no data."""
    rows = (stats or {}).get("drivingStatistics")
    if not isinstance(rows, list):
        rows = []
    df = pd.DataFrame([r for r in rows if isinstance(r, dict)])
    if df.empty or "day" not in df:
        return pd.DataFrame()

    df["day"] = pd.to_datetime(df["day"], errors="coerce")
    df = df.dropna(subset=["day"]).copy()
    for col in _NUMERIC:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0) if col in df else 0

    car_names = {c.get("id"): c.get("name") for c in cars or [] if isinstance(c, dict)}
    track_names = {t.get("id"): track_label(t) for t in tracks or [] if isinstance(t, dict)}
    classes: dict = {}
    for group in car_groups or []:
        if not isinstance(group, dict):
            continue
        for car_id in group.get("cars") or []:
            classes.setdefault(car_id, []).append(group.get("name", ""))

    df["car_name"] = [car_names.get(c) or f"Car #{c}" for c in df.get("car", pd.Series(dtype=object))]
    df["track_name"] = [track_names.get(t) or f"Track #{t}" for t in df.get("track", pd.Series(dtype=object))]
    df["car_class"] = [", ".join(sorted(set(classes.get(c, [])))) or "—" for c in df.get("car", pd.Series(dtype=object))]
    df["session"] = [session_label(s) for s in df.get("sessionType", pd.Series(dtype=object))]

    seasons = iracing_seasons(platforms)
    df["season"] = None
    df["season_week"] = pd.NA
    for season in seasons:
        mask = (df["day"] >= season["start"]) & (df["day"] < season["end"])
        df.loc[mask, "season"] = season["name"]
        df.loc[mask, "season_week"] = ((df.loc[mask, "day"] - season["start"]).dt.days // 7 + 1).astype(int)
    return df


def iracing_seasons(platforms: list[dict] | None) -> list[dict]:
    """iRacing seasons as [{"name", "short", "start", "end"}], newest first.
    Dates are tz-naive (matching the statistics' day column)."""
    out = []
    for platform in platforms or []:
        if not isinstance(platform, dict) or platform.get("id") != "iracing":
            continue
        for s in platform.get("seasons") or []:
            start = pd.to_datetime(s.get("start"), errors="coerce", utc=True)
            end = pd.to_datetime(s.get("end"), errors="coerce", utc=True)
            if pd.isna(start) or pd.isna(end):
                continue
            out.append(
                {
                    "name": s.get("name") or s.get("shortName") or "Season",
                    "short": s.get("shortName") or s.get("name"),
                    "start": start.tz_localize(None).normalize(),
                    "end": end.tz_localize(None).normalize(),
                }
            )
    return sorted(out, key=lambda s: s["start"], reverse=True)


def summarize(df: pd.DataFrame, by: str | list[str]) -> pd.DataFrame:
    """Totals per group: laps, clean laps, clean %, time on track (hours),
    events, days driven and last day driven. Sorted by time on track."""
    if df.empty:
        return pd.DataFrame()
    grouped = df.groupby(by, dropna=False)
    out = grouped.agg(
        laps=("lapsDriven", "sum"),
        clean_laps=("cleanLapsDriven", "sum"),
        seconds=("timeOnTrack", "sum"),
        events=("events", "sum"),
        days=("day", lambda d: d.dt.date.nunique()),
        last_driven=("day", "max"),
    )
    out["clean_pct"] = (out["clean_laps"] / out["laps"].where(out["laps"] > 0) * 100).fillna(0)
    out["hours"] = out["seconds"] / 3600
    out = out.drop(columns="seconds").sort_values("hours", ascending=False)
    return out.reset_index()


def totals(df: pd.DataFrame) -> dict:
    """Headline numbers for a (possibly filtered) statistics frame."""
    laps = int(df["lapsDriven"].sum()) if not df.empty else 0
    clean = int(df["cleanLapsDriven"].sum()) if not df.empty else 0
    return {
        "laps": laps,
        "clean_laps": clean,
        "clean_pct": clean / laps * 100 if laps else 0.0,
        "hours": float(df["timeOnTrack"].sum()) / 3600 if not df.empty else 0.0,
        "events": int(df["events"].sum()) if not df.empty else 0,
        "days": int(df["day"].dt.date.nunique()) if not df.empty else 0,
        "tracks": int(df["track"].nunique()) if not df.empty and "track" in df else 0,
        "cars": int(df["car"].nunique()) if not df.empty and "car" in df else 0,
    }


def needs_work(summary: pd.DataFrame, name_col: str, min_laps: int = 50, n: int = 3) -> pd.DataFrame:
    """The n groups with the lowest clean-lap % among those with enough laps
    to be meaningful."""
    if summary.empty:
        return summary
    enough = summary[summary["laps"] >= min_laps]
    return enough.nsmallest(n, "clean_pct")[[name_col, "laps", "clean_pct"]]


def monthly_clean_pct(df: pd.DataFrame, by: str = "session", min_laps: int = 20) -> pd.DataFrame:
    """Clean-lap % per month per group; months with fewer than min_laps laps
    in a group are dropped so a handful of laps can't swing the line."""
    if df.empty:
        return pd.DataFrame()
    m = (
        df.assign(month=df["day"].dt.to_period("M").dt.to_timestamp())
        .groupby(["month", by])[["lapsDriven", "cleanLapsDriven"]]
        .sum()
        .reset_index()
    )
    m = m[m["lapsDriven"] >= min_laps].copy()
    m["clean_pct"] = m["cleanLapsDriven"] / m["lapsDriven"] * 100
    return m


def practice_race_gap(df: pd.DataFrame, min_laps: int = 20) -> pd.DataFrame:
    """Per track: practice vs race clean-lap %, for tracks with at least
    min_laps of each. Sorted by how much cleaner practice is than racing."""
    if df.empty:
        return pd.DataFrame()
    s = summarize(df[df["session"].isin(["Practice", "Race"])], ["track_name", "session"])
    if s.empty:
        return s
    wide = s.pivot_table(index="track_name", columns="session", values=["clean_pct", "laps"], aggfunc="first")
    if ("laps", "Practice") not in wide or ("laps", "Race") not in wide:
        return pd.DataFrame()
    out = pd.DataFrame(
        {
            "track_name": wide.index,
            "practice_laps": wide[("laps", "Practice")].values,
            "race_laps": wide[("laps", "Race")].values,
            "practice_clean_pct": wide[("clean_pct", "Practice")].values,
            "race_clean_pct": wide[("clean_pct", "Race")].values,
        }
    ).dropna()
    out = out[(out["practice_laps"] >= min_laps) & (out["race_laps"] >= min_laps)]
    out["gap"] = out["practice_clean_pct"] - out["race_clean_pct"]
    return out.sort_values("gap", ascending=False).reset_index(drop=True)
