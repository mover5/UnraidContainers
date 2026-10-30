import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS manual_ip (
    ip TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS manual_mac (
    mac TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS range_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cidr TEXT NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS owner_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT NOT NULL,
    replacement TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS ips (
    ip TEXT PRIMARY KEY,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    is_lan INTEGER NOT NULL DEFAULT 0,
    mac TEXT,
    vendor TEXT,
    name TEXT,
    kind TEXT,
    source TEXT,
    owner TEXT,
    asn INTEGER,
    location TEXT,
    country TEXT,
    rdns TEXT,
    rdns_checked_at TEXT,
    reviewed INTEGER NOT NULL DEFAULT 0,
    label_written_at TEXT,
    label_written_hash TEXT
);
CREATE TABLE IF NOT EXISTS ip_daily (
    ip TEXT NOT NULL,
    day TEXT NOT NULL,
    bytes_sent REAL NOT NULL DEFAULT 0,
    bytes_recv REAL NOT NULL DEFAULT 0,
    samples INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (ip, day)
);
CREATE TABLE IF NOT EXISTS ip_mac_daily (
    ip TEXT NOT NULL,
    mac TEXT NOT NULL,
    day TEXT NOT NULL,
    samples INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (ip, mac, day)
);
CREATE TABLE IF NOT EXISTS macs (
    mac TEXT PRIMARY KEY,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    last_ip TEXT
);
CREATE TABLE IF NOT EXISTS tautulli (
    ip TEXT PRIMARY KEY,
    user TEXT NOT NULL,
    friendly_name TEXT NOT NULL,
    player TEXT NOT NULL DEFAULT '',
    platform TEXT NOT NULL DEFAULT '',
    last_seen_epoch INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS adguard (
    key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    origin TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_status (
    source TEXT PRIMARY KEY,
    last_attempt TEXT,
    last_success TEXT,
    last_error TEXT,
    detail TEXT
);
CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_ip_daily_day ON ip_daily(day);
CREATE INDEX IF NOT EXISTS ix_ip_mac_daily_day ON ip_mac_daily(day);
"""

# Seeded once, on first start. Owner names come from MaxMind's ASN database.
SEED_MANUAL_MAC = [
    ("cc:40:d0:74:bf:ef", "R8000 router", "router"),
    ("0c:42:a1:63:8c:ec", "Unraid", "server"),
    ("02:42:c0:a8:01:02", "AdGuard Home", "server"),
]
SEED_MANUAL_IP = [
    ("98.232.108.93", "Home WAN (R8000)", "wan",
     "Our public IP. Seen on the LAN when the router hairpins traffic aimed at our own public address."),
]
SEED_OWNER_RULES = [
    ("GOOGLE-CLOUD-PLATFORM", "Google Cloud"),
    ("GOOGLE*", "Google"),
    ("AMAZON-*", "Amazon AWS"),
    ("AKAMAI-*", "Akamai"),
    ("FASTLY", "Fastly"),
    ("CLOUDFLARENET", "Cloudflare"),
    ("MICROSOFT-CORP-*", "Microsoft"),
    ("APPLE-*", "Apple"),
    ("AS714", "Apple"),
    ("AS2906", "Netflix"),
    ("FACEBOOK", "Meta"),
    ("COMCAST-*", "Comcast"),
]


def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Database:
    def __init__(self, config_path):
        os.makedirs(config_path, exist_ok=True)
        self.db_path = os.path.join(config_path, "ip-directory.db")
        self._local = threading.local()
        self._init_db()

    def _connect(self):
        # One long-lived connection per thread: opening/closing per call forces a WAL checkpoint each time.
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            # Safe with WAL; a power cut can lose at most the last commit, which the next refresh redoes.
            conn.execute("PRAGMA synchronous = NORMAL")
            self._local.conn = conn
        return conn

    @contextmanager
    def tx(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _init_db(self):
        with self.tx() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(SCHEMA)
            if conn.execute("SELECT value FROM kv WHERE key = 'seeded'").fetchone() is None:
                now = utcnow()
                conn.executemany(
                    "INSERT OR IGNORE INTO manual_mac (mac, name, kind, updated_at) VALUES (?, ?, ?, ?)",
                    [(m, n, k, now) for m, n, k in SEED_MANUAL_MAC],
                )
                conn.executemany(
                    "INSERT OR IGNORE INTO manual_ip (ip, name, kind, notes, updated_at) VALUES (?, ?, ?, ?, ?)",
                    [(i, n, k, notes, now) for i, n, k, notes in SEED_MANUAL_IP],
                )
                conn.executemany(
                    "INSERT INTO owner_rules (pattern, replacement, position) VALUES (?, ?, ?)",
                    [(p, r, pos) for pos, (p, r) in enumerate(SEED_OWNER_RULES)],
                )
                conn.execute("INSERT INTO kv (key, value) VALUES ('seeded', ?)", (now,))

    def query(self, sql, params=()):
        with self.tx() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def query_one(self, sql, params=()):
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql, params=()):
        with self.tx() as conn:
            conn.execute(sql, params)

    def get_kv(self, key, default=None):
        row = self.query_one("SELECT value FROM kv WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_kv(self, key, value):
        self.execute("INSERT OR REPLACE INTO kv (key, value) VALUES (?, ?)", (key, str(value)))

    def record_status(self, source, ok, detail="", error=""):
        now = utcnow()
        with self.tx() as conn:
            conn.execute("INSERT OR IGNORE INTO source_status (source) VALUES (?)", (source,))
            if ok:
                conn.execute(
                    "UPDATE source_status SET last_attempt = ?, last_success = ?, last_error = NULL, detail = ? WHERE source = ?",
                    (now, now, detail, source),
                )
            else:
                conn.execute(
                    "UPDATE source_status SET last_attempt = ?, last_error = ?, detail = ? WHERE source = ?",
                    (now, error, detail, source),
                )
