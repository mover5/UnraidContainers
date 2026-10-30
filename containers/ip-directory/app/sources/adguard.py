import ipaddress
import logging
import re

import requests

logger = logging.getLogger(__name__)

_MAC = re.compile(r"^[0-9a-f]{2}([:-][0-9a-f]{2}){5}$", re.I)


def _key(identifier):
    """AdGuard client IDs can be an IP, a MAC, a CIDR or a ClientID; only IPs and MACs are usable."""
    identifier = identifier.strip()
    if _MAC.match(identifier):
        return identifier.lower().replace("-", ":")
    try:
        return str(ipaddress.ip_address(identifier))
    except ValueError:
        return None


def sync(config, db):
    auth = (config.adguard_user, config.adguard_password) if config.adguard_user else None
    resp = requests.get(f"{config.adguard_url}/control/clients", auth=auth, timeout=15)
    resp.raise_for_status()
    body = resp.json()

    entries = {}
    # Runtime clients first so persistent (hand-named in AdGuard) ones overwrite them.
    for c in body.get("auto_clients") or []:
        key = _key(c.get("ip") or "")
        if key and c.get("name"):
            entries[key] = (c["name"], f"runtime:{c.get('source') or '?'}")
    for c in body.get("clients") or []:
        for identifier in c.get("ids") or []:
            key = _key(identifier)
            if key and c.get("name"):
                entries[key] = (c["name"], "persistent")

    with db.tx() as conn:
        conn.execute("DELETE FROM adguard")
        conn.executemany(
            "INSERT INTO adguard (key, name, origin) VALUES (?, ?, ?)",
            [(k, n, o) for k, (n, o) in entries.items()],
        )
    return f"{len(entries)} named clients"
