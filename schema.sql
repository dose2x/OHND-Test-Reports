-- Cloudflare D1 schema for the "ohnd-telemetry" database (copied from the
-- live database). To recreate it:
--   npx wrangler d1 execute ohnd-telemetry --remote --file schema.sql

CREATE TABLE IF NOT EXISTS laps (
  id TEXT PRIMARY KEY,
  driver_slug TEXT,
  driver_name TEXT,
  track_id INTEGER,
  track_name TEXT,
  car_id INTEGER,
  car_name TEXT,
  session_type INTEGER,
  lap_time REAL,
  driven_at TEXT,
  fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
  raw_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_laps_track ON laps(track_id);
CREATE INDEX IF NOT EXISTS idx_laps_car ON laps(car_id);
CREATE INDEX IF NOT EXISTS idx_laps_driver ON laps(driver_slug);
CREATE INDEX IF NOT EXISTS idx_laps_driven_at ON laps(driven_at);
