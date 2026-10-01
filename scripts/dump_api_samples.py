"""
Save raw Garage 61 API responses to data/api_samples.json, so the client
and dashboard can be matched to the real response shapes, and so we can see
exactly which endpoints your token's permissions allow.

Usage:
    python scripts/dump_api_samples.py

The output file is in data/, which is gitignored (it contains your
account details), and never includes your token.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from garage61 import Garage61Client  # noqa: E402


def _truncate(value, max_items=3):
    """Keep big lists short so the sample file stays readable."""
    if isinstance(value, list):
        return [_truncate(v, max_items) for v in value[:max_items]] + (
            [f"... {len(value) - max_items} more"] if len(value) > max_items else []
        )
    if isinstance(value, dict):
        return {k: _truncate(v, max_items) for k, v in value.items()}
    return value


def _first_id(data):
    """First item's id from a list or {"items": [...]} response, if any."""
    items = data.get("items") if isinstance(data, dict) else data
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and item.get("id"):
                return item["id"]
    return None


def main() -> None:
    client = Garage61Client()
    samples = {}

    def record(name, call):
        try:
            result = call()
            samples[name] = _truncate(result)
            print(f"OK    {name}")
            return result
        except Exception as exc:  # noqa: BLE001 - we want every result, good or bad
            samples[name] = {"error": f"{type(exc).__name__}: {exc}"}
            print(f"ERROR {name}: {exc}")
            return None

    record("me", client.get_me)
    record("me_accounts", client.get_my_accounts)
    record("me_statistics", client.get_my_statistics)
    teams = record("teams", client.find_teams) or []

    # Content lookups (to turn car/track ids in statistics into names).
    record("cars", client.get_cars)
    record("tracks", client.get_tracks)
    record("car_groups", client.get_car_groups)
    record("platforms", client.get_platforms)

    # Team statistics for the team you own (e.g. OHND Racing).
    owned = next((t for t in teams if isinstance(t, dict) and t.get("isOwner")), None)
    if owned:
        record("team_statistics", lambda: client.get_team_statistics(owned["id"]))

    # Analyses (the "analyses" permission) and one analysis in full.
    analyses = record("analyses", client.find_analyses)
    analysis_id = _first_id(analyses) if analyses else None
    if analysis_id:
        record("analysis_detail", lambda: client.get_analysis(analysis_id))

    # Laps need the "driving_data" permission; this shows whether it's missing.
    record("laps", lambda: client.find_laps(drivers=["me"], limit=1))

    out = ROOT / "data" / "api_samples.json"
    out.write_text(json.dumps(samples, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
