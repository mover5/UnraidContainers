import sqlite3
import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, config_path):
        os.makedirs(config_path, exist_ok=True)
        self.db_path = os.path.join(config_path, "cleanrr.db")
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS torrents (
                torrent_hash TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                size INTEGER DEFAULT 0,
                state TEXT DEFAULT 'Unknown',
                progress REAL DEFAULT 0,
                ratio REAL DEFAULT 0,
                completed_date TEXT,
                scheduled_removal TEXT,
                protected INTEGER DEFAULT 0,
                removed INTEGER DEFAULT 0,
                removed_date TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL
            )
        """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('seed_time_days', '14')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('check_interval_minutes', '5')"
        )
        conn.commit()
        conn.close()

    def get_settings(self):
        conn = self._get_conn()
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        conn.close()
        return {row["key"]: row["value"] for row in rows}

    def update_setting(self, key, value):
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, str(value)),
        )
        conn.commit()
        conn.close()

    def upsert_torrent(self, torrent_hash, name, size, state, progress, ratio, completed_date, scheduled_removal):
        conn = self._get_conn()
        now = datetime.utcnow().isoformat()
        existing = conn.execute(
            "SELECT torrent_hash FROM torrents WHERE torrent_hash = ?",
            (torrent_hash,),
        ).fetchone()

        if existing:
            conn.execute(
                """
                UPDATE torrents
                SET name=?, size=?, state=?, progress=?, ratio=?,
                    completed_date=COALESCE(?, completed_date),
                    scheduled_removal=CASE WHEN protected=1 THEN scheduled_removal ELSE COALESCE(?, scheduled_removal) END,
                    last_seen=?
                WHERE torrent_hash=? AND removed=0
            """,
                (name, size, state, progress, ratio, completed_date, scheduled_removal, now, torrent_hash),
            )
        else:
            conn.execute(
                """
                INSERT INTO torrents
                    (torrent_hash, name, size, state, progress, ratio,
                     completed_date, scheduled_removal, protected, removed, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
            """,
                (torrent_hash, name, size, state, progress, ratio, completed_date, scheduled_removal, now, now),
            )
        conn.commit()
        conn.close()

    def get_all_torrents(self):
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM torrents ORDER BY removed ASC, scheduled_removal ASC"
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_active_torrents(self):
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM torrents WHERE removed=0 ORDER BY scheduled_removal ASC"
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_torrents_to_remove(self):
        conn = self._get_conn()
        now = datetime.utcnow().isoformat()
        rows = conn.execute(
            """
            SELECT * FROM torrents
            WHERE removed=0 AND protected=0
                  AND scheduled_removal IS NOT NULL
                  AND scheduled_removal <= ?
        """,
            (now,),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def mark_removed(self, torrent_hash):
        conn = self._get_conn()
        now = datetime.utcnow().isoformat()
        conn.execute(
            "UPDATE torrents SET removed=1, removed_date=?, state='Removed' WHERE torrent_hash=?",
            (now, torrent_hash),
        )
        conn.commit()
        conn.close()

    def set_protected(self, torrent_hash, protected):
        conn = self._get_conn()
        conn.execute(
            "UPDATE torrents SET protected=? WHERE torrent_hash=?",
            (1 if protected else 0, torrent_hash),
        )
        conn.commit()
        conn.close()

    def mark_missing_torrents(self, active_hashes):
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT torrent_hash FROM torrents WHERE removed=0"
        ).fetchall()
        for row in rows:
            if row["torrent_hash"] not in active_hashes:
                conn.execute(
                    "UPDATE torrents SET state='Missing' WHERE torrent_hash=?",
                    (row["torrent_hash"],),
                )
        conn.commit()
        conn.close()

    def get_seed_time_days(self):
        settings = self.get_settings()
        return float(settings.get("seed_time_days", "14"))

    def recalculate_removal_dates(self, seed_time_days):
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT torrent_hash, completed_date FROM torrents WHERE removed=0 AND protected=0 AND completed_date IS NOT NULL"
        ).fetchall()
        for row in rows:
            completed = datetime.fromisoformat(row["completed_date"])
            new_removal = (completed + timedelta(days=seed_time_days)).isoformat()
            conn.execute(
                "UPDATE torrents SET scheduled_removal=? WHERE torrent_hash=?",
                (new_removal, row["torrent_hash"]),
            )
        conn.commit()
        conn.close()
