"""
Pull laps from Garage 61 and store them in the Cloudflare D1 database, so
the dashboard (and any future analysis) can query stored history without
re-hitting the API every time.

Usage:
    python scripts/sync_laps.py --tracks 123 456
    python scripts/sync_laps.py --tracks 123 --cars 7 --limit 200
    python scripts/sync_laps.py --tracks 123 --group driver   # personal bests only

Requires GARAGE61_TOKEN plus the CLOUDFLARE_* variables in .env (see
README.md for how to create a Cloudflare API token).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from garage61 import Garage61APIError, Garage61AuthError, Garage61Client  # noqa: E402
from storage import D1Client, notify_new_laps  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tracks", type=int, nargs="*", help="Track IDs to search")
    parser.add_argument("--cars", type=int, nargs="*", help="Car IDs to search")
    parser.add_argument(
        "--drivers",
        nargs="*",
        default=["me"],
        help="Drivers to include (default: just yourself)",
    )
    parser.add_argument(
        "--group",
        choices=["none", "driver", "driver-car"],
        default="none",
        help="none = every lap (default); driver = each driver's personal best; "
        "driver-car = personal best per driver/car",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max laps to fetch (default: all)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.tracks and not args.cars and not args.drivers:
        print("Give at least one of --tracks, --cars, or --drivers; Garage 61 requires one to search.")
        sys.exit(1)

    try:
        client = Garage61Client()
        db = D1Client()
    except RuntimeError as exc:
        print(f"Configuration error: {exc}")
        sys.exit(1)

    print("Fetching laps from Garage 61...")
    try:
        laps = client.find_all_laps(
            tracks=args.tracks,
            cars=args.cars,
            drivers=args.drivers,
            group=args.group,
            max_laps=args.limit,
        )
    except Garage61AuthError:
        print("Garage 61 rejected GARAGE61_TOKEN. Check it in .env, or request a new one.")
        sys.exit(1)
    except (Garage61APIError, requests.exceptions.RequestException) as exc:
        print(f"Couldn't fetch laps from Garage 61: {exc}")
        sys.exit(1)
    print(f"Found {len(laps)} laps.")

    if not laps:
        return

    try:
        existing_ids = db.get_existing_lap_ids([lap.get("id") for lap in laps])
        new_laps = [lap for lap in laps if lap.get("id") not in existing_ids]

        print("Storing in Cloudflare D1...")
        count = db.upsert_laps(laps)
        print(f"Synced {count} laps ({len(new_laps)} new). Total laps in D1: {db.count_laps()}")
    except (RuntimeError, requests.exceptions.RequestException) as exc:
        print(f"Couldn't write to Cloudflare D1: {exc}")
        sys.exit(1)

    if new_laps:
        # The laps are already saved, so a failed email shouldn't fail the sync.
        try:
            sent = notify_new_laps(new_laps)
        except requests.exceptions.RequestException as exc:
            print(f"{len(new_laps)} new laps saved, but the email notification failed: {exc}")
            return
        if sent:
            print(f"Sent notification for {len(new_laps)} new laps.")
        else:
            print(
                f"{len(new_laps)} new laps found, but RESEND_API_KEY or "
                "RESEND_TO_EMAIL isn't set, so no email was sent. See storage/notify.py."
            )


if __name__ == "__main__":
    main()
