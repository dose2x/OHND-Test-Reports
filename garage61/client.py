"""
A thin Python client for the Garage 61 API.

Docs: https://garage61.net/developer

Covers the endpoints listed under the Developer Portal's "Endpoints" page
(general info, content lookups, driving data, analyses, and teams). Add
more wrapper methods as your app needs them — `_get` / `_post` / `_delete`
can be used directly for anything not yet wrapped.
"""

from __future__ import annotations

import io
import time
from typing import Any

import pandas as pd
import requests

from .config import Config
from .exceptions import Garage61APIError, Garage61AuthError, Garage61RateLimitError

# Seconds to wait for garage61.net before giving up, so an unattended sync
# can't hang forever on a stalled connection.
_TIMEOUT = 30
# On 429 Too Many Requests, wait Retry-After seconds and retry this many times.
_MAX_RETRIES = 3
_MAX_RETRY_WAIT = 60
# /laps returns at most 1000 laps per request.
_LAPS_PAGE_SIZE = 1000


class Garage61Client:
    def __init__(self, config: Config | None = None):
        self.config = config or Config.from_env()
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.config.token}",
                "Accept": "application/json",
            }
        )

    # ------------------------------------------------------------------
    # Low-level request helpers
    # ------------------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.config.base_url}/{path.lstrip('/')}"

    def _handle_errors(self, response: requests.Response) -> None:
        if response.ok:
            return

        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        message = payload.get("message", response.text or response.reason)

        if response.status_code == 401:
            raise Garage61AuthError(response.status_code, message, payload)
        if response.status_code == 429:
            raise Garage61RateLimitError(
                message,
                retry_after=_retry_after(response),
                payload=payload,
            )
        raise Garage61APIError(response.status_code, message, payload)

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        """Send a request, waiting and retrying when rate limited."""
        for attempt in range(_MAX_RETRIES + 1):
            response = self._session.request(method, self._url(path), timeout=_TIMEOUT, **kwargs)
            if response.status_code != 429 or attempt == _MAX_RETRIES:
                break
            time.sleep(min(_retry_after(response) or 5, _MAX_RETRY_WAIT))
        self._handle_errors(response)
        return response

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._request("GET", path, params=_clean_params(params)).json()

    def _get_raw(self, path: str, params: dict[str, Any] | None = None) -> str:
        """Like `_get`, but returns the raw response body (e.g. CSV) as text."""
        return self._request("GET", path, params=_clean_params(params)).text

    def _post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        response = self._request("POST", path, json=json)
        return response.json() if response.content else None

    def _delete(self, path: str) -> None:
        self._request("DELETE", path)

    # ------------------------------------------------------------------
    # General information
    # ------------------------------------------------------------------

    def get_me(self) -> dict:
        """Information about the currently authenticated user."""
        return self._get("/me")

    def get_my_accounts(self) -> list[dict]:
        """Linked accounts (e.g. iRacing) for the current user."""
        return _items(self._get("/me/accounts"))

    def get_my_statistics(self) -> dict:
        """Personal driving statistics: {"drivingStatistics": [...]}, one row
        per day/track/car/session type."""
        return self._get("/me/statistics")

    # ------------------------------------------------------------------
    # Content lookups
    # ------------------------------------------------------------------

    def get_car_groups(self) -> list[dict]:
        return self._get("/car-groups")

    def get_cars(self) -> list[dict]:
        return self._get("/cars")

    def get_platforms(self) -> list[dict]:
        return self._get("/platforms")

    def get_tracks(self) -> list[dict]:
        return self._get("/tracks")

    # ------------------------------------------------------------------
    # Driving data
    # ------------------------------------------------------------------

    def find_laps(
        self,
        *,
        tracks: list[int] | None = None,
        cars: list[int] | None = None,
        drivers: list[str] | None = None,
        teams: list[str] | None = None,
        group: str = "driver",
        limit: int | None = None,
        offset: int | None = None,
        **extra_params: Any,
    ) -> dict:
        """Find laps / lap records. Returns one page: {"total": n, "items": [...]}.

        You must supply at least one of `tracks`, `cars`, or a user
        (`drivers`/`teams`). `group="driver"` (the API default) returns only
        each driver's personal best; use `group="none"` for every lap. Any
        other supported query parameter (e.g. `sessionTypes`, `minLapTime`,
        `after`) can be passed as a keyword argument. Use `find_all_laps` to
        page through more than 1000 results.
        """
        params = {
            "tracks": tracks,
            "cars": cars,
            "drivers": drivers,
            "teams": teams,
            "group": group,
            "limit": limit,
            "offset": offset,
            **extra_params,
        }
        return self._get("/laps", params=params)

    def find_all_laps(self, *, max_laps: int | None = None, **filters: Any) -> list[dict]:
        """Like `find_laps`, but follows pagination and returns a flat list of
        laps (up to `max_laps`, if given)."""
        laps: list[dict] = []
        while max_laps is None or len(laps) < max_laps:
            page_size = _LAPS_PAGE_SIZE if max_laps is None else min(_LAPS_PAGE_SIZE, max_laps - len(laps))
            page = self.find_laps(limit=page_size, offset=len(laps), **filters)
            items = _items(page)
            laps.extend(items)
            total = page.get("total", 0) if isinstance(page, dict) else len(items)
            if not items or len(laps) >= total:
                break
        return laps

    def get_lap(self, lap_id: str) -> dict:
        return self._get(f"/laps/{lap_id}")

    def get_lap_csv(self, lap_id: str) -> str:
        """Raw telemetry for a lap, as CSV text."""
        return self._get_raw(f"/laps/{lap_id}/csv")

    def get_lap_dataframe(self, lap_id: str) -> pd.DataFrame:
        """Convenience wrapper: telemetry for a lap as a pandas DataFrame."""
        csv_text = self.get_lap_csv(lap_id)
        return pd.read_csv(io.StringIO(csv_text))

    # ------------------------------------------------------------------
    # Analyses
    # ------------------------------------------------------------------

    def find_analyses(self) -> list[dict]:
        return self._get("/analyses")

    def get_analysis(self, analysis_id: str) -> dict:
        return self._get(f"/analyses/{analysis_id}")

    # ------------------------------------------------------------------
    # Teams
    # ------------------------------------------------------------------

    def find_teams(self) -> list[dict]:
        """Teams the current user has joined."""
        return _items(self._get("/teams"))

    def get_team(self, team_id: str) -> dict:
        return self._get(f"/teams/{team_id}")

    def get_team_statistics(self, team_id: str) -> dict:
        return self._get(f"/teams/{team_id}/statistics")


def _items(data: Any) -> list[dict]:
    """List endpoints return {"total": n, "items": [...]}; unwrap the items."""
    if isinstance(data, dict):
        return data.get("items") or []
    return data or []


def _retry_after(response: requests.Response) -> float | None:
    """Garage 61 sends Retry-After in whole seconds."""
    try:
        return float(response.headers.get("Retry-After", ""))
    except ValueError:
        return None


def _clean_params(params: dict[str, Any] | None) -> dict[str, Any]:
    """Drop None values and join lists into comma-separated strings, the
    format the Garage 61 API expects for array query parameters."""
    if not params:
        return {}
    cleaned = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            if not value:
                continue
            cleaned[key] = ",".join(str(v) for v in value)
        else:
            cleaned[key] = value
    return cleaned
