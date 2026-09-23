"""Pull the fields we store and display out of a Garage 61 lap record.

Field names follow the /laps response documented at
https://garage61.net/developer/endpoints/v1/findLaps
"""

from __future__ import annotations


def driver_name(lap: dict) -> str | None:
    # `driver` can be null when Garage 61 doesn't know who drove the lap.
    driver = lap.get("driver") or {}
    name = " ".join(part for part in (driver.get("firstName"), driver.get("lastName")) if part)
    return name or None


def track_name(lap: dict) -> str | None:
    """Track plus layout, e.g. "Spa-Francorchamps - Grand Prix Pits"."""
    track = lap.get("track") or {}
    name, variant = track.get("name"), track.get("variant")
    if name and variant:
        return f"{name} - {variant}"
    return name or None


def format_lap_time(seconds: float | None) -> str:
    """83.456 -> '1:23.456'."""
    if seconds is None:
        return "?"
    minutes, secs = divmod(float(seconds), 60)
    return f"{int(minutes)}:{secs:06.3f}"
