import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)


class TorrentScheduler:
    def __init__(self, config, database, deluge_client):
        self.config = config
        self.db = database
        self.deluge = deluge_client
        self.scheduler = BackgroundScheduler(daemon=True)
        self.last_check = None
        self.last_error = None

    def start(self):
        interval = int(self.db.get_settings().get("check_interval_minutes", "5"))
        self.scheduler.add_job(
            self.check_torrents,
            "interval",
            minutes=interval,
            id="check_torrents",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info("Scheduler started with %d minute interval", interval)
        self.check_torrents()

    def reschedule(self):
        interval = int(self.db.get_settings().get("check_interval_minutes", "5"))
        self.scheduler.reschedule_job(
            "check_torrents", trigger="interval", minutes=interval
        )
        logger.info("Rescheduled checks to every %d minutes", interval)

    def check_torrents(self):
        try:
            logger.info("Checking torrents...")
            torrents = self.deluge.get_torrents()

            if torrents is None:
                self.last_error = "Could not connect to Deluge"
                logger.warning("Skipping check - Deluge unavailable")
                return

            seed_time_days = self.db.get_seed_time_days()
            active_hashes = set()

            for torrent_hash, info in torrents.items():
                active_hashes.add(torrent_hash)

                name = info.get("name", "Unknown")
                state = info.get("state", "Unknown")
                progress = info.get("progress", 0)
                size = info.get("total_size", 0)
                ratio = info.get("ratio", 0)
                seeding_time = info.get("seeding_time", 0)

                completed_date = None
                scheduled_removal = None

                if seeding_time and seeding_time > 0:
                    now = datetime.utcnow()
                    seed_limit_seconds = seed_time_days * 86400
                    remaining = max(0, seed_limit_seconds - seeding_time)
                    completed_date = (now - timedelta(seconds=seeding_time)).isoformat()
                    scheduled_removal = (now + timedelta(seconds=remaining)).isoformat()

                self.db.upsert_torrent(
                    torrent_hash=torrent_hash,
                    name=name,
                    size=size,
                    state=state,
                    progress=progress,
                    ratio=ratio,
                    completed_date=completed_date,
                    scheduled_removal=scheduled_removal,
                )

            self.db.mark_missing_torrents(active_hashes)

            to_remove = self.db.get_torrents_to_remove()
            removed_count = 0
            for torrent in to_remove:
                logger.info(
                    "Removing torrent: %s (%s)",
                    torrent["name"],
                    torrent["torrent_hash"],
                )
                if self.deluge.remove_torrent(
                    torrent["torrent_hash"], remove_data=True
                ):
                    self.db.mark_removed(torrent["torrent_hash"])
                    removed_count += 1
                else:
                    logger.error("Failed to remove torrent: %s", torrent["name"])

            self.last_check = datetime.utcnow().isoformat()
            self.last_error = None
            logger.info(
                "Check complete. %d active, %d removed this cycle.",
                len(torrents),
                removed_count,
            )

        except Exception as e:
            logger.error("Error during torrent check: %s", e)
            self.last_error = str(e)

    def remove_torrent_now(self, torrent_hash):
        if self.deluge.remove_torrent(torrent_hash, remove_data=True):
            self.db.mark_removed(torrent_hash)
            return True
        return False

    def get_status(self):
        return {
            "connected": self.deluge.connected,
            "last_check": self.last_check,
            "last_error": self.last_error,
        }
