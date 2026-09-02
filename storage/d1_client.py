"""
Minimal client for Cloudflare D1's HTTP query API.

Docs: https://developers.cloudflare.com/api/resources/d1/subresources/database/methods/query/
"""

from __future__ import annotations

from typing import Any

import requests

from .config import D1Config

_CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4"

# Upsert: insert a lap, or refresh it (and its cached raw payload) if we've
# already stored that lap id before.
_UPSERT_LAP_SQL = """
INSERT INTO laps (
    id, driver_slug, driver_name, track_id, track_name,
    car_id, car_name, session_type, lap_time, driven_at, raw_json
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    driver_slug = excluded.driver_slug,
    driver_name = excluded.driver_name,
    track_id = excluded.track_id,
    track_name = excluded.track_name,
    car_id = excluded.car_id,
    car_name = excluded.car_name,
    session_type = excluded.session_type,
    lap_time = excluded.lap_time,
    driven_at = excluded.driven_at,
    fetched_at = datetime('now'),
    raw_json = excluded.raw_json
"""


class D1Client:
    def __init__(self, config: D1Config | None = None):
        self.config = config or D1Config.from_env()
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.config.api_token}",
                "Content-Type": "application/json",
            }
        )

    def query(self, sql: str, params: list[Any] | None = None) -> list[dict]:
        """Run a single SQL statement and return its result rows."""
        url = (
            f"{_CLOUDFLARE_API_BASE}/accounts/{self.config.account_id}"
            f"/d1/database/{self.config.database_id}/query"
        )
        response = self._session.post(url, json={"sql": sql, "params": params or []})
        response.raise_for_status()
        payload = response.json()

        if not payload.get("success"):
            raise RuntimeError(f"D1 query failed: {payload.get('errors')}")

        # Cloudflare returns one result block per statement; we only send one.
        return payload["result"][0]["results"]

    def upsert_lap(self, lap: dict) -> None:
        """Store (or refresh) a single lap record, as returned by
        Garage61Client.find_laps() / get_lap()."""
        track = lap.get("track") or {}
        car = lap.get("car") or {}
        driver = lap.get("driver") or {}

        self.query(
            _UPSERT_LAP_SQL,
            params=[
                lap.get("id"),
                driver.get("slug"),
                driver.get("name"),
                track.get("id"),
                track.get("name"),
                car.get("id"),
                car.get("name"),
                lap.get("sessionType"),
                lap.get("lapTime"),
                lap.get("drivenAt"),
                _to_json(lap),
            ],
        )

    def upsert_laps(self, laps: list[dict]) -> int:
        """Store (or refresh) many laps. Returns the number processed."""
        for lap in laps:
            self.upsert_lap(lap)
        return len(laps)

    def count_laps(self) -> int:
        rows = self.query("SELECT COUNT(*) AS n FROM laps")
        return rows[0]["n"] if rows else 0

    def get_existing_lap_ids(self, ids: list[str]) -> set[str]:
        """Which of the given lap ids are already stored in D1.

        Used to figure out which laps in a sync batch are genuinely new,
        e.g. so a notification can be sent only for those.
        """
        ids = [i for i in ids if i]
        if not ids:
            return set()
        placeholders = ",".join(["?"] * len(ids))
        rows = self.query(f"SELECT id FROM laps WHERE id IN ({placeholders})", params=ids)
        return {row["id"] for row in rows}


def _to_json(value: Any) -> str:
    import json

    return json.dumps(value, default=str)
