"""
Notify pvisracing@gmx.com when new laps show up during a sync.

This is a plain webhook POST, not a Zapier MCP call — the Zapier actions
Claude used to set this up only work inside a live Claude session, but
scripts/sync_laps.py needs to notify on its own, whenever you (or a cron
job) run it. So instead, this hits a "Catch Hook" webhook URL from a Zap
you build once in the Zapier web app:

  1. https://zapier.com/app/editor -> Create Zap.
  2. Trigger: "Webhooks by Zapier" -> "Catch Hook". Copy the webhook URL
     it gives you into ZAPIER_NOTIFY_WEBHOOK_URL in .env.
  3. Action: "Email by Zapier" -> "Send Outbound Email":
       To:      pvisracing@gmx.com
       Subject: New laps synced ({{count}})
       Body:    {{summary}}
     (count/summary come from the webhook's JSON payload, sent below.)
  4. Turn the Zap on.

Until ZAPIER_NOTIFY_WEBHOOK_URL is set, this is a no-op — sync_laps.py
still runs and prints what it found, it just won't send an email.
"""

from __future__ import annotations

import os

import requests

_MAX_LAPS_LISTED = 20


def notify_new_laps(new_laps: list[dict], webhook_url: str | None = None) -> bool:
    """POST a summary of newly-synced laps to the configured webhook.

    Returns True if a notification was sent, False if skipped (no laps,
    or no webhook URL configured).
    """
    if not new_laps:
        return False

    webhook_url = webhook_url or os.getenv("ZAPIER_NOTIFY_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return False

    lines = [_describe_lap(lap) for lap in new_laps[:_MAX_LAPS_LISTED]]
    if len(new_laps) > _MAX_LAPS_LISTED:
        lines.append(f"...and {len(new_laps) - _MAX_LAPS_LISTED} more")

    payload = {
        "count": len(new_laps),
        "summary": "\n".join(lines),
    }
    response = requests.post(webhook_url, json=payload, timeout=10)
    response.raise_for_status()
    return True


def _describe_lap(lap: dict) -> str:
    driver = (lap.get("driver") or {}).get("name", "Unknown driver")
    track = (lap.get("track") or {}).get("name", "Unknown track")
    car = (lap.get("car") or {}).get("name", "Unknown car")
    lap_time = lap.get("lapTime")
    return f"- {driver}: {lap_time}s at {track} ({car})"
