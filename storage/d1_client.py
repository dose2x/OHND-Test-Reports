"""
Minimal client for Cloudflare D1's HTTP query API.

Docs: https://developers.cloudflare.com/api/resources/d1/subresources/database/methods/query/
Table definition: schema.sql
"""

from __future__ import annotations

import json
from typing import Any

import requests

from .config import D1Config
from .laps import driver_name, track_name

_CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4"
_TIMEOUT = 30

# D1 allows at most 100 bound parameters per query
# (https://developers.cloudflare.com/d1/platform/limits/).
_MAX_PARAMS = 100

_LAP_COLUMNS = (
    "id, driver_slug, driver_name, track_id, track_name, "
    "car_id, car_name, session_type, lap_time, driven_at, raw_json"
)
_PARAMS_PER_LAP = 11
_LAPS_PER_INSERT = _MAX_PARAMS // _PARAMS_PER_LAP  # 9 laps per request instead of 1

# Upsert: insert laps, or refresh them (and their cached raw payload) if
# we've already stored those lap ids before.
_UPSERT_CONFLICT_SQL = """
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
        response = self._session.post(url, json={"sql": sql, "params": params or []}, timeout=_TIMEOUT)
        try:
            payload = response.json()
        except ValueError:
            response.raise_for_status()
            raise

        # Cloudflare explains failures (bad token, SQL error) in "errors";
        # show that instead of a bare "400 Bad Request".
        if not response.ok or not payload.get("success"):
            raise RuntimeError(f"D1 query failed ({response.status_code}): {payload.get('errors')}")

        # Cloudflare returns one result block per statement; we only send one.
        return payload["result"][0]["results"]

    def upsert_lap(self, lap: dict) -> None:
        """Store (or refresh) a single lap record, as returned by
        Garage61Client.find_all_laps() / get_lap()."""
        self.upsert_laps([lap])

    def upsert_laps(self, laps: list[dict]) -> int:
        """Store (or refresh) many laps, several per request. Returns the
        number processed."""
        for start in range(0, len(laps), _LAPS_PER_INSERT):
            batch = laps[start : start + _LAPS_PER_INSERT]
            placeholders = ", ".join(["(" + ", ".join(["?"] * _PARAMS_PER_LAP) + ")"] * len(batch))
            params = [value for lap in batch for value in _lap_row(lap)]
            self.query(f"INSERT INTO laps ({_LAP_COLUMNS}) VALUES {placeholders} {_UPSERT_CONFLICT_SQL}", params)
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
        existing: set[str] = set()
        for start in range(0, len(ids), _MAX_PARAMS):
            chunk = ids[start : start + _MAX_PARAMS]
            placeholders = ",".join(["?"] * len(chunk))
            rows = self.query(f"SELECT id FROM laps WHERE id IN ({placeholders})", params=chunk)
            existing.update(row["id"] for row in rows)
        return existing


def _lap_row(lap: dict) -> list[Any]:
    """One lap as values for _LAP_COLUMNS, in order."""
    track = lap.get("track") or {}
    car = lap.get("car") or {}
    driver = lap.get("driver") or {}
    return [
        lap.get("id"),
        driver.get("slug"),
        driver_name(lap),
        track.get("id"),
        track_name(lap),
        car.get("id"),
        car.get("name"),
        lap.get("sessionType"),
        lap.get("lapTime"),
        lap.get("startTime"),
        json.dumps(lap, default=str),
    ]
