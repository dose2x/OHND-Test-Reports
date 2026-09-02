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
from typing import Any

import pandas as pd
import requests

from .config import Config
from .exceptions import Garage61APIError, Garage61AuthError, Garage61RateLimitError


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
        message = payload.get("message", response.text or response.reason)

        if response.status_code == 401:
            raise Garage61AuthError(response.status_code, message, payload)
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise Garage61RateLimitError(
                message,
                retry_after=float(retry_after) if retry_after else None,
                payload=payload,
            )
        raise Garage61APIError(response.status_code, message, payload)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self._session.get(self._url(path), params=_clean_params(params))
        self._handle_errors(response)
        return response.json()

    def _get_raw(self, path: str, params: dict[str, Any] | None = None) -> str:
        """Like `_get`, but returns the raw response body (e.g. CSV) as text."""
        response = self._session.get(self._url(path), params=_clean_params(params))
        self._handle_errors(response)
        return response.text

    def _post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        response = self._session.post(self._url(path), json=json)
        self._handle_errors(response)
        return response.json() if response.content else None

    def _delete(self, path: str) -> None:
        response = self._session.delete(self._url(path))
        self._handle_errors(response)

    # ------------------------------------------------------------------
    # General information
    # ------------------------------------------------------------------

    def get_me(self) -> dict:
        """Information about the currently authenticated user."""
        return self._get("/me")

    def get_my_accounts(self) -> list[dict]:
        """Linked accounts (e.g. iRacing) for the current user."""
        return self._get("/me/accounts")

    def get_my_statistics(self) -> dict:
        """Personal driving statistics."""
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
        **extra_params: Any,
    ) -> list[dict]:
        """Find laps / lap records.

        You must supply at least one of `tracks`, `cars`, `drivers`, or
        `teams` (a bare user is also enough — see the API docs). Any other
        supported query parameter (e.g. `sessionTypes`, `minLapTime`,
        `after`) can be passed as a keyword argument.
        """
        params = {
            "tracks": tracks,
            "cars": cars,
            "drivers": drivers,
            "teams": teams,
            "group": group,
            "limit": limit,
            **extra_params,
        }
        return self._get("/laps", params=params)

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
        return self._get("/teams")

    def get_team(self, team_id: str) -> dict:
        return self._get(f"/teams/{team_id}")

    def get_team_statistics(self, team_id: str) -> dict:
        return self._get(f"/teams/{team_id}/statistics")


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
