import ipaddress
import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for
from waitress import serve

from app import resolver
from app.config import Config
from app.db import Database, utcnow
from app.influx import Influx
from app.refresher import Refresher
from app.sources.geoip import GeoIP
from app.sources.vendor import Vendors

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

config = Config()
db = Database(config.config_path)
influx = Influx(config)
geoip = GeoIP(config)
vendors = Vendors(config)
refresher = Refresher(config, db, influx, geoip, vendors)

app = Flask(__name__)

KIND_SUGGESTIONS = ["device", "phone", "computer", "tv", "server", "router", "iot", "camera",
                    "person", "plex", "service", "vpn", "wan"]
SOURCES = [
    ("influxdb", "InfluxDB (sFlow)", "Which IPs are active, traffic, IP→MAC"),
    ("labels", "Label writes", "Names pushed to InfluxDB for Grafana"),
    ("tautulli", "Tautulli", "Plex users by IP"),
    ("adguard", "AdGuard Home", "LAN client names"),
    ("maxmind", "MaxMind GeoLite2", "Owner + location for public IPs"),
    ("vendors", "MAC vendors", "Wireshark manufacturer list"),
    ("rdns", "Reverse DNS", "Hostname hints for public IPs"),
]
_MAC = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")


# -- helpers ------------------------------------------------------------------------------------

