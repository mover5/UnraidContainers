"""Thread-safe CRUD operations on the servers.json config file.

Separate from backup.config because load_config() calls sys.exit() on errors.
The web layer needs raw read/write without exit behavior.
"""

import json
import threading
from pathlib import Path

CONFIG_PATH = Path("/config/servers.json")

_config_lock = threading.Lock()

# Keys injected by load_config / validate that should not be persisted
_INTERNAL_KEYS = {"_interval", "_retention"}


def read_raw_config(path=None):
    """Read the config JSON file and return the raw dict (no validation/mutation)."""
    p = path or CONFIG_PATH
    with _config_lock:
        text = p.read_text(encoding="utf-8")
        return json.loads(text)


def write_config(config, path=None):
    """Write config dict to JSON, stripping internal keys."""
    p = path or CONFIG_PATH
    clean = _strip_internal(config)
    with _config_lock:
        p.write_text(json.dumps(clean, indent=2), encoding="utf-8")


def _strip_internal(obj):
    """Recursively strip internal keys from config dicts."""
    if isinstance(obj, dict):
        return {k: _strip_internal(v) for k, v in obj.items() if k not in _INTERNAL_KEYS}
    if isinstance(obj, list):
        return [_strip_internal(item) for item in obj]
    return obj


def get_source_by_name(config, name):
    """Find a source by name across all source types.

    Returns (source_dict, source_type) or (None, None).
    """
    from backup.sources import ALL_SOURCES
    for handler in ALL_SOURCES:
        for source in config.get(handler.CONFIG_KEY, []):
            if source.get("name") == name:
                return source, handler.SOURCE_TYPE
    return None, None


def add_source(config, source_type, data):
    """Append a new source to the correct config key."""
    from backup.sources import ALL_SOURCES
    for handler in ALL_SOURCES:
        if handler.SOURCE_TYPE == source_type:
            config.setdefault(handler.CONFIG_KEY, [])
            config[handler.CONFIG_KEY].append(data)
            return


def update_source(config, old_name, source_type, new_data):
    """Replace a source by name in the correct config key."""
    from backup.sources import ALL_SOURCES
    for handler in ALL_SOURCES:
        if handler.SOURCE_TYPE == source_type:
            source_list = config.get(handler.CONFIG_KEY, [])
            for i, source in enumerate(source_list):
                if source.get("name") == old_name:
                    source_list[i] = new_data
                    return


def delete_source(config, name):
    """Remove a source by name from any config key."""
    from backup.sources import ALL_SOURCES
    for handler in ALL_SOURCES:
        key = handler.CONFIG_KEY
        if key in config:
            config[key] = [s for s in config[key] if s.get("name") != name]
