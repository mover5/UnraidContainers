"""End-to-end: fake sFlow samples through a full refresh, then every page and edit."""
import importlib
from datetime import datetime, timedelta, timezone

import pytest

# Patterns taken from the real network: dominant MAC per IP, stray one-off samples, hairpin traffic.
SAMPLES = [
    # (src, dst, src_mac, count)
    ("192.168.1.30", "50.82.218.165", "0c:42:a1:63:8c:ec", 40),
    ("192.168.1.30", "192.168.1.84", "0c:42:a1:63:8c:ec", 30),
    ("192.168.1.30", "98.232.108.93", "0c:42:a1:63:8c:ec", 10),
    ("192.168.1.30", "192.168.1.61", "bc:d7:d4:3d:d5:c8", 1),   # stray sample, must not win
    ("98.232.108.93", "192.168.1.84", "cc:40:d0:74:bf:ef", 10),
    ("192.168.1.84", "192.168.1.30", "bc:d7:d4:3d:d5:c8", 20),
    ("192.168.1.61", "192.168.1.30", "00:17:88:46:be:38", 5),
    ("192.168.1.78", "199.232.214.172", "16:01:45:de:91:d0", 5),
    ("199.232.214.172", "192.168.1.78", "cc:40:d0:74:bf:ef", 8),
    ("192.168.1.2", "239.255.255.250", "02:42:c0:a8:01:02", 3),
    # Not devices, all seen on the real network:
    ("192.168.1.88", "192.168.1.255", "bc:fc:e7:72:79:5e", 5),      # LAN broadcast (Spotify Connect)
    ("192.168.1.30", "10.30.131.86", "0c:42:a1:63:8c:ec", 2),       # Tailscale probing a peer's LAN
    ("172.17.0.4", "172.64.151.205", "0c:42:a1:63:8c:ec", 1),       # stray un-NATed Docker packet
    ("192.168.1.82", "172.18.0.1", "b0:e4:5c:22:2d:4c", 1),         # client trying a Docker IP Plex advertised
]


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path))
    monkeypatch.setenv("INFLUX_TOKEN", "test")
    monkeypatch.setenv("TAUTULLI_URL", "")
    import app.main as main
    main = importlib.reload(main)

    now = datetime.now(timezone.utc)

    def fake_scan(start, stop):
        ts = stop - timedelta(minutes=5)
        if ts < start:
            return
        for src, dst, mac, count in SAMPLES:
            for _ in range(count):
                yield ts, src, dst, mac, 1024.0 * 1500

    written = []
    monkeypatch.setattr(main.influx, "scan", fake_scan)
    monkeypatch.setattr(main.influx, "write_labels", lambda labels: written.extend(labels) or len(labels))
    monkeypatch.setattr(main.vendors, "update", lambda force=False: "test")
    monkeypatch.setattr(main.vendors, "lookup", lambda mac: "Signify" if mac and mac.startswith("00:17:88") else None)
    monkeypatch.setattr("app.refresher.rdns.lookup_many", lambda ips: {ip: "" for ip in ips})
    # Tautulli via a fake row, as if synced.
    main.db.execute(
        "INSERT INTO tautulli (ip, user, friendly_name, player, platform, last_seen_epoch) VALUES (?,?,?,?,?,?)",
        ("50.82.218.165", "oyoj4", "oyoj4", "Roku", "Roku", int(now.timestamp())),
    )
    main.refresher.refresh()
    client = main.app.test_client()
    client.environ_base["HTTP_ORIGIN"] = "http://localhost"  # what a browser sends on a same-site form POST
    return main, written, client


def names(main):
    return {r["ip"]: r for r in main.db.query("SELECT * FROM ips")}


def test_refresh_names_everything(env):
    main, written, _ = env
    n = names(main)
    assert n["192.168.1.30"]["name"] == "Unraid"                    # seeded MAC, majority vote
    assert n["192.168.1.30"]["mac"] == "0c:42:a1:63:8c:ec"
    assert n["98.232.108.93"]["name"] == "Home WAN (R8000)"         # seeded IP
    assert n["50.82.218.165"]["name"] == "oyoj4"                    # Tautulli
    assert n["192.168.1.2"]["name"] == "AdGuard Home"               # seeded Docker MAC
    assert n["192.168.1.78"]["name"] == "Unknown phone (91:d0)"
    assert n["192.168.1.61"]["name"] == "Signify device (be:38)"
    assert n["239.255.255.250"]["kind"] == "multicast"
    assert all(r["name"] for r in n.values())
    assert {l["ip"] for l in written} == set(n)


def test_unchanged_labels_are_not_rewritten(env):
    main, written, _ = env
    written.clear()
    main.refresher.relabel()
    assert written == []


def test_pages_render(env):
    main, _, client = env
    for url in ["/", "/?q=unraid", "/?scope=lan&sort=name", "/inbox", "/devices", "/rules", "/sources",
                "/ip/192.168.1.30", "/ip/50.82.218.165", "/ip/203.0.113.1", "/api/labels", "/healthz"]:
        resp = client.get(url)
        assert resp.status_code == 200, url
    assert b"Unraid" in client.get("/?q=unraid").data
    assert client.get("/ip/not-an-ip").status_code == 404


def test_inbox_and_review(env):
    main, _, client = env
    page = client.get("/inbox").data.decode()
    assert "Unknown phone (91:d0)" in page
    assert "Home WAN" not in page  # manual names never land in the inbox
    assert "SSDP" not in page  # multicast is not something to name
    client.post("/ip/192.168.1.78/review", data={"next": "/inbox"})
    assert "Unknown phone (91:d0)" not in client.get("/inbox").data.decode()


