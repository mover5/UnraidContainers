import time
from glob import glob
from pathlib import Path

from .common import BACKUP_DIR, log, _format_interval
from .config import load_config
from .state import shared_state
from . import sources


def cleanup_source_backups(source_dir, retention_count):
    """Keep the N most recent backup files and delete the rest.

    Always keeps at least one backup file regardless of the retention count.
    """
    extensions = ("*.sql.gz", "*.tar.gz", "*.json.gz")

    all_files = []
    for ext in extensions:
        pattern = str(source_dir / "**" / ext)
        for filepath in glob(pattern, recursive=True):
            path = Path(filepath)
            mtime = path.stat().st_mtime
            all_files.append((path, mtime))

    keep = max(retention_count, 1)
    if len(all_files) <= keep:
        return

    all_files.sort(key=lambda x: x[1], reverse=True)

    for path, _mtime in all_files[keep:]:
        try:
            path.unlink()
            log.info("Deleted old backup: %s (keeping %d most recent)", path.name, keep)
        except OSError:
            log.exception("Failed to delete %s", path.name)


def _latest_backup_age(source_dir):
    """Return the age in seconds of the most recent backup file in source_dir, or None if empty."""
    extensions = ("*.sql.gz", "*.tar.gz", "*.json.gz")
    newest_mtime = None
    for ext in extensions:
        pattern = str(source_dir / "**" / ext)
        for filepath in glob(pattern, recursive=True):
            mtime = Path(filepath).stat().st_mtime
            if newest_mtime is None or mtime > newest_mtime:
                newest_mtime = mtime
    if newest_mtime is None:
        return None
    return time.time() - newest_mtime


def scheduler_loop():
    """Main scheduler loop. Designed to run in a daemon thread."""
    log.info("Starting backup scheduler (config reloaded each cycle)")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Track last backup time per source name (empty → all run immediately)
    last_backup: dict[str, float] = {}

    while True:
        try:
            config = load_config()
        except SystemExit:
            log.warning("Config is invalid or missing — retrying in 30s")
            shared_state.wait_for_wake(timeout=30)
            continue

        # Build list of all sources with their handler
        all_sources = []
        for handler in sources.ALL_SOURCES:
            for source in config.get(handler.CONFIG_KEY, []):
                all_sources.append((handler, source))

        # Update shared state with source info and log each source
        for handler, source in all_sources:
            shared_state.update_source(
                source["name"],
                source_type=handler.SOURCE_TYPE,
                interval_seconds=source["_interval"],
                retention_count=source["_retention"],
            )
            log.info(
                "[%s] %s source — interval: %s, retention: %d copies",
                source["name"],
                handler.SOURCE_TYPE,
                _format_interval(source["_interval"]),
                source["_retention"],
            )

        # Seed last_backup from disk for sources not yet tracked (e.g. after restart)
        now = time.monotonic()
        for handler, source in all_sources:
            name = source["name"]
            if name not in last_backup:
                age = _latest_backup_age(handler.backup_dir(name))
                if age is not None and age < source["_interval"]:
                    last_backup[name] = now - age
                    shared_state.update_source(
                        name,
                        last_backup_monotonic=last_backup[name],
                        last_backup_wall=time.time() - age,
                    )
                    log.info("[%s] Found recent backup (%.0fm ago), skipping until next interval", name, age / 60)

        # Check for manual triggers
        manual_triggers = set(shared_state.pop_manual_triggers())

        # Determine which sources are due
        now = time.monotonic()
        due_sources = []
        for handler, source in all_sources:
            name = source["name"]
            is_manual = name in manual_triggers
            is_scheduled = name not in last_backup or (now - last_backup[name] >= source["_interval"])
            if is_manual or is_scheduled:
                due_sources.append((handler, source))

        # Run backups for due sources
        if due_sources:
            names = [s["name"] for _, s in due_sources]
            log.info("Running backup for due sources: %s", ", ".join(names))

            for handler, source in due_sources:
                name = source["name"]
                shared_state.update_source(name, is_running=True, last_error=None)
                try:
                    handler.run_backup(source)
                    cleanup_source_backups(handler.backup_dir(name), source["_retention"])
                    now_mono = time.monotonic()
                    last_backup[name] = now_mono
                    shared_state.update_source(
                        name,
                        is_running=False,
                        last_backup_monotonic=now_mono,
                        last_backup_wall=time.time(),
                    )
                except Exception as e:
                    log.exception("[%s] Backup failed", name)
                    shared_state.update_source(name, is_running=False, last_error=str(e))
                    last_backup[name] = time.monotonic()

        # Prune last_backup entries and shared state for sources no longer in config
        current_names = {s["name"] for _, s in all_sources}
        for name in list(last_backup):
            if name not in current_names:
                del last_backup[name]
                shared_state.remove_source(name)

        # Compute sleep until next due source
        if all_sources:
            now = time.monotonic()
            next_due = min(
                max(0, last_backup[source["name"]] + source["_interval"] - now)
                for _, source in all_sources
            )
            sleep_time = max(next_due, 10)  # at least 10s to avoid busy-spinning
        else:
            sleep_time = 30

        log.info("Next source due in %s. Sleeping...", _format_interval(int(sleep_time)))
        shared_state.wait_for_wake(timeout=sleep_time)


# Keep backward compat alias for existing tests that import main
main = scheduler_loop
