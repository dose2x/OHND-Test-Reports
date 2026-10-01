"""
Quick sanity check: confirms your GARAGE61_TOKEN works and prints some
basic info about your account.

Usage:
    python scripts/test_connection.py
"""

import sys
from pathlib import Path

# Allow running this script directly without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from garage61 import Garage61AuthError, Garage61Client  # noqa: E402

# Permissions the lap sync (scripts/sync_laps.py) needs on your token.
_NEEDED_FOR_LAPS = "driving_data"


def main() -> None:
    try:
        client = Garage61Client()
    except RuntimeError as exc:
        print(f"Configuration error: {exc}")
        sys.exit(1)

    try:
        me = client.get_me()
    except Garage61AuthError:
        print("Authentication failed — check that GARAGE61_TOKEN in .env is correct.")
        sys.exit(1)

    name = " ".join(p for p in (me.get("firstName"), me.get("lastName")) if p)
    permissions = me.get("apiPermissions") or []

    print("Connected to Garage 61 as:")
    print(f"  Name:        {name or '(not shared)'}")
    if me.get("nickName"):
        print(f"  Nickname:    {me['nickName']}")
    print(f"  Slug:        {me.get('slug')}")
    print(f"  Plan:        {me.get('subscriptionPlan', 'unknown')}")
    print(f"  Permissions: {', '.join(permissions) or '(none listed)'}")

    teams = client.find_teams()
    if teams:
        print("\nTeams:")
        for team in teams:
            owner = " (owner)" if team.get("isOwner") else ""
            print(f"  - {team.get('name')} ({team.get('slug')}){owner}")
    else:
        print("\nNo teams found.")

    if permissions and _NEEDED_FOR_LAPS not in permissions:
        print(
            f"\nNote: this token doesn't have the '{_NEEDED_FOR_LAPS}' permission, "
            "so lap data (scripts/sync_laps.py) won't work yet. Request a token "
            "with it at https://garage61.net/developer/applications"
        )


if __name__ == "__main__":
    main()