def test_manual_mac_edit_renames_and_pushes(env):
    main, written, client = env
    written.clear()
    resp = client.post("/mac/16:01:45:de:91:d0/label", data={"name": "Mark's iPhone", "kind": "phone", "next": "/inbox"})
    assert resp.status_code == 302 and resp.headers["Location"] == "/inbox"
    assert names(main)["192.168.1.78"]["name"] == "Mark's iPhone"  # immediately, before the background write
    main.refresher.relabel()
    assert any(l["ip"] == "192.168.1.78" and l["name"] == "Mark's iPhone" for l in written)


def test_owner_and_range_rules(env):
    main, _, client = env
    client.post("/rules/range", data={"cidr": "199.232.0.0/16", "name": "Fastly CDN", "kind": "service"})
    assert names(main)["199.232.214.172"]["name"] == "Fastly CDN"
    assert client.post("/rules/range", data={"cidr": "nope", "name": "x"}).status_code == 302
    rule = main.db.query_one("SELECT id FROM range_rules")
    client.post(f"/rules/range/{rule['id']}/delete")
    assert names(main)["199.232.214.172"]["name"] == "Unknown"  # no MaxMind in tests

    client.post("/rules/owner", data={"pattern": "TEST-*", "replacement": "Test"})
    rules = main.db.query("SELECT * FROM owner_rules ORDER BY position, id")
    assert rules[-1]["pattern"] == "TEST-*"
    client.post(f"/rules/owner/{rules[-1]['id']}/move", data={"dir": "up"})
    rules = main.db.query("SELECT * FROM owner_rules ORDER BY position, id")
    assert rules[-2]["pattern"] == "TEST-*"


def test_open_redirect_blocked(env):
    _, _, client = env
    resp = client.post("/ip/192.168.1.78/review", data={"next": "//evil.example"})
    assert resp.headers["Location"] == "/inbox"


def test_lan_labels_carry_mac_for_grafana(env):
    _, written, _ = env
    by_ip = {l["ip"]: l for l in written}
    assert by_ip["192.168.1.30"]["mac"] == "0c:42:a1:63:8c:ec"
    assert by_ip["50.82.218.165"]["mac"] is None


def test_redirect_rejects_backslash_and_schemes(env):
    _, _, client = env
    for bad in ["/\\evil.example", "https://evil.example", "/\t/evil.example", "javascript:alert(1)"]:
        resp = client.post("/ip/192.168.1.78/review", data={"next": bad})
        assert resp.headers["Location"] == "/inbox", bad
    resp = client.post("/ip/192.168.1.78/review", data={"next": "/ip/192.168.1.78"})
    assert resp.headers["Location"] == "/ip/192.168.1.78"


def test_cross_site_posts_rejected(env):
    main, _, client = env
    resp = client.post("/ip/8.8.8.8/label", data={"name": "pwned"}, headers={"Origin": "https://evil.example"})
    assert resp.status_code == 403
    assert main.db.query_one("SELECT * FROM manual_ip WHERE ip = '8.8.8.8'") is None
    resp = client.post("/ip/8.8.8.8/label", data={"name": "ok"}, headers={"Origin": "http://localhost"})
    assert resp.status_code == 302


def test_errors_shown_in_ui_are_redacted(env):
    main, _, _ = env
    main.config.tautulli_api_key = "SECRETKEY123"
    msg = main.refresher._redact(
        "HTTPError: 401 Client Error: Unauthorized for url: http://tautulli:8181/api/v2?apikey=SECRETKEY123&cmd=get_history"
    )
    assert "SECRETKEY123" not in msg and "apikey" not in msg
    assert "http://tautulli:8181/api/v2?***" in msg


def test_post_without_origin_rejected(env):
    _, _, client = env
    client.environ_base.pop("HTTP_ORIGIN")
    assert client.post("/refresh").status_code == 403


def test_dns_rebinding_hosts_rejected(env):
    main, _, client = env
    assert client.get("/", headers={"Host": "attacker.example"}).status_code == 403
    assert client.get("/", headers={"Host": "192.168.1.30:9595"}).status_code == 200
    assert client.get("/", headers={"Host": "[::1]:9595"}).status_code == 200
    main.config.allowed_hosts = ["unraid.tail1234.ts.net"]
    assert client.get("/", headers={"Host": "unraid.tail1234.ts.net:9595"}).status_code == 200


def test_non_devices_named_and_kept_out_of_inbox(env):
    main, _, client = env
    n = names(main)
    assert n["192.168.1.255"]["name"] == "LAN broadcast"
    for ip in ("10.30.131.86", "172.17.0.4", "172.18.0.1"):
        assert n[ip]["kind"] == "private" and n[ip]["is_lan"] == 0 and n[ip]["mac"] is None, ip
    page = client.get("/inbox").data.decode()
    for text in ("LAN broadcast", "Private address", "10.30.131.86", "172.17.0.4"):
        assert text not in page
    # A stray 172.17.0.4 sample carried Unraid's MAC; Unraid's MAC must still point at Unraid's real IP.
    assert main.db.query_one("SELECT last_ip FROM macs WHERE mac = '0c:42:a1:63:8c:ec'")["last_ip"] == "192.168.1.30"


def test_lan_ness_recomputed_when_lan_cidrs_change(env):
    main, _, _ = env
    main.db.execute("UPDATE ips SET is_lan = 1, mac = '0c:42:a1:63:8c:ec' WHERE ip = '172.18.0.1'")  # as the old default stored it
    main.refresher.relabel()
    row = names(main)["172.18.0.1"]
    assert (row["is_lan"], row["mac"], row["kind"]) == (0, None, "private")
