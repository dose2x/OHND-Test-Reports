"""
Save raw Garage 61 API responses to data/api_samples.json, so the client
and dashboard can be matched to the real response shapes.

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


def main() -> None:
    client = Garage61Client()
    calls = {
        "me": client.get_me,
        "me_accounts": client.get_my_accounts,
        "me_statistics": client.get_my_statistics,
        "teams": client.find_teams,
    }

    samples = {}
    for name, call in calls.items():
        try:
            samples[name] = _truncate(call())
            print(f"OK    {name}")
        except Exception as exc:  # noqa: BLE001 - we want every result, good or bad
            samples[name] = {"error": f"{type(exc).__name__}: {exc}"}
            print(f"ERROR {name}: {exc}")

    out = ROOT / "data" / "api_samples.json"
    out.write_text(json.dumps(samples, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
