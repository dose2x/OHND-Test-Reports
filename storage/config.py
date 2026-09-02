"""
Configuration for the Cloudflare D1 storage layer.

D1 is used as durable storage for pulled lap data (instead of, or in
addition to, local CSVs in data/) so it survives across machines/sessions
and can be queried without re-downloading from Garage 61.

The database itself ("ohnd-telemetry") already exists in the OHND
Cloudflare account. To let this app write to it, you need a Cloudflare
API token with D1 edit permissions — see README.md for how to create one.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class D1Config:
    account_id: str
    database_id: str
    api_token: str

    @classmethod
    def from_env(cls, dotenv_path: str | None = None) -> "D1Config":
        load_dotenv(dotenv_path=dotenv_path)

        account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
        database_id = os.getenv("CLOUDFLARE_D1_DATABASE_ID", "").strip()
        api_token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()

        missing = [
            name
            for name, value in [
                ("CLOUDFLARE_ACCOUNT_ID", account_id),
                ("CLOUDFLARE_D1_DATABASE_ID", database_id),
                ("CLOUDFLARE_API_TOKEN", api_token),
            ]
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Missing Cloudflare D1 configuration: "
                + ", ".join(missing)
                + ". Set these in .env — see README.md for how to create a "
                "Cloudflare API token."
            )

        return cls(account_id=account_id, database_id=database_id, api_token=api_token)
