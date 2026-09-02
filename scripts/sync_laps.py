"""
Pull laps from Garage 61 and store them in the Cloudflare D1 database, so
the dashboard (and any future analysis) can query stored history without
re-hitting the API every time.

Usage:
    python scripts/sync_laps.py --tracks 123 456
    python scripts/sync_laps.py --tracks 123 --cars 7 --limit 200

Requires GARAGE61_TOKEN plus the CLOUDFLARE_* variables in .env (see
README.md for how to create a Cloudflare API token).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from garage61 import Garage61Client  # noqa: E402
from storage import D1Client, notify_new_laps  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracks", type=int, nargs="*", help="Track IDs to search")
    parser.add_argument("--cars", type=int, nargs="*", help="Car IDs to search")
    parser.add_argument(
        "--drivers",
        nargs="*",
        default=["me"],
        help="Drivers to include (default: just yourself)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max laps to fetch")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.tracks and not args.cars:
        print(
            "Note: no --tracks or --cars given; the Garage 61 API requires "
            "at least one of tracks/cars/drivers/teams to search."
        )

    try:
        client = Garage61Client()
        db = D1Client()
    except RuntimeError as exc:
        print(f"Configuration error: {exc}")
        sys.exit(1)

    print("Fetching laps from Garage 61...")
    laps = client.find_laps(
        tracks=args.tracks,
        cars=args.cars,
        drivers=args.drivers,
        limit=args.limit,
    )
    print(f"Found {len(laps)} laps.")

    if not laps:
        return

    existing_ids = db.get_existing_lap_ids([lap.get("id") for lap in laps])
    new_laps = [lap for lap in laps if lap.get("id") not in existing_ids]

    print("Storing in Cloudflare D1...")
    count = db.upsert_laps(laps)
    print(f"Synced {count} laps ({len(new_laps)} new). Total laps in D1: {db.count_laps()}")

    if new_laps:
        if notify_new_laps(new_laps):
            print(f"Sent notification for {len(new_laps)} new laps.")
        else:
            print(
                f"{len(new_laps)} new laps found, but ZAPIER_NOTIFY_WEBHOOK_URL "
                "isn't set — skipping notification. See storage/notify.py."
            )


if __name__ == "__main__":
    main()
