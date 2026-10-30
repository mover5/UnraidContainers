import io
import logging
import os
import tarfile
import threading
import time

import maxminddb
import requests

logger = logging.getLogger(__name__)

EDITIONS = ("GeoLite2-City", "GeoLite2-ASN")
# MaxMind publishes GeoLite2 twice a week; checking every 3 days keeps us current.
MAX_AGE_SECONDS = 3 * 86400
DOWNLOAD_URL = "https://download.maxmind.com/geoip/databases/{edition}/download?suffix=tar.gz"


class GeoIP:
    def __init__(self, config):
        self.config = config
        self.dir = os.path.join(config.config_path, "geoip")
        os.makedirs(self.dir, exist_ok=True)
        self._readers = {}
        self._lock = threading.Lock()

    def _path(self, edition):
        return os.path.join(self.dir, f"{edition}.mmdb")

    def update(self, force=False):
        """Download any database that is missing or stale. Returns a short status string."""
        updated = []
        for edition in EDITIONS:
            path = self._path(edition)
            if not force and os.path.exists(path) and time.time() - os.path.getmtime(path) < MAX_AGE_SECONDS:
                continue
            resp = requests.get(
                DOWNLOAD_URL.format(edition=edition),
                auth=(self.config.maxmind_account_id, self.config.maxmind_license_key),
                timeout=120,
            )
            resp.raise_for_status()
            with tarfile.open(fileobj=io.BytesIO(resp.content), mode="r:gz") as tar:
                member = next(m for m in tar.getmembers() if m.name.endswith(".mmdb"))
                data = tar.extractfile(member).read()
            tmp = path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(data)
            # Replacing in place also deletes the old copy, as the GeoLite2 licence requires.
            os.replace(tmp, path)
            updated.append(edition)
        with self._lock:
            for edition in updated:
                old = self._readers.pop(edition, None)
                if old:
                    old.close()
        ages = []
        for edition in EDITIONS:
            if os.path.exists(self._path(edition)):
                ages.append(f"{edition} {time.strftime('%Y-%m-%d', time.gmtime(os.path.getmtime(self._path(edition))))}")
        return ("updated " + ", ".join(updated) + "; " if updated else "") + "; ".join(ages)

    def _reader(self, edition):
        with self._lock:
            if edition not in self._readers:
                path = self._path(edition)
                if not os.path.exists(path):
                    return None
                self._readers[edition] = maxminddb.open_database(path)
            return self._readers[edition]

    def lookup(self, ip):
        """Return dict(asn, org, city, region, country) — any value may be None."""
        out = {"asn": None, "org": None, "city": None, "region": None, "country": None}
        asn = self._reader("GeoLite2-ASN")
        if asn:
            rec = asn.get(ip) or {}
            out["asn"] = rec.get("autonomous_system_number")
            out["org"] = rec.get("autonomous_system_organization")
        city = self._reader("GeoLite2-City")
        if city:
            rec = city.get(ip) or {}
            out["city"] = (rec.get("city") or {}).get("names", {}).get("en")
            subdivisions = rec.get("subdivisions") or []
            if subdivisions:
                out["region"] = subdivisions[0].get("iso_code") or subdivisions[0].get("names", {}).get("en")
            out["country"] = (rec.get("country") or rec.get("registered_country") or {}).get("iso_code")
        return out