@app.template_filter("bytes")
def fmt_bytes(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1000


@app.template_filter("ago")
def fmt_ago(ts):
    if not ts:
        return "never"
    delta = datetime.now(timezone.utc) - datetime.fromisoformat(ts)
    secs = int(delta.total_seconds())
    if secs < 90:
        return "just now"
    if secs < 5400:
        return f"{secs // 60} min ago"
    if secs < 129600:
        return f"{secs // 3600} h ago"
    return f"{secs // 86400} d ago"


@app.context_processor
def inject():
    inbox = db.query_one(
        f"""
        SELECT COUNT(*) AS n FROM ips i JOIN ({_traffic_sql()}) t ON t.ip = i.ip
        WHERE i.reviewed = 0 AND COALESCE(i.kind, '') != 'multicast'
          AND i.source IN ({",".join("?" * len(resolver.AUTO_SOURCES))})
        """,
        (_since(7), *resolver.AUTO_SOURCES),
    )["n"]
    return {"inbox_count": inbox, "refresh_running": refresher.running, "kinds": KIND_SUGGESTIONS}


def _since(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()


def _traffic_sql():
    return """
        SELECT ip, SUM(bytes_sent) AS sent7, SUM(bytes_recv) AS recv7,
               SUM(bytes_sent + bytes_recv) AS bytes7
        FROM ip_daily WHERE day >= ? GROUP BY ip
    """


def _valid_ip(ip):
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        abort(404)


def _valid_mac(mac):
    mac = mac.lower().replace("-", ":")
    if not _MAC.match(mac):
        abort(404)
    return mac


def _back(default):
    nxt = request.form.get("next") or ""
    parts = urlsplit(nxt)
    local = (
        nxt.startswith("/") and not parts.scheme and not parts.netloc
        and "\\" not in nxt and not any(ord(ch) < 32 for ch in nxt) and not nxt.startswith("//")
    )
    return redirect(nxt if local else default)


def _host_allowed(host):
    """IP literals and localhost can't be DNS-rebound; any hostname must be listed in ALLOWED_HOSTS."""
    name = (urlsplit(f"//{host}").hostname or "").lower()
    if name == "localhost" or name in config.allowed_hosts:
        return True
    try:
        ipaddress.ip_address(name)
        return True
    except ValueError:
        return False


@app.before_request
def guard_requests():
    # No login, so: refuse DNS-rebinding hosts, and refuse edits submitted by other web pages.
    if not _host_allowed(request.host):
        abort(403, "Host not allowed - add it to ALLOWED_HOSTS")
    if request.method == "POST":
        source = request.headers.get("Origin") or request.headers.get("Referer")
        if not source or urlsplit(source).netloc != request.host:
            abort(403)
    return None


# -- pages --------------------------------------------------------------------------------------

@app.route("/")
def directory():
    q = request.args.get("q", "").strip()
    kind = request.args.get("kind", "")
    source = request.args.get("source", "")
    scope = request.args.get("scope", "")
    sort = request.args.get("sort", "traffic")
    page = max(int(request.args.get("page", "1") or 1), 1)
    per_page = 100

    where, params = [], [_since(7)]
    if q:
        like = f"%{q}%"
        where.append("(i.ip LIKE ? OR i.name LIKE ? OR i.owner LIKE ? OR i.mac LIKE ? OR i.location LIKE ? OR i.rdns LIKE ?)")
        params += [like] * 6
    if kind:
        where.append("i.kind = ?")
        params.append(kind)
    if source:
        where.append("i.source = ?")
        params.append(source)
    if scope == "lan":
        where.append("i.is_lan = 1")
    elif scope == "internet":
        where.append("i.is_lan = 0")
    order = {
        "traffic": "COALESCE(t.bytes7, 0) DESC",
        "recent": "i.last_seen DESC",
        "name": "i.name COLLATE NOCASE",
        "ip": "i.is_lan DESC, i.ip",
    }.get(sort, "COALESCE(t.bytes7, 0) DESC")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    total = db.query_one(
        f"SELECT COUNT(*) AS n FROM ips i LEFT JOIN ({_traffic_sql()}) t ON t.ip = i.ip {where_sql}", params
    )["n"]
    rows = db.query(
        f"""
        SELECT i.*, t.sent7, t.recv7, t.bytes7 FROM ips i
        LEFT JOIN ({_traffic_sql()}) t ON t.ip = i.ip
        {where_sql} ORDER BY {order} LIMIT ? OFFSET ?
        """,
        params + [per_page, (page - 1) * per_page],
    )
    facets = {
        "kinds": [r["kind"] for r in db.query("SELECT DISTINCT kind FROM ips WHERE kind IS NOT NULL ORDER BY kind")],
        "sources": [r["source"] for r in db.query("SELECT DISTINCT source FROM ips WHERE source IS NOT NULL ORDER BY source")],
    }
    return render_template(
        "directory.html", rows=rows, total=total, page=page, pages=max((total + per_page - 1) // per_page, 1),
        q=q, kind=kind, source=source, scope=scope, sort=sort, facets=facets,
    )


@app.route("/inbox")
def inbox():
    placeholders = ",".join("?" * len(resolver.AUTO_SOURCES))
    sql = f"""
        SELECT i.*, t.sent7, t.recv7, t.bytes7 FROM ips i
        JOIN ({_traffic_sql()}) t ON t.ip = i.ip
        WHERE i.reviewed = 0 AND COALESCE(i.kind, '') != 'multicast'
          AND i.source IN ({placeholders}) AND i.is_lan = ?
        ORDER BY t.bytes7 DESC LIMIT 50
    """
    lan = db.query(sql, (_since(7), *resolver.AUTO_SOURCES, 1))
    internet = db.query(sql, (_since(7), *resolver.AUTO_SOURCES, 0))
    return render_template("inbox.html", lan=lan, internet=internet)


@app.route("/ip/<ip>")
def ip_detail(ip):
    ip = _valid_ip(ip)
    row = db.query_one(
        f"SELECT i.*, t.sent7, t.recv7, t.bytes7 FROM ips i LEFT JOIN ({_traffic_sql()}) t ON t.ip = i.ip WHERE i.ip = ?",
        (_since(7), ip),
    )
    ctx = refresher._context()
    mac = (row or {}).get("mac")
    label, opinions = resolver.resolve(ip, mac, ctx)
    geo = geoip.lookup(ip) if config.maxmind_configured and not resolver.is_lan(ip, refresher.lan_networks) else {}
    return render_template(
        "ip.html", ip=ip, row=row, label=label, opinions=opinions, geo=geo,
        manual_ip=db.query_one("SELECT * FROM manual_ip WHERE ip = ?", (ip,)),
        manual_mac=db.query_one("SELECT * FROM manual_mac WHERE mac = ?", (mac,)) if mac else None,
        tautulli=db.query_one("SELECT * FROM tautulli WHERE ip = ?", (ip,)),
        other_ips=db.query("SELECT ip FROM ips WHERE mac = ? AND ip != ?", (mac, ip)) if mac else [],
        live=config.influx_configured,
    )


@app.route("/devices")
def devices():
    rows = db.query(
        """
        SELECT m.mac, m.first_seen, m.last_seen, m.last_ip, mm.name AS manual_name, mm.kind AS manual_kind,
               i.name AS current_name, i.source AS current_source, i.vendor
        FROM macs m
        LEFT JOIN manual_mac mm ON mm.mac = m.mac
        LEFT JOIN ips i ON i.ip = m.last_ip
        UNION ALL
        SELECT mm.mac, NULL, NULL, NULL, mm.name, mm.kind, NULL, NULL, NULL
        FROM manual_mac mm WHERE mm.mac NOT IN (SELECT mac FROM macs)
        ORDER BY 3 DESC
        """
    )
    for r in rows:
        r["randomized"] = resolver.is_randomized_mac(r["mac"])
        if not r["vendor"]:
            r["vendor"] = vendors.lookup(r["mac"])
    return render_template("devices.html", rows=rows)


@app.route("/rules")
def rules():
    return render_template(
        "rules.html",
        owner_rules=db.query("SELECT * FROM owner_rules ORDER BY position, id"),
        range_rules=db.query("SELECT * FROM range_rules ORDER BY id"),
        top_owners=db.query(
            f"""
            SELECT i.owner, COUNT(*) AS ips, SUM(COALESCE(t.bytes7, 0)) AS bytes7 FROM ips i
            LEFT JOIN ({_traffic_sql()}) t ON t.ip = i.ip
            WHERE i.is_lan = 0 AND i.owner IS NOT NULL GROUP BY i.owner ORDER BY bytes7 DESC LIMIT 25
            """,
            (_since(7),),
        ),
    )


@app.route("/sources")
def sources():
    status = {r["source"]: r for r in db.query("SELECT * FROM source_status")}
    stats = {
        "ips": db.query_one("SELECT COUNT(*) AS n FROM ips")["n"],
        "ips_7d": db.query_one("SELECT COUNT(DISTINCT ip) AS n FROM ip_daily WHERE day >= ?", (_since(7),))["n"],
        "macs": db.query_one("SELECT COUNT(*) AS n FROM macs")["n"],
        "manual_ip": db.query_one("SELECT COUNT(*) AS n FROM manual_ip")["n"],
        "manual_mac": db.query_one("SELECT COUNT(*) AS n FROM manual_mac")["n"],
        "plex": db.query_one("SELECT COUNT(*) AS n FROM tautulli")["n"],
        "bytes_7d": db.query_one("SELECT SUM(bytes_sent) AS n FROM ip_daily WHERE day >= ?", (_since(7),))["n"] or 0,
    }
    by_source = db.query("SELECT source, COUNT(*) AS n FROM ips GROUP BY source ORDER BY n DESC")
    by_kind = db.query("SELECT kind, COUNT(*) AS n FROM ips GROUP BY kind ORDER BY n DESC")
    return render_template(
        "sources.html", sources=SOURCES, status=status, stats=stats, by_source=by_source, by_kind=by_kind,
        last_refresh=db.get_kv("last_refresh"), scan_until=db.get_kv("scan_until"), config=config,
    )


# -- edits --------------------------------------------------------------------------------------

@app.post("/ip/<ip>/label")
def set_ip_label(ip):
    ip = _valid_ip(ip)
    name = request.form.get("name", "").strip()
    if name:
        db.execute(
            """
            INSERT INTO manual_ip (ip, name, kind, notes, updated_at) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(ip) DO UPDATE SET name = excluded.name, kind = excluded.kind,
                notes = excluded.notes, updated_at = excluded.updated_at
            """,
            (ip, name, request.form.get("kind", "").strip(), request.form.get("notes", "").strip(), utcnow()),
        )
        refresher.apply_edits()
    return _back(url_for("ip_detail", ip=ip))


@app.post("/ip/<ip>/label/delete")
def delete_ip_label(ip):
    db.execute("DELETE FROM manual_ip WHERE ip = ?", (_valid_ip(ip),))
    refresher.apply_edits()
    return _back(url_for("ip_detail", ip=ip))


@app.post("/ip/<ip>/review")
def review_ip(ip):
    db.execute("UPDATE ips SET reviewed = ? WHERE ip = ?", (0 if request.form.get("undo") else 1, _valid_ip(ip)))
    return _back(url_for("inbox"))


@app.post("/mac/<mac>/label")
def set_mac_label(mac):
    mac = _valid_mac(mac)
    name = request.form.get("name", "").strip()
    if name:
        db.execute(
            """
            INSERT INTO manual_mac (mac, name, kind, notes, updated_at) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(mac) DO UPDATE SET name = excluded.name, kind = excluded.kind,
                notes = excluded.notes, updated_at = excluded.updated_at
            """,
            (mac, name, request.form.get("kind", "").strip(), request.form.get("notes", "").strip(), utcnow()),
        )
        refresher.apply_edits()
    return _back(url_for("devices"))


@app.post("/mac/<mac>/label/delete")
def delete_mac_label(mac):
    db.execute("DELETE FROM manual_mac WHERE mac = ?", (_valid_mac(mac),))
    refresher.apply_edits()
    return _back(url_for("devices"))


@app.post("/rules/owner")
def add_owner_rule():
    pattern = request.form.get("pattern", "").strip()
    replacement = request.form.get("replacement", "").strip()
    if pattern and replacement:
        pos = db.query_one("SELECT COALESCE(MAX(position), -1) + 1 AS p FROM owner_rules")["p"]
        db.execute("INSERT INTO owner_rules (pattern, replacement, position) VALUES (?, ?, ?)", (pattern, replacement, pos))
        refresher.apply_edits()
    return redirect(url_for("rules"))


@app.post("/rules/owner/<int:rule_id>/move")
def move_owner_rule(rule_id):
    rules_ = db.query("SELECT id FROM owner_rules ORDER BY position, id")
    ids = [r["id"] for r in rules_]
    if rule_id in ids:
        i = ids.index(rule_id)
        j = i - 1 if request.form.get("dir") == "up" else i + 1
        if 0 <= j < len(ids):
            ids[i], ids[j] = ids[j], ids[i]
            with db.tx() as conn:
                conn.executemany("UPDATE owner_rules SET position = ? WHERE id = ?", [(p, rid) for p, rid in enumerate(ids)])
            refresher.apply_edits()
    return redirect(url_for("rules"))


@app.post("/rules/owner/<int:rule_id>/delete")
def delete_owner_rule(rule_id):
    db.execute("DELETE FROM owner_rules WHERE id = ?", (rule_id,))
    refresher.apply_edits()
    return redirect(url_for("rules"))


@app.post("/rules/range")
def add_range_rule():
    cidr = request.form.get("cidr", "").strip()
    name = request.form.get("name", "").strip()
    try:
        cidr = str(ipaddress.ip_network(cidr, strict=False))
    except ValueError:
        return redirect(url_for("rules", error=f"Not a valid IP range: {cidr}"))
    if name:
        db.execute(
            "INSERT INTO range_rules (cidr, name, kind, notes) VALUES (?, ?, ?, ?)",
            (cidr, name, request.form.get("kind", "").strip(), request.form.get("notes", "").strip()),
        )
        refresher.apply_edits()
    return redirect(url_for("rules"))


@app.post("/rules/range/<int:rule_id>/delete")
def delete_range_rule(rule_id):
    db.execute("DELETE FROM range_rules WHERE id = ?", (rule_id,))
    refresher.apply_edits()
    return redirect(url_for("rules"))


@app.post("/refresh")
def refresh_now():
    refresher.trigger()
    return redirect(url_for("sources"))


# -- JSON ---------------------------------------------------------------------------------------

@app.route("/api/labels")
def api_labels():
    return jsonify(db.query(
        "SELECT ip, name, kind, source, owner, location, mac, vendor, last_seen FROM ips ORDER BY ip"
    ))


@app.route("/api/ip/<ip>/live")
def api_live(ip):
    ip = _valid_ip(ip)
    if not config.influx_configured:
        return jsonify({"error": "InfluxDB not configured"}), 503
    hours = min(max(int(request.args.get("hours", "168")), 1), 24 * 31)
    try:
        traffic = influx.traffic(ip, hours)
        peers = influx.peers(ip, hours)
        ports = influx.ports(ip, hours)
    except Exception as e:
        logger.exception("Live query failed")
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 502
    names = {r["ip"]: r for r in db.query(
        f"SELECT ip, name, kind FROM ips WHERE ip IN ({','.join('?' * len(peers)) or 'NULL'})",
        [p["peer"] for p in peers],
    )}
    for p in peers:
        p["name"] = (names.get(p["peer"]) or {}).get("name")
    return jsonify({"hours": hours, "traffic": traffic, "peers": peers, "ports": ports})


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "last_refresh": db.get_kv("last_refresh")})


def start():
    refresher.start()
    logger.info("IP-Directory listening on :%d", config.port)
    serve(app, host="0.0.0.0", port=config.port, threads=8)
