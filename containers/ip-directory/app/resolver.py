"""Decide one name per IP from every source, in the agreed priority order.

Pure functions: everything they need arrives in a Context, so they are easy to test.
"""
import fnmatch
import hashlib
import ipaddress
from dataclasses import dataclass, field

# Sources whose names were not chosen by a person — these feed the Inbox.
AUTO_SOURCES = ("auto", "vendor", "geoip", "rdns")
# Addresses that are not devices to name — never shown in the Inbox.
NOT_DEVICE_KINDS = ("multicast", "broadcast", "private", "tailscale")
TAILSCALE = ipaddress.ip_network("100.64.0.0/10")

SPECIAL = {
    "255.255.255.255": "Broadcast",
    "0.0.0.0": "Unspecified (0.0.0.0)",
    "224.0.0.251": "mDNS multicast",
    "239.255.255.250": "SSDP / UPnP multicast",
    "224.0.0.1": "All-hosts multicast",
    "224.0.0.22": "IGMP multicast",
}


@dataclass
class Context:
    lan_networks: list
    manual_ip: dict = field(default_factory=dict)      # ip -> {name, kind}
    manual_mac: dict = field(default_factory=dict)     # mac -> {name, kind}
    range_rules: list = field(default_factory=list)    # [(network, {name, kind})]
    tautulli: dict = field(default_factory=dict)       # ip -> {friendly_name, player}
    adguard: dict = field(default_factory=dict)        # ip-or-mac -> name
    owner_rules: list = field(default_factory=list)    # [(pattern, replacement)] in order
    geo: object = None                                 # callable ip -> dict, or None
    vendor: object = None                              # callable mac -> str, or None


def is_lan(ip, lan_networks):
    addr = ipaddress.ip_address(ip)
    return any(addr in net for net in lan_networks)


def is_randomized_mac(mac):
    """Locally-administered bit set = randomized/'private' MAC — except Docker's 02:42:* addresses."""
    if not mac:
        return False
    first = int(mac.split(":")[0], 16)
    return bool(first & 0x02) and not mac.lower().startswith("02:42:")


def rename_owner(org, asn, rules):
    if not org and not asn:
        return None
    for pattern, replacement in rules:
        p = pattern.strip().upper()
        if p.startswith("AS") and p[2:].isdigit():
            if asn and int(p[2:]) == int(asn):
                return replacement
        elif org and fnmatch.fnmatchcase(org.upper(), p):
            return replacement
    return org


def format_location(city, region, country):
    parts = [p for p in (city, region) if p]
    if country and country != "US":
        parts.append(country)
    if not parts and country:
        parts.append(country)
    return ", ".join(parts) or None


def _short_mac(mac):
    return mac[-5:] if mac else ""


def resolve(ip, mac, ctx):
    """Return (label, opinions).

    label: dict(name, kind, source, owner, asn, location, country)
    opinions: [(source, name)] — what every source would call this IP, for the detail page.
    """
    lan = is_lan(ip, ctx.lan_networks)
    opinions = []

    geo = {}
    addr = ipaddress.ip_address(ip)
    if not lan and ctx.geo and addr.is_global:
        geo = ctx.geo(ip) or {}
    owner = rename_owner(geo.get("org"), geo.get("asn"), ctx.owner_rules)
    location = format_location(geo.get("city"), geo.get("region"), geo.get("country"))
    base = {"owner": owner, "asn": geo.get("asn"), "location": location, "country": geo.get("country")}
    default_kind = "lan" if lan else "internet"

    if ip in ctx.manual_ip:
        m = ctx.manual_ip[ip]
        opinions.append(("manual", m["name"]))
    if lan and mac and mac in ctx.manual_mac:
        opinions.append(("manual-mac", ctx.manual_mac[mac]["name"]))
    for net, rule in ctx.range_rules:
        if addr in net:
            opinions.append(("manual-range", rule["name"]))
            break
    if ip in ctx.tautulli:
        t = ctx.tautulli[ip]
        # A LAN IP is a device in the house — name it by its Plex player; a public IP is a person.
        name = f'{t["player"]} ({t["friendly_name"]})' if lan and t.get("player") else t["friendly_name"]
        opinions.append(("tautulli", name))
    if ip in ctx.adguard:
        opinions.append(("adguard", ctx.adguard[ip]))
    elif lan and mac and mac in ctx.adguard:
        opinions.append(("adguard", ctx.adguard[mac]))

    vendor = ctx.vendor(mac) if (lan and mac and ctx.vendor) else None
    auto_kind = None
    if ip in SPECIAL or addr.is_multicast:
        opinions.append(("auto", SPECIAL.get(ip, "Multicast")))
        auto_kind = "broadcast" if ip == "255.255.255.255" else "multicast"
    elif any(net.prefixlen < net.max_prefixlen and addr == net.broadcast_address for net in ctx.lan_networks):
        opinions.append(("auto", "LAN broadcast"))
        auto_kind = "broadcast"
    elif lan:
        if is_randomized_mac(mac):
            opinions.append(("auto", f"Unknown phone ({_short_mac(mac)})"))
        elif vendor:
            opinions.append(("vendor", f"{vendor} device ({_short_mac(mac)})"))
        else:
            suffix = f" ({_short_mac(mac)})" if mac else ""
            opinions.append(("auto", f"Unknown LAN device{suffix}"))
    elif addr in TAILSCALE:
        opinions.append(("auto", "Tailscale node"))
        auto_kind = "tailscale"
    elif addr.is_link_local:
        opinions.append(("auto", "Link-local address"))
        auto_kind = "private"
    elif addr.is_private:
        # Docker networks inside Unraid, or a remote peer's LAN address (e.g. Tailscale probing for a direct path).
        opinions.append(("auto", "Private address (not on this LAN)"))
        auto_kind = "private"
    else:
        if owner and location:
            opinions.append(("geoip", f"{owner} · {location}"))
        elif owner or location:
            opinions.append(("geoip", owner or location))
        else:
            opinions.append(("auto", "Unknown"))

    source, name = opinions[0]
    kind = default_kind
    if source == "manual":
        kind = ctx.manual_ip[ip].get("kind") or default_kind
    elif source == "manual-mac":
        kind = ctx.manual_mac[mac].get("kind") or default_kind
    elif source == "manual-range":
        kind = next(r for n, r in ctx.range_rules if addr in n).get("kind") or default_kind
    elif source == "tautulli":
        kind = "plex"
    elif source == "auto" and name.startswith("Unknown phone"):
        kind = "phone"
    elif auto_kind and source == "auto":
        kind = auto_kind

    label = dict(base, name=name, kind=kind, source=source, vendor=vendor)
    return label, opinions


def label_hash(label):
    raw = "|".join(str(label.get(k) or "") for k in ("name", "kind", "source", "owner", "location", "mac"))
    return hashlib.sha1(raw.encode()).hexdigest()
