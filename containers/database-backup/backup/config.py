import json
import sys
from pathlib import Path

from .common import log, parse_interval, parse_retention
from . import sources


def load_config(path="/config/servers.json"):
    """Read and validate a JSON config file. Returns a config dict."""
    path = Path(path)
    if not path.is_file():
        log.error("Config file not found: %s", path)
        sys.exit(1)

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log.error("Failed to read config file: %s", e)
        sys.exit(1)

    errors = []

    # Parse global defaults first (needed for per-source fallback)
    interval_str = raw.get("backup_interval", "24h")
    try:
        global_interval = parse_interval(interval_str)
    except ValueError as e:
        errors.append(str(e))
        global_interval = 86400

    retention_str = raw.get("backup_retention", "30")
    try:
        global_retention = parse_retention(retention_str)
    except ValueError as e:
        errors.append(str(e))
        global_retention = 30

    # Load and validate all source types via the registry
    config = {
        "interval": global_interval,
        "interval_str": interval_str,
        "retention": global_retention,
        "retention_str": retention_str,
    }

    has_any_source = False
    for handler in sources.ALL_SOURCES:
        source_list = raw.get(handler.CONFIG_KEY) or []
        for legacy_key in getattr(handler, "LEGACY_KEYS", []):
            if not source_list:
                source_list = raw.get(legacy_key) or []
        for i, source in enumerate(source_list):
            handler.validate(source, i, errors, global_interval, global_retention)
        config[handler.CONFIG_KEY] = source_list
        if source_list:
            has_any_source = True

    if not has_any_source:
        keys = " or ".join(
            f"'{h.CONFIG_KEY}'" + (f" (or '{h.LEGACY_KEYS[0]}')" if getattr(h, "LEGACY_KEYS", []) else "")
            for h in sources.ALL_SOURCES
        )
        log.error("Config must contain at least one of %s.", keys)
        sys.exit(1)

    if errors:
        for err in errors:
            log.error(err)
        sys.exit(1)

    return config
