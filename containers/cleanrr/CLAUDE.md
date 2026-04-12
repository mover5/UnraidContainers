# cleanrr

Torrent lifecycle manager for Deluge. Connects to the Deluge Web API, tracks torrents in SQLite, and auto-removes them after a configurable seed duration. Flask web dashboard on port 9494.

## Development

```bash
cd containers/cleanrr
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run locally (requires accessible Deluge instance)
DELUGE_HOST=<ip> DELUGE_PORT=8112 DELUGE_PASSWORD=<pass> CONFIG_PATH=./config python run.py
```

Dashboard at `http://localhost:9494`. No test suite.

## Architecture

```
run.py → app/main.py (Flask + API routes)
              ├→ config.py      reads env vars (DELUGE_HOST, DELUGE_PORT, DELUGE_PASSWORD, CONFIG_PATH)
              ├→ database.py    SQLite at {CONFIG_PATH}/cleanrr.db (torrents + settings tables)
              ├→ deluge.py      JSON-RPC client to Deluge Web API (not the daemon RPC protocol)
              └→ scheduler.py   APScheduler background job
                    ├→ calls deluge.get_torrents() on interval
                    ├→ calculates removal date from Deluge's seeding_time field
                    └→ auto-removes expired, unprotected torrents with data deletion
```

**Frontend:** Vanilla JS single-page dashboard (`templates/index.html`, `static/js/app.js`, `static/css/style.css`). No build step. Auto-refreshes every 30 seconds.

## Key Design Decisions

- **Deluge Web API over HTTP** (port 8112), not the daemon RPC protocol (58846), because most Docker/Unraid setups don't expose the daemon port.
- **seeding_time** (Deluge's live counter in seconds) is used for removal calculation instead of `completed_time` (which is unreliable). Scheduled removal = now + (seed_days * 86400 - seeding_time).
- **Seed time supports floats** (e.g. 14.1 days). All casts must use `float()` not `int()`.
- **Protected torrents** are never auto-removed and their `scheduled_removal` is not recalculated when settings change (enforced via SQL CASE in upsert).
- **All timestamps** are UTC ISO format strings. Frontend appends "Z" when parsing.
- **No authentication** on the dashboard — expected to run behind a firewall or reverse proxy.

## API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | Dashboard HTML |
| `/api/torrents` | GET | List torrents (`?show_removed=true` includes removed) |
| `/api/torrents/<hash>/protect` | POST | Protect from auto-removal |
| `/api/torrents/<hash>/unprotect` | POST | Remove protection |
| `/api/torrents/<hash>/dismiss` | POST | Dismiss a missing torrent from tracking |
| `/api/torrents/<hash>` | DELETE | Immediately remove and delete data |
| `/api/settings` | GET | Get seed_time_days and check_interval_minutes |
| `/api/settings` | PUT | Update settings (triggers recalculation if seed_time changes) |
| `/api/status` | GET | Connection status and last check time |
| `/api/check` | POST | Trigger immediate torrent check |

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| DELUGE_HOST | localhost | Deluge Web UI hostname/IP |
| DELUGE_PORT | 8112 | Deluge Web UI port |
| DELUGE_PASSWORD | deluge | Deluge Web UI password |
| CONFIG_PATH | /config | SQLite database storage path |
