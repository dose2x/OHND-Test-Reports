"""
Notify pvisracing@gmx.com when new laps show up during a sync.

This sends the email directly via Resend (https://resend.com), a
transactional email API with a free tier (100 emails/day, 3,000/month —
plenty for lap syncing) and no OAuth/SMTP setup. No Zapier account is
required for this piece: Zapier's own actions only run during a live
Claude session, so they can't be triggered by an unattended script anyway,
and Zapier's webhook trigger (the alternative) requires a paid plan.

Setup (one-time, free):
  1. Sign up at https://resend.com.
  2. Dashboard -> API Keys -> Create API Key.
  3. Paste it into .env as RESEND_API_KEY.

By default this sends from Resend's shared "onboarding@resend.dev" address,
which works immediately with no domain setup. If you verify your own
sending domain in Resend later, set RESEND_FROM_EMAIL in .env to use it
instead (e.g. "OHND Racing <laps@yourdomain.com>").

Until RESEND_API_KEY is set, this is a no-op — sync_laps.py still runs and
prints what it found, it just won't send an email.
"""

from __future__ import annotations

import os

import requests

_MAX_LAPS_LISTED = 20
_RESEND_API_URL = "https://api.resend.com/emails"
_DEFAULT_FROM = "OHND Test Data App <onboarding@resend.dev>"
_NOTIFY_TO = "pvisracing@gmx.com"


def notify_new_laps(new_laps: list[dict], api_key: str | None = None) -> bool:
    """Email a summary of newly-synced laps to pvisracing@gmx.com.

    Returns True if a notification was sent, False if skipped (no laps,
    or no RESEND_API_KEY configured).
    """
    if not new_laps:
        return False

    api_key = api_key or os.getenv("RESEND_API_KEY", "").strip()
    if not api_key:
        return False

    from_email = os.getenv("RESEND_FROM_EMAIL", "").strip() or _DEFAULT_FROM

    lines = [_describe_lap(lap) for lap in new_laps[:_MAX_LAPS_LISTED]]
    if len(new_laps) > _MAX_LAPS_LISTED:
        lines.append(f"...and {len(new_laps) - _MAX_LAPS_LISTED} more")

    payload = {
        "from": from_email,
        "to": [_NOTIFY_TO],
        "subject": f"New laps synced ({len(new_laps)})",
        "text": "\n".join(lines),
    }
    response = requests.post(
        _RESEND_API_URL,
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=10,
    )
    response.raise_for_status()
    return True


def _describe_lap(lap: dict) -> str:
    driver = (lap.get("driver") or {}).get("name", "Unknown driver")
    track = (lap.get("track") or {}).get("name", "Unknown track")
    car = (lap.get("car") or {}).get("name", "Unknown car")
    lap_time = lap.get("lapTime")
    return f"- {driver}: {lap_time}s at {track} ({car})"
