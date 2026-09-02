"""
Configuration loading for the Garage 61 API client.

The personal access token is read from the environment (a .env file in the
project root, or real environment variables) — it is never hardcoded here.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_BASE_URL = "https://garage61.net/api/v1"


@dataclass(frozen=True)
class Config:
    token: str
    base_url: str = DEFAULT_BASE_URL

    @classmethod
    def from_env(cls, dotenv_path: str | None = None) -> "Config":
        """Load configuration from environment variables / a .env file.

        Raises:
            RuntimeError: if GARAGE61_TOKEN is not set.
        """
        load_dotenv(dotenv_path=dotenv_path)

        token = os.getenv("GARAGE61_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "GARAGE61_TOKEN is not set. Copy .env.example to .env and "
                "fill in your personal access token from "
                "https://garage61.net/developer/applications"
            )

        base_url = os.getenv("GARAGE61_BASE_URL", DEFAULT_BASE_URL).rstrip("/")

        return cls(token=token, base_url=base_url)
