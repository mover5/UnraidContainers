import logging
import re
from pathlib import Path

BACKUP_DIR = Path("/backups")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("backup")


def parse_interval(value):
    """Parse a human-readable interval like '6h', '30m', '7d' into seconds."""
    match = re.fullmatch(r"(\d+)([mhd])", value.strip().lower())
    if not match:
        raise ValueError(
            f"Invalid interval '{value}'. Use a number followed by m/h/d (e.g. 6h, 30m, 7d)."
        )
    amount = int(match.group(1))
    unit = match.group(2)
    multipliers = {"m": 60, "h": 3600, "d": 86400}
    return amount * multipliers[unit]


def parse_retention(value):
    """Parse a retention count (e.g. '5', '30'). Returns an integer >= 1."""
    try:
        count = int(str(value).strip())
    except (ValueError, TypeError):
        raise ValueError(
            f"Invalid retention '{value}'. Use a positive integer (number of backups to keep)."
        )
    if count < 1:
        raise ValueError(
            f"Invalid retention '{value}'. Must be at least 1."
        )
    return count


def _format_interval(seconds):
    """Format seconds into a human-readable string like '6h', '30m', '7d'."""
    if seconds >= 86400 and seconds % 86400 == 0:
        return f"{seconds // 86400}d"
    if seconds >= 3600 and seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    return f"{seconds // 60}m"
