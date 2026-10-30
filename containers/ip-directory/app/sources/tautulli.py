import logging

import requests

logger = logging.getLogger(__name__)

PAGE = 500


def sync(config, db):
    """Pull Plex playback history newer than the last sync; remember the latest user/player per IP."""
    since = int(db.get_kv("tautulli_max_date", "0"))
    newest = since
    latest_by_ip = {}
    start = 0
    while True:
        resp = requests.get(
            f"{config.tautulli_url}/api/v2",
            params={
                "apikey": config.tautulli_api_key,
                "cmd": "get_history",
                "start": start,
                "length": PAGE,
                "order_column": "date",
                "order_dir": "desc",
            },
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()["response"]
        if body.get("result") != "success":
            raise RuntimeError(body.get("message") or "Tautulli returned an error")
        rows = body["data"]["data"]
        reached_old = False
        for row in rows:
            date = int(row.get("date") or 0)
            if date <= since:
                reached_old = True
                break
            newest = max(newest, date)
            ip = (row.get("ip_address") or "").strip()
            if ip and ip not in latest_by_ip:  # rows are newest first
                latest_by_ip[ip] = {
                    "user": row.get("user") or "",
                    "friendly_name": row.get("friendly_name") or row.get("user") or "",
                    "player": row.get("player") or "",
                    "platform": row.get("platform") or "",
                    "date": date,
                }
        if reached_old or len(rows) < PAGE:
            break
        start += PAGE

    with db.tx() as conn:
        for ip, r in latest_by_ip.items():
            conn.execute(
                """
                INSERT INTO tautulli (ip, user, friendly_name, player, platform, last_seen_epoch)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(ip) DO UPDATE SET
                    user = excluded.user, friendly_name = excluded.friendly_name,
                    player = excluded.player, platform = excluded.platform,
                    last_seen_epoch = excluded.last_seen_epoch
                WHERE excluded.last_seen_epoch >= tautulli.last_seen_epoch
                """,
                (ip, r["user"], r["friendly_name"], r["player"], r["platform"], r["date"]),
            )
        conn.execute("INSERT OR REPLACE INTO kv (key, value) VALUES ('tautulli_max_date', ?)", (str(newest),))

    total = db.query_one("SELECT COUNT(*) AS n FROM tautulli")["n"]
    return f"{len(latest_by_ip)} IPs updated, {total} known"
