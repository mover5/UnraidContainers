import logging
import os
import re
import threading
import time

import requests

logger = logging.getLogger(__name__)

# Wireshark's manufacturer list: MAC prefix -> vendor. No account needed.
MANUF_URL = "https://www.wireshark.org/download/automated/data/manuf"
MAX_AGE_SECONDS = 30 * 86400

_SUFFIXES = re.compile(
    r"[,.\s]+(inc|incorporated|corp|corporate|corporation|co|company|ltd|limited|llc|gmbh|ag|bv|b\.v|s\.a|sa|oy|ab|plc|pte)\.?$",
    re.I,
)


def _tidy(name):
    name = name.strip()
    for _ in range(3):  # "Foo Co., Ltd." needs more than one pass
        name = _SUFFIXES.sub("", name).strip().rstrip(",.")
    return name


class Vendors:
    def __init__(self, config):
        self.path = os.path.join(config.config_path, "manuf.txt")
        self._tables = None  # {prefix_bits: {prefix_int: vendor}}
        self._lock = threading.Lock()

    def update(self, force=False):
        if not force and os.path.exists(self.path) and time.time() - os.path.getmtime(self.path) < MAX_AGE_SECONDS:
            return f"{self.count()} prefixes"
        resp = requests.get(MANUF_URL, timeout=60)
        resp.raise_for_status()
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(resp.text)
        os.replace(tmp, self.path)
        with self._lock:
            self._tables = None
        return f"downloaded, {self.count()} prefixes"

    def _load(self):
        with self._lock:
            if self._tables is not None:
                return self._tables
            tables = {}
            if os.path.exists(self.path):
                with open(self.path, encoding="utf-8", errors="replace") as f:
                    for line in f:
                        if not line.strip() or line.startswith("#"):
                            continue
                        parts = [p.strip() for p in line.rstrip("\n").split("\t")]
                        if len(parts) < 2:
                            continue
                        prefix, _, bits = parts[0].partition("/")
                        hexdigits = prefix.replace(":", "").replace("-", "")
                        bits = int(bits) if bits else len(hexdigits) * 4
                        value = int(hexdigits.ljust(12, "0"), 16) >> (48 - bits)
                        vendor = parts[2] if len(parts) > 2 and parts[2] else parts[1]
                        tables.setdefault(bits, {})[value] = _tidy(vendor)
            self._tables = tables
            return tables

    def count(self):
        return sum(len(t) for t in self._load().values())

    def lookup(self, mac):
        if not mac:
            return None
        try:
            value = int(mac.replace(":", "").replace("-", ""), 16)
        except ValueError:
            return None
        # Longest (most specific) prefix wins.
        for bits, table in sorted(self._load().items(), reverse=True):
            vendor = table.get(value >> (48 - bits))
            if vendor:
                return vendor
        return None
