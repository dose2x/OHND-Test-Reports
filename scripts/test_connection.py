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

    print("Connected to Garage 61 as:")
    print(f"  Name:  {me.get('name')}")
    print(f"  Slug:  {me.get('slug')}")
    print(f"  Email: {me.get('email')}")

    teams = client.find_teams()
    if teams:
        print("\nTeams:")
        for team in teams:
            print(f"  - {team.get('name')} ({team.get('slug')})")
    else:
        print("\nNo teams found.")


if __name__ == "__main__":
    main()
