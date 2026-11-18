"""SQLite helpers. One shared connection; all access happens on the asyncio thread."""
import os
import sqlite3

from config import DB_PATH

_conn = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
  crate_id TEXT, ts TEXT, stage TEXT, location_name TEXT, truck_id TEXT,
  temp_c REAL, humidity REAL, voc_index REAL, door_open INTEGER,
  tvc REAL, freshness_score REAL, eff_rate REAL, extra_loss_h REAL, minutes REAL
);
CREATE INDEX IF NOT EXISTS idx_readings_crate ON readings(crate_id, ts);
"""

COLUMNS = [
    "crate_id", "ts", "stage", "location_name", "truck_id",
    "temp_c", "humidity", "voc_index", "door_open",
    "tvc", "freshness_score", "eff_rate", "extra_loss_h", "minutes",
]


def conn():
    global _conn
    if _conn is None:
        path = os.environ.get("FRESHSENSE_DB", str(DB_PATH))
        _conn = sqlite3.connect(path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn


def reset_db():
    c = conn()
    c.execute("DROP TABLE IF EXISTS readings")
    c.executescript(SCHEMA)
    c.commit()


def insert_readings(rows):
    if not rows:
        return
    c = conn()
    c.executemany(f"INSERT INTO readings VALUES ({','.join('?' * len(COLUMNS))})", rows)
    c.commit()


def get_readings(crate_id):
    cur = conn().execute(
        "SELECT * FROM readings WHERE crate_id = ? ORDER BY ts, rowid", (crate_id,)
    )
    return [dict(r) for r in cur.fetchall()]


def extra_loss_by_stage():
    cur = conn().execute(
        "SELECT stage, SUM(extra_loss_h) AS extra FROM readings GROUP BY stage"
    )
    return {r["stage"]: r["extra"] or 0.0 for r in cur.fetchall()}
