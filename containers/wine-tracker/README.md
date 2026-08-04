# 🍷 Wine Tracker

A tiny, mobile-first app for tracking the wine you win (trivia-night trophies and
all). Log bottles by **name** and **year**, note the **date you won** each one,
and mark bottles **drunk** to move them into your history — so you always know
what's in stock and never double-add a duplicate.

- **Frontend:** a single self-contained HTML page — mobile-first, dark-mode
  aware, no build step and no CDN (works on your LAN offline).
- **Backend:** a small Express API that also serves the page. One container.
- **Database:** a local **SQLite** file at `/data/wine.db`. Map `/data` to a
  persistent path and your cellar survives reboots, image updates, and
  container recreation. No external database to run.

## Features

- **Cellar view** — everything currently in stock, alphabetical.
- **History view** — every bottle you've drunk, most recent first, with the
  won → drank dates.
- **Add a bottle** — name, optional year, optional "date won" (leave the date
  blank when backfilling your existing cellar).
- **Mark drank** — one tap, pick a date (defaults to today); it moves to History.
  Undo it any time to send it back to the cellar.
- **Edit / delete** any bottle.
- **Search** and a **duplicate warning** when you add a name + year already in
  the cellar.

## Data model

One table, `wines`:

| column | meaning |
|---|---|
| `id` | auto id |
| `name` | wine name (required) |
| `year` | vintage year (optional — blank for non-vintage) |
| `won_date` | `YYYY-MM-DD` you won it (optional) |
| `drank_date` | `YYYY-MM-DD` you drank it — **null means it's still in the cellar** |
| `created_at` | when the row was added |

The schema is created automatically on first start.

## Run it

### Docker Compose (local) — recommended

```bash
docker compose up --build
```

Open <http://localhost:8080>. The SQLite file is written to `./data/wine.db`.

### Without Docker

```bash
npm install
DB_PATH=./data/wine.db npm start
```

Open <http://localhost:8080>.

### docker run

```bash
docker run -d --name wine-tracker -p 8080:8080 \
  -v /mnt/user/appdata/wine-tracker:/data \
  ghcr.io/mover5/wine-tracker:latest
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8080` | Port the server listens on. |
| `DB_PATH` | `/data/wine.db` | Path to the SQLite database file. |

## API

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/wines?status=cellar\|drank\|all` | List bottles (default `cellar`). |
| `POST` | `/api/wines` | Add: `{ name, year?, won_date? }`. |
| `PATCH` | `/api/wines/:id` | Update any of `name/year/won_date/drank_date`. Set `drank_date: null` to un-drink. |
| `DELETE` | `/api/wines/:id` | Remove a bottle. |
| `GET` | `/api/health` | Health check. |

## Deploy on Unraid

Publishes to `ghcr.io/mover5/wine-tracker`. Add this repo as a template
repository (**Docker → Template Repositories**) and install **wine-tracker**, or
run the `docker run` command above. Map **/data** to persistent storage
(e.g. `/mnt/user/appdata/wine-tracker`) and include that path in your appdata
backups to keep your cellar safe.
