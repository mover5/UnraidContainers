# database-backup

Scheduled database backup tool with a Flask web dashboard (port 8008). Supports MySQL and Azure Storage (blobs, file shares, tables) as backup sources, with configurable intervals and retention policies.

## Development

```bash
cd containers/database-backup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Run locally (requires /config/servers.json)
mkdir -p config backups
python backup.py
# Scheduler starts + Flask listens on http://localhost:8008

# Run tests
pytest tests/
```

## Architecture

```
backup.py (entry point)
  ├→ scheduler thread (backup/scheduler.py)
  │     ├→ loads config from /config/servers.json
  │     ├→ checks intervals, runs backups, manages retention
  │     └→ wakes on manual triggers from web UI
  └→ Flask web app (backup/web/)
        ├→ dashboard with source status and manual triggers
        └→ CRUD for backup sources (reads/writes servers.json)
```

**Thread-safe shared state** (`backup/state.py`): `SchedulerState` coordinates between scheduler and web UI — tracks per-source status, queues manual triggers, uses threading events for wake-up.

## Backup Sources (Plugin System)

Sources live in `backup/sources/`. Each module exports: `SOURCE_TYPE`, `CONFIG_KEY`, `backup_dir()`, `validate()`, `run_backup()`.

### MySQL (`backup/sources/mysql.py`)
- Config key: `"mysql_servers"` (legacy: `"servers"`)
- Uses `mysqldump --single-transaction --routines --triggers --events`
- Output: `<database>_YYYY-MM-DD_HHMMSS.sql.gz` under `/backups/mysql/<server_name>/`

### Azure Storage (`backup/sources/azure.py`)
- Config key: `"storage_accounts"`
- Backs up blobs (`.tar.gz`), file shares (`.tar.gz`), and tables (`.json.gz`)
- Output under `/backups/azure-storage/<account_name>/{blobs,files,tables}/`

### Adding a new source
1. Create `backup/sources/newsource.py` with `SOURCE_TYPE`, `CONFIG_KEY`, `backup_dir()`, `validate()`, `run_backup()`
2. Add to `backup/sources/__init__.py` in `ALL_SOURCES`
3. Add form fields to `backup/web/routes.py` (`_extract_form_data()`, `_validate_source()`)
4. Update `backup/web/templates/source_form.html`
5. Add tests in `tests/`

## Configuration

**File:** `/config/servers.json`

```json
{
  "backup_interval": "24h",
  "backup_retention": "30d",
  "mysql_servers": [...],
  "storage_accounts": [...]
}
```

Global `backup_interval` and `backup_retention` apply as defaults; each source can override with its own values. Intervals/retention accept formats like `"30m"`, `"6h"`, `"7d"`.

## Retention Policy

Runs after every successful backup. Deletes files older than retention, but always keeps at least 1 backup per source. Scans `.sql.gz`, `.tar.gz`, `.json.gz` extensions.

## Web Routes

| Route | Method | Purpose |
|---|---|---|
| `/` | GET | Dashboard with all sources and status |
| `/source/<name>` | GET | Source detail with backup file list |
| `/source/<name>/backup` | POST | Trigger manual backup |
| `/source/add/<type>` | GET/POST | Add new source |
| `/source/<name>/edit` | GET/POST | Edit source config |
| `/source/<name>/delete` | GET/POST | Delete source (with confirmation) |

## Key Design Decisions

- **Scheduler uses `time.monotonic()`** for elapsed time (immune to clock skew), with wall-clock time stored separately for display.
- **Config is reloaded every cycle** so edits to `servers.json` (via UI or manually) take effect without restart.
- **On startup failure** (bad config), scheduler retries every 30 seconds instead of exiting.
- **Thread-safe config manager** (`backup/web/config_manager.py`) uses a lock for all reads/writes and strips internal keys before persisting.

## Testing

8 test modules in `tests/` covering config validation, scheduler logic, source handlers, state management, config manager, and web routes. Run with `pytest tests/`.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| WEB_PORT | 8008 | Flask dashboard port |
| SECRET_KEY | (auto) | Flask session secret key |
| TZ | (system) | Container timezone |
