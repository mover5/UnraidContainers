import gzip
import subprocess
from datetime import datetime
from pathlib import Path

from ..common import BACKUP_DIR, log, parse_interval, parse_retention

SOURCE_TYPE = "mysql"
CONFIG_KEY = "mysql_servers"
LEGACY_KEYS = ["servers"]

_MYSQL_DIR = BACKUP_DIR / "mysql"
_REQUIRED_FIELDS = ("name", "host", "user", "password", "databases")


def backup_dir(source_name):
    """Return the backup directory Path for a MySQL server."""
    return _MYSQL_DIR / source_name


def validate(source, index, errors, global_interval, global_retention):
    """Validate and mutate a MySQL server config dict."""
    for field in _REQUIRED_FIELDS:
        if not source.get(field):
            errors.append(f"MySQL server #{index + 1}: '{field}' is required.")
    if isinstance(source.get("databases"), list) and not source["databases"]:
        errors.append(f"MySQL server #{index + 1}: 'databases' must not be empty.")
    source.setdefault("port", 3306)

    if "backup_interval" in source:
        try:
            source["_interval"] = parse_interval(source["backup_interval"])
        except ValueError as e:
            errors.append(f"MySQL server #{index + 1}: {e}")
            source["_interval"] = global_interval
    else:
        source["_interval"] = global_interval

    if "backup_retention" in source:
        try:
            source["_retention"] = parse_retention(source["backup_retention"])
        except ValueError as e:
            errors.append(f"MySQL server #{index + 1}: {e}")
            source["_retention"] = global_retention
    else:
        source["_retention"] = global_retention


def run_backup(source):
    """Run mysqldump for each database on a single server, saving gzip-compressed files."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    server_dir = backup_dir(source["name"])
    server_dir.mkdir(parents=True, exist_ok=True)

    for database in source["databases"]:
        filename = f"{database}_{timestamp}.sql.gz"
        filepath = server_dir / filename

        cmd = [
            "mysqldump",
            "-h", source["host"],
            "-P", str(source["port"]),
            "-u", source["user"],
            f"-p{source['password']}",
            "--single-transaction",
            "--routines",
            "--triggers",
            "--events",
            database,
        ]

        log.info("[%s] Backing up database '%s'...", source["name"], database)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                check=False,
            )

            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace").strip()
                log.error("[%s] mysqldump failed for '%s': %s", source["name"], database, stderr)
                continue

            with open(filepath, "wb") as f:
                f.write(gzip.compress(result.stdout))

            size_kb = filepath.stat().st_size / 1024
            log.info("[%s] Saved %s (%.1f KB)", source["name"], filename, size_kb)

        except Exception:
            log.exception("[%s] Unexpected error backing up '%s'", source["name"], database)
