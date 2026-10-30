import ipaddress
import logging
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from app import resolver
from app.db import utcnow
from app.sources import adguard, rdns, tautulli

logger = logging.getLogger(__name__)

RDNS_BATCH = 400
RDNS_MAX_AGE_DAYS = 30
MAC_WINDOW_DAYS = 7
# Re-assert unchanged labels once a day for IPs still being seen, so Grafana's 31-day lookback finds them.
LABEL_REWRITE_HOURS = 24
KEEP_DAILY_DAYS = 90
KEEP_MAC_DAYS = 30


def _parse(ts):
    return datetime.fromisoformat(ts) if ts else None


class Refresher:
    def __init__(self, config, db, influx, geoip, vendors):
        self.config = config
        self.db = db
        self.influx = influx
        self.geoip = geoip
        self.vendors = vendors
        self.lan_networks = [ipaddress.ip_network(c, strict=False) for c in config.lan_cidrs]
        self.lock = threading.Lock()
        self.scheduler = BackgroundScheduler(daemon=True)
        self.running = False

    def start(self):
        self.scheduler.add_job(
            self.refresh, "interval", minutes=self.config.refresh_minutes, id="refresh",
            next_run_time=datetime.now(timezone.utc) + timedelta(seconds=5), max_instances=1, coalesce=True,
        )
        self.scheduler.start()

    def trigger(self):
        self.scheduler.add_job(self.refresh, id="refresh-now", replace_existing=True)

    # -- full refresh ---------------------------------------------------------------------------

    def refresh(self):
        if not self.lock.acquire(blocking=False):
            logger.info("Refresh already running; skipping")
            return
        self.running = True
        try:
            self._step("maxmind", self.config.maxmind_configured, self.geoip.update)
            self._step("vendors", True, self.vendors.update)
            self._step("influxdb", self.config.influx_configured, self._scan)
            self._step("tautulli", self.config.tautulli_configured, lambda: tautulli.sync(self.config, self.db))
            self._step("adguard", self.config.adguard_configured, lambda: adguard.sync(self.config, self.db))
            self._step("rdns", True, self._reverse_dns)
            self._relabel_locked()
            self._prune()
            self.db.set_kv("last_refresh", utcnow())
        except Exception:
            logger.exception("Refresh failed")
        finally:
            self.running = False
            self.lock.release()

    def _step(self, source, configured, fn):
        if not configured:
            self.db.record_status(source, False, detail="not configured", error="not configured")
            return
        try:
            detail = fn()
            self.db.record_status(source, True, detail=detail or "")
            logger.info("%s: %s", source, detail)
        except Exception as e:  # one broken source must not stop the others
            logger.exception("%s failed", source)
            self.db.record_status(source, False, error=f"{type(e).__name__}: {e}")

    # -- sFlow scan -----------------------------------------------------------------------------

    def _scan(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        stop = now - timedelta(minutes=1)  # leave room for samples still being written
        start = _parse(self.db.get_kv("scan_until")) or (stop - timedelta(days=self.config.initial_scan_days))
        if stop <= start:
            return "nothing new"
        samples = 0
        # Scan in day-sized chunks so the first (7-day) run stays light on InfluxDB.
        chunk_start = start
        while chunk_start < stop:
            chunk_stop = min(chunk_start + timedelta(days=1), stop)
            samples += self._scan_window(chunk_start, chunk_stop)
            chunk_start = chunk_stop
        return f"{samples} samples since {start.isoformat()}"

    def _scan_window(self, start, stop):
        daily = defaultdict(lambda: [0.0, 0.0, 0])  # (ip, day) -> [sent, recv, samples]
        mac_counts = defaultdict(int)                # (ip, mac, day) -> samples
        seen = {}                                    # ip -> (first, last)
        mac_seen = {}
        n = 0
        for ts, src, dst, mac, nbytes in self.influx.scan(start, stop):
            n += 1
            day = ts.date().isoformat()
            stamp = ts.replace(microsecond=0).isoformat()
            daily[(src, day)][0] += nbytes
            daily[(src, day)][2] += 1
            daily[(dst, day)][1] += nbytes
            daily[(dst, day)][2] += 1
            for ip in (src, dst):
                first, last = seen.get(ip, (stamp, stamp))
                seen[ip] = (min(first, stamp), max(last, stamp))
            mac = (mac or "").lower()
            if mac and self._is_lan(src):
                mac_counts[(src, mac, day)] += 1
                first, last = mac_seen.get(mac, (stamp, stamp))
                mac_seen[mac] = (min(first, stamp), max(last, stamp))

        with self.db.tx() as conn:
            conn.executemany(
                """
                INSERT INTO ip_daily (ip, day, bytes_sent, bytes_recv, samples) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(ip, day) DO UPDATE SET
                    bytes_sent = bytes_sent + excluded.bytes_sent,
                    bytes_recv = bytes_recv + excluded.bytes_recv,
                    samples = samples + excluded.samples
                """,
                [(ip, day, v[0], v[1], v[2]) for (ip, day), v in daily.items()],
            )
            conn.executemany(
                """
                INSERT INTO ip_mac_daily (ip, mac, day, samples) VALUES (?, ?, ?, ?)
                ON CONFLICT(ip, mac, day) DO UPDATE SET samples = samples + excluded.samples
                """,
                [(ip, mac, day, c) for (ip, mac, day), c in mac_counts.items()],
            )
            conn.executemany(
                """
                INSERT INTO ips (ip, first_seen, last_seen, is_lan) VALUES (?, ?, ?, ?)
                ON CONFLICT(ip) DO UPDATE SET
                    first_seen = MIN(first_seen, excluded.first_seen),
                    last_seen = MAX(last_seen, excluded.last_seen)
                """,
                [(ip, f, l, int(self._is_lan(ip))) for ip, (f, l) in seen.items() if self._valid(ip)],
            )
            conn.executemany(
                """
                INSERT INTO macs (mac, first_seen, last_seen) VALUES (?, ?, ?)
                ON CONFLICT(mac) DO UPDATE SET
                    first_seen = MIN(first_seen, excluded.first_seen),
                    last_seen = MAX(last_seen, excluded.last_seen)
                """,
                [(mac, f, l) for mac, (f, l) in mac_seen.items()],
            )
            # Same transaction as the counts, so a crash can never count a window twice.
            conn.execute("INSERT OR REPLACE INTO kv (key, value) VALUES ('scan_until', ?)", (stop.isoformat(),))
        return n

    def _valid(self, ip):
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    def _is_lan(self, ip):
        try:
            return resolver.is_lan(ip, self.lan_networks)
        except ValueError:
            return False

    # -- reverse DNS ----------------------------------------------------------------------------

    def _reverse_dns(self):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=RDNS_MAX_AGE_DAYS)).isoformat()
        recent = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        rows = self.db.query(
            """
            SELECT ip FROM ips
            WHERE is_lan = 0 AND last_seen >= ? AND (rdns_checked_at IS NULL OR rdns_checked_at < ?)
            ORDER BY last_seen DESC LIMIT ?
            """,
            (recent, cutoff, RDNS_BATCH),
        )
        ips = [r["ip"] for r in rows if not ipaddress.ip_address(r["ip"]).is_multicast]
        if not ips:
            return "up to date"
        names = rdns.lookup_many(ips)
        now = utcnow()
        with self.db.tx() as conn:
            conn.executemany(
                "UPDATE ips SET rdns = ?, rdns_checked_at = ? WHERE ip = ?",
                [(name, now, ip) for ip, name in names.items()],
            )
        found = sum(1 for v in names.values() if v)
        return f"{len(ips)} looked up, {found} with names"

    # -- naming ---------------------------------------------------------------------------------

    def relabel(self):
        """Re-resolve every IP and push changed labels to InfluxDB."""
        with self.lock:
            return self._relabel_locked()

    def apply_edits(self):
        """After a manual edit: update names in SQLite now, push to InfluxDB in the background."""
        self._resolve_all()
        threading.Thread(target=self.relabel, daemon=True).start()

    def _context(self):
        db = self.db
        ranges = []
        for r in db.query("SELECT * FROM range_rules ORDER BY id"):
            try:
                ranges.append((ipaddress.ip_network(r["cidr"], strict=False), r))
            except ValueError:
                logger.warning("Skipping bad range rule %s", r["cidr"])
        # More specific ranges win.
        ranges.sort(key=lambda x: x[0].prefixlen, reverse=True)
        return resolver.Context(
            lan_networks=self.lan_networks,
            manual_ip={r["ip"]: r for r in db.query("SELECT * FROM manual_ip")},
            manual_mac={r["mac"]: r for r in db.query("SELECT * FROM manual_mac")},
            range_rules=ranges,
            tautulli={r["ip"]: r for r in db.query("SELECT * FROM tautulli")},
            adguard={r["key"]: r["name"] for r in db.query("SELECT key, name FROM adguard")},
            owner_rules=[(r["pattern"], r["replacement"]) for r in db.query("SELECT * FROM owner_rules ORDER BY position, id")],
            geo=self.geoip.lookup if self.config.maxmind_configured else None,
            vendor=self.vendors.lookup,
        )

    def dominant_macs(self):
        since = (datetime.now(timezone.utc) - timedelta(days=MAC_WINDOW_DAYS)).date().isoformat()
        rows = self.db.query(
            """
            SELECT ip, mac FROM (
                SELECT ip, mac, SUM(samples) AS n,
                       ROW_NUMBER() OVER (PARTITION BY ip ORDER BY SUM(samples) DESC) AS rk
                FROM ip_mac_daily WHERE day >= ? GROUP BY ip, mac
            ) WHERE rk = 1
            """,
            (since,),
        )
        return {r["ip"]: r["mac"] for r in rows}

    def _resolve_all(self):
        """Resolve every IP into the ips table. Returns (ip count, labels that need writing)."""
        ctx = self._context()
        macs = self.dominant_macs()
        rows = self.db.query("SELECT ip, mac, is_lan, last_seen, label_written_at, label_written_hash FROM ips")
        rewrite_before = datetime.now(timezone.utc) - timedelta(hours=LABEL_REWRITE_HOURS)
        updates, to_write = [], []
        for row in rows:
            ip = row["ip"]
            mac = macs.get(ip) or row["mac"]
            label, _ = resolver.resolve(ip, mac, ctx)
            label["mac"] = mac if row["is_lan"] else None  # lets Grafana's Devices-by-MAC table join too
            h = resolver.label_hash(label)
            written = _parse(row["label_written_at"])
            stale = written is None or (written < rewrite_before and _parse(row["last_seen"]) > written)
            if h != row["label_written_hash"] or stale:
                to_write.append(dict(label, ip=ip, hash=h))
            updates.append((mac, label["vendor"], label["name"], label["kind"], label["source"], label["owner"],
                            label["asn"], label["location"], label["country"], ip))

        with self.db.tx() as conn:
            conn.executemany(
                """
                UPDATE ips SET mac = ?, vendor = ?, name = ?, kind = ?, source = ?, owner = ?,
                               asn = ?, location = ?, country = ?
                WHERE ip = ?
                """,
                updates,
            )
            conn.executemany("UPDATE macs SET last_ip = ? WHERE mac = ?", [(ip, mac) for ip, mac in macs.items()])
        return len(rows), to_write

    def _relabel_locked(self):
        count, to_write = self._resolve_all()
        if not to_write or not self.config.influx_configured:
            return 0
        try:
            written = self.influx.write_labels(to_write)
            stamp = utcnow()
            with self.db.tx() as conn:
                conn.executemany(
                    "UPDATE ips SET label_written_at = ?, label_written_hash = ? WHERE ip = ?",
                    [(stamp, l["hash"], l["ip"]) for l in to_write],
                )
            self.db.record_status("labels", True, detail=f"{written} labels written, {count} IPs named")
            return written
        except Exception as e:
            logger.exception("Writing labels failed")
            self.db.record_status("labels", False, error=f"{type(e).__name__}: {e}")
            return 0

    def _prune(self):
        today = datetime.now(timezone.utc).date()
        with self.db.tx() as conn:
            conn.execute("DELETE FROM ip_daily WHERE day < ?", ((today - timedelta(days=KEEP_DAILY_DAYS)).isoformat(),))
            conn.execute("DELETE FROM ip_mac_daily WHERE day < ?", ((today - timedelta(days=KEEP_MAC_DAYS)).isoformat(),))
