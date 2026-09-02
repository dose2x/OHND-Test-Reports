# OHND Test Data App

A Python scaffold for pulling and analyzing telemetry / lap data from the
[Garage 61](https://garage61.net) API, for the OHND Racing team.

This is an early framework: authentication, a typed API client, a
connection test script, and a Streamlit dashboard. More analysis features
can be layered on as the project's direction firms up.

## Setup

1. **Install dependencies** (Python 3.10+ recommended):

   ```bash
   pip install -r requirements.txt
   ```

2. **Get your API token.** If you don't have one yet, request a personal
   access token at <https://garage61.net/developer/applications> (owned by
   the OHND Racing team). Garage 61 reviews these requests manually, so it
   may take a bit before it's issued.

3. **Configure your token:**

   ```bash
   cp .env.example .env
   ```

   Then open `.env` and paste your token into `GARAGE61_TOKEN`. This file
   is gitignored — never commit real tokens.

4. **Test the connection:**

   ```bash
   python scripts/test_connection.py
   ```

   You should see your account name and teams printed out.

5. **Launch the dashboard:**

   ```bash
   streamlit run app.py
   ```

   This opens a browser tab (usually at http://localhost:8501) with an
   overview of your account: profile info, driving statistics, linked
   accounts (e.g. iRacing), and your teams (with per-team stats). Use the
   "Refresh data" button in the sidebar to clear the cache and re-fetch.
   If `GARAGE61_TOKEN` isn't set yet, the dashboard shows setup
   instructions instead of crashing.

6. **(Optional) Sync laps into Cloudflare D1.** A D1 database called
   `ohnd-telemetry` already exists in the OHND Cloudflare account, for
   durable storage of pulled lap data (so it doesn't need to be
   re-downloaded from Garage 61 every time). To use it:

   - Create a Cloudflare API token: Cloudflare dashboard → **My Profile →
     API Tokens → Create Token** → use the "Edit Cloudflare Workers" template
     or a custom token with **D1: Edit** permission, scoped to your account.
   - Fill in `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` in `.env`
     (`CLOUDFLARE_D1_DATABASE_ID` is already filled in).
   - Run:

     ```bash
     python scripts/sync_laps.py --tracks 123 --cars 45
     ```

     (Use real track/car IDs from `client.get_tracks()` / `client.get_cars()`
     — Garage 61 requires at least one of tracks/cars/drivers/teams to
     search.) This upserts matching laps into the `laps` table in D1,
     storing both parsed columns (track, car, lap time, etc.) and the full
     raw API response per lap. Laps not already in D1 are reported as
     "new" — see the next step for getting notified about them.

7. **(Optional) Get notified about new laps.** `scripts/sync_laps.py`
   detects which synced laps are new (vs. laps it's seen before) and can
   send an email to **pvisracing@gmx.com** when it finds some. This goes
   through a Zap you build once in the Zapier web app, since Claude's own
   Zapier actions only run during a live chat session:

   1. In Zapier, create a new Zap.
   2. Trigger: **Webhooks by Zapier** → **Catch Hook**. Copy the webhook
      URL it gives you.
   3. Action: **Email by Zapier** → **Send Outbound Email**:
      - To: `pvisracing@gmx.com`
      - Subject: `New laps synced ({{count}})`
      - Body: `{{summary}}`
      (`count` and `summary` come from the webhook payload `sync_laps.py`
      sends — see `storage/notify.py`.)
   4. Turn the Zap on, then paste the webhook URL into
      `ZAPIER_NOTIFY_WEBHOOK_URL` in `.env`.

   Until that's set, `sync_laps.py` still runs and prints what it found —
   it just skips sending the email.

## Project layout

```
ohnd-test-data-app/
├── app.py               # Streamlit dashboard entry point (overview page)
├── dashboard/
│   ├── data.py          # Cached wrappers around Garage61Client calls
│   └── ui.py             # Reusable Streamlit display helpers
├── garage61/            # The API client package
│   ├── client.py        # Garage61Client — wraps the REST API
│   ├── config.py        # Loads GARAGE61_TOKEN from .env
│   └── exceptions.py    # Garage61APIError / AuthError / RateLimitError
├── storage/              # Cloudflare D1 storage layer
│   ├── config.py        # Loads CLOUDFLARE_* from .env
│   ├── d1_client.py      # D1Client — upserts laps via D1's HTTP query API
│   └── notify.py         # Emails pvisracing@gmx.com about new laps (via a Zap webhook)
├── scripts/
│   ├── test_connection.py
│   └── sync_laps.py      # Pulls laps from Garage 61, stores in D1, notifies on new ones
├── data/                 # Downloaded laps/telemetry land here (gitignored)
├── .env.example
└── requirements.txt
```

## Using the client

```python
from garage61 import Garage61Client

client = Garage61Client()

me = client.get_me()
tracks = client.get_tracks()

# Find your own personal-best laps at a given track (see Garage 61's
# "Find laps" docs for all available filters, e.g. sessionTypes, minLapTime).
laps = client.find_laps(tracks=[123], drivers=["me"])

# Pull full telemetry for one lap as a pandas DataFrame.
if laps:
    df = client.get_lap_dataframe(laps[0]["id"])
    print(df.head())
```

See the [endpoints reference](https://garage61.net/developer/endpoints) for
the full list of available data (driving data, analyses, teams, data packs,
training plans) and the
[lap filtering guide](https://garage61.net/docs/usage/filtering) for how
`find_laps` filters work.

## Notes on permissions

Your personal access token is scoped to the permissions selected when it
was requested (e.g. `driving_data` is required for `find_laps` /
`get_lap_csv`). If you hit a 403/permission error, you may need to request
a new token with additional scopes from the
[applications page](https://garage61.net/developer/applications) — see the
[permissions reference](https://garage61.net/developer/permissions).

## Infrastructure status

- **GitHub:** [dose2x/OHND-Test-Reports](https://github.com/dose2x/OHND-Test-Reports) — this code is pushed here
- **Cloudflare D1:** `ohnd-telemetry` database, `laps` table, schema verified live (see above)
- **Zapier:** GitHub connected (used to push this code); email notifications
  configured to send to pvisracing@gmx.com — test email sent successfully.
  The last piece (a webhook-triggered Zap so `sync_laps.py` can notify on
  its own) needs to be built once in the Zapier web app — see step 7 above.
- **Garage 61:** token received and configured in `.env` locally, but not
  yet verified end-to-end — this sandbox can't reach garage61.net
  (network policy), so run `python scripts/test_connection.py` on your own
  machine to confirm it works.

## Next steps

Ideas for where to take this next, once the token is active:

- A "Lap Browser" dashboard page: filter laps by track/car/session type,
  then view speed/throttle/brake telemetry traces for a selected lap.
- A "Lap Comparison" page: pick two laps, see the time delta and overlaid
  telemetry to find where time is gained or lost.
- A script to bulk-download laps for a track/car into `data/` as CSVs.

Streamlit's [multi-page app convention](https://docs.streamlit.io/develop/concepts/multipage-apps)
(a `pages/` directory next to `app.py`) is a natural fit for adding the
pages above.
