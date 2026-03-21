import logging

import requests

logger = logging.getLogger(__name__)

TORRENT_FIELDS = [
    "name",
    "state",
    "progress",
    "total_size",
    "ratio",
    "time_added",
    "seeding_time",
    "is_finished",
    "completed_time",
]


class DelugeClient:
    def __init__(self, host, port, password):
        self.url = f"http://{host}:{port}/json"
        self.password = password
        self.session = requests.Session()
        self.connected = False
        self._request_id = 0

    def _call(self, method, params=None):
        self._request_id += 1
        payload = {
            "method": method,
            "params": params or [],
            "id": self._request_id,
        }
        resp = self.session.post(self.url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            raise Exception(data["error"]["message"])
        return data.get("result")

    def connect(self):
        try:
            result = self._call("auth.login", [self.password])
            if not result:
                logger.error("Deluge auth failed - check password")
                self.connected = False
                return False

            # Ensure the web UI is connected to a daemon
            web_connected = self._call("web.connected")
            if not web_connected:
                # Try to connect to the first available daemon
                hosts = self._call("web.get_hosts")
                if hosts:
                    self._call("web.connect", [hosts[0][0]])
                    web_connected = self._call("web.connected")

            if not web_connected:
                logger.error("Deluge web UI is not connected to a daemon")
                self.connected = False
                return False

            self.connected = True
            logger.info("Connected to Deluge Web API at %s", self.url)
            return True
        except Exception as e:
            logger.error("Failed to connect to Deluge: %s", e)
            self.connected = False
            return False

    def _ensure_connected(self):
        if not self.connected:
            return self.connect()
        # Verify session is still valid
        try:
            result = self._call("auth.check_session")
            if not result:
                return self.connect()
            return True
        except Exception:
            return self.connect()

    def get_torrents(self):
        if not self._ensure_connected():
            return None
        try:
            torrents = self._call(
                "core.get_torrents_status", [{}, TORRENT_FIELDS]
            )
            return torrents
        except Exception as e:
            logger.error("Failed to get torrents: %s", e)
            self.connected = False
            return None

    def remove_torrent(self, torrent_hash, remove_data=True):
        if not self._ensure_connected():
            return False
        try:
            self._call("core.remove_torrent", [torrent_hash, remove_data])
            logger.info(
                "Removed torrent %s (data deleted: %s)", torrent_hash, remove_data
            )
            return True
        except Exception as e:
            logger.error("Failed to remove torrent %s: %s", torrent_hash, e)
            return False
