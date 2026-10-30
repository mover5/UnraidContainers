import ipaddress

from app import resolver

LAN = [ipaddress.ip_network("192.168.0.0/16")]


def ctx(**kw):
    return resolver.Context(lan_networks=LAN, **kw)


def test_manual_ip_beats_everything():
    c = ctx(
        manual_ip={"98.232.108.93": {"name": "Home WAN (R8000)", "kind": "wan"}},
        tautulli={"98.232.108.93": {"friendly_name": "moverholt", "player": "iPhone"}},
    )
    label, opinions = resolver.resolve("98.232.108.93", None, c)
    assert label["name"] == "Home WAN (R8000)"
    assert label["kind"] == "wan"
    assert label["source"] == "manual"
    assert [s for s, _ in opinions][:2] == ["manual", "tautulli"]


def test_manual_mac_names_lan_device_whatever_its_ip():
    c = ctx(manual_mac={"0c:42:a1:63:8c:ec": {"name": "Unraid", "kind": "server"}})
    for ip in ("192.168.1.30", "192.168.1.31"):
        label, _ = resolver.resolve(ip, "0c:42:a1:63:8c:ec", c)
        assert (label["name"], label["kind"], label["source"]) == ("Unraid", "server", "manual-mac")


def test_manual_mac_ignored_for_public_ip():
    # The router forwards internet traffic with its own MAC; that must not name the internet host.
    c = ctx(manual_mac={"cc:40:d0:74:bf:ef": {"name": "R8000 router", "kind": "router"}})
    label, _ = resolver.resolve("8.8.8.8", "cc:40:d0:74:bf:ef", c)
    assert label["name"] != "R8000 router"


def test_range_rule_beats_tautulli_but_not_manual_ip():
    net = ipaddress.ip_network("10.8.0.0/16")
    c = ctx(
        range_rules=[(net, {"name": "Work VPN", "kind": "vpn"})],
        tautulli={"10.8.1.1": {"friendly_name": "someone", "player": ""}},
    )
    label, _ = resolver.resolve("10.8.1.1", None, c)
    assert (label["name"], label["source"], label["kind"]) == ("Work VPN", "manual-range", "vpn")


def test_tautulli_public_ip_is_the_person():
    c = ctx(tautulli={"50.82.218.165": {"friendly_name": "oyoj4", "player": "Roku"}})
    label, _ = resolver.resolve("50.82.218.165", None, c)
    assert (label["name"], label["kind"], label["source"]) == ("oyoj4", "plex", "tautulli")


def test_tautulli_lan_ip_is_the_player():
    c = ctx(tautulli={"192.168.1.84": {"friendly_name": "moverholt", "player": "Living Room"}})
    label, _ = resolver.resolve("192.168.1.84", "bc:d7:d4:3d:d5:c8", c)
    assert label["name"] == "Living Room (moverholt)"


def test_adguard_by_ip_then_by_mac():
    c = ctx(adguard={"192.168.1.88": "Desktop", "bc:fc:e7:72:79:5e": "Old name"})
    assert resolver.resolve("192.168.1.88", "bc:fc:e7:72:79:5e", c)[0]["name"] == "Desktop"
    c = ctx(adguard={"bc:fc:e7:72:79:5e": "Desktop"})
    assert resolver.resolve("192.168.1.88", "bc:fc:e7:72:79:5e", c)[0]["source"] == "adguard"


def test_randomized_mac_is_unknown_phone():
    label, _ = resolver.resolve("192.168.1.78", "16:01:45:de:91:d0", ctx())
    assert label["name"] == "Unknown phone (91:d0)"
    assert label["kind"] == "phone"
    assert label["source"] in resolver.AUTO_SOURCES


def test_docker_mac_is_not_a_phone():
    assert not resolver.is_randomized_mac("02:42:c0:a8:01:02")
    assert resolver.is_randomized_mac("76:65:32:a5:72:8e")
    assert not resolver.is_randomized_mac("00:17:88:46:be:38")


def test_vendor_fallback_for_lan():
    c = ctx(vendor=lambda mac: "Signify" if mac.startswith("00:17:88") else None)
    label, _ = resolver.resolve("192.168.1.61", "00:17:88:46:be:38", c)
    assert (label["name"], label["source"]) == ("Signify device (be:38)", "vendor")
    label, _ = resolver.resolve("192.168.1.99", "1c:db:d4:6c:30:54", c)
    assert label["name"] == "Unknown LAN device (30:54)"


def test_public_ip_named_by_owner_and_location():
    geo = lambda ip: {"asn": 54113, "org": "FASTLY", "city": "San Jose", "region": "CA", "country": "US"}
    c = ctx(geo=geo, owner_rules=[("FASTLY", "Fastly")])
    label, _ = resolver.resolve("199.232.214.172", None, c)
    assert label["name"] == "Fastly · San Jose, CA"
    assert (label["owner"], label["location"], label["source"]) == ("Fastly", "San Jose, CA", "geoip")


def test_public_ip_without_geo_is_unknown_not_bare():
    label, _ = resolver.resolve("203.0.113.9", None, ctx())
    assert label["name"] == "Unknown"


def test_owner_rules_order_wildcards_and_asn():
    rules = [("GOOGLE-CLOUD-PLATFORM", "Google Cloud"), ("GOOGLE*", "Google"), ("AS2906", "Netflix")]
    assert resolver.rename_owner("GOOGLE-CLOUD-PLATFORM", 396982, rules) == "Google Cloud"
    assert resolver.rename_owner("GOOGLE", 15169, rules) == "Google"
    assert resolver.rename_owner("google-fiber", 16591, rules) == "Google"
    assert resolver.rename_owner("AS-SSI", 2906, rules) == "Netflix"
    assert resolver.rename_owner("COMCAST-7922", 7922, rules) == "COMCAST-7922"


def test_location_formatting():
    assert resolver.format_location("Seattle", "WA", "US") == "Seattle, WA"
    assert resolver.format_location("Paris", "IDF", "FR") == "Paris, IDF, FR"
    assert resolver.format_location(None, None, "DE") == "DE"
    assert resolver.format_location(None, None, None) is None


def test_multicast_and_broadcast():
    assert resolver.resolve("239.255.255.250", None, ctx())[0]["name"] == "SSDP / UPnP multicast"
    label, _ = resolver.resolve("224.0.0.99", None, ctx())
    assert (label["name"], label["kind"]) == ("Multicast", "multicast")


def test_label_hash_changes_with_name():
    a = {"name": "x", "kind": "lan", "source": "auto", "owner": None, "location": None}
    assert resolver.label_hash(a) != resolver.label_hash(dict(a, name="y"))
    assert resolver.label_hash(a) == resolver.label_hash(dict(a))
