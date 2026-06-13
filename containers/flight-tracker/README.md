# ✈️ Flight Tracker

A lightweight, mobile-first app for logging flights, tagging in-flight event
times with one tap, keeping timestamped notes, and visualizing the data
(taxi-out, delays, air time, and more). Built from a Google Sheet of real
flights, packaged as a single Docker container that talks to your own Postgres.

- **Frontend:** React + Vite + TypeScript, Tailwind, Recharts — local-first and
  installable as a PWA (works offline).
- **Backend:** a small Express + `pg` API server that also serves the built
  frontend. One container.
- **Database:** your existing Postgres (via `DATABASE_URL`).

## Features

- **Live logging** — big tap-to-stamp buttons for **Gate Push · Takeoff ·
  Land · Gate Arrive** that record the current time in one touch (with manual
  edit / clear). Designed for use on your phone during a flight.
- **Add flights** — a quick form for the high-level info.
- **Notes over time** — a timestamped notes thread per flight.
- **Dashboard** — on-time rate, average taxi-out, taxi time by airport,
  departure-delay trend, on-time rate by carrier, most-flown routes, total
  time aloft.
- **Derived metrics** per flight — taxi-out, taxi-in, air time (timezone
  corrected), block time, departure/arrival delay.

## Architecture

```
Browser (PWA, local-first cache + outbox)
   │  HTTPS, /api/*
   ▼
Express server  ──>  Postgres (your Unraid instance)
   │
   └── also serves the built React app (static)
```

The frontend reads and writes a **local cache** first, then syncs changes to
the API through an outbox queue — so the app works fully offline and the server
is a sync target, not a hard dependency. See [Offline support](#offline-support).

## Run it

### Full stack (Docker Compose) — recommended

Builds the image and runs it against a throwaway Postgres:

```bash
docker compose up --build
```

Open <http://localhost:8080>. On first run the database is seeded with the
imported flights. (On Unraid you won't use the bundled `db` service — point
`DATABASE_URL` at your existing Postgres instead.)

### Frontend only (quick UI work)

```bash
npm install
npm run dev
```

With no `VITE_API_URL` set, the app runs in **local-only mode** (browser
storage, seeded with the flights) — handy for iterating on the UI without a
backend. To dev against a running API, start the server (below) and run
`VITE_API_URL=/api npm run dev`; the vite proxy forwards `/api` to `:8080`.

### Backend without Docker

```bash
cd server && npm install
DATABASE_URL=postgres://user:pass@localhost:5432/flighttracker \
PUBLIC_DIR=../dist npm start    # build the frontend first: `npm run build`
```

## Configuration

| Variable | Where | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | server | — | Postgres connection string (`postgres://user:pass@host:port/db`). |
| `DATABASE_SSL` | server | `false` | Set `true` if your Postgres requires SSL. |
| `PORT` | server | `8080` | Port the server listens on. |
| `SEED_ON_EMPTY` | server | `true` | Seed the imported flights on first run if the DB is empty. |
| `VITE_API_URL` | build | `/api` (Docker) | API base URL baked into the frontend. Unset ⇒ local-only mode. |

The schema (tables + indexes) is created automatically on startup.

## Deploy on Unraid

The image publishes to `ghcr.io/mover5/flight-tracker` once it's in the
[UnraidContainers](https://github.com/mover5/UnraidContainers) repo (see below).
Then either add the template repo in **Docker → Template Repositories** and
install **flight-tracker**, or run it directly:

```bash
docker run -d --name flight-tracker -p 8080:8080 \
  -e DATABASE_URL=postgres://user:pass@<your-pg-host>:5432/flighttracker \
  ghcr.io/mover5/flight-tracker:latest
```

Point `DATABASE_URL` at your existing Postgres. Create an empty database
(e.g. `flighttracker`) first; the app creates its own tables and seeds them.

## Moving into the UnraidContainers repo

This repo is laid out to drop straight into `containers/flight-tracker/`:

1. Copy the repo contents into `containers/flight-tracker/` in
   [UnraidContainers](https://github.com/mover5/UnraidContainers) (it already
   includes `Dockerfile`, `VERSION`, `unraid-template.xml`, `icon.png`, and
   `.dockerignore` matching that repo's conventions — the build context is the
   container directory, and the Dockerfile is self-contained).
2. Add the build workflow: `./add-container.sh flight-tracker` (or copy an
   existing `build-<name>.yml` and swap the name). It triggers on changes under
   `containers/flight-tracker/` and publishes to `ghcr.io/mover5/flight-tracker`.
3. Commit and push — CI builds the image and `sync-templates.yml` copies the
   Unraid template automatically.

## Offline support

The app is **local-first** and installable as a PWA, so it keeps working with
no connectivity — exactly what you need when tagging gate push / takeoff / land
mid-flight without WiFi:

- A **service worker** precaches the app shell, so it loads even with no
  network (add it to your home screen for a full-screen, app-like launch).
- Every read and write hits a **local cache** first, so tagging and notes work
  instantly offline. An offline tag keeps the time it actually happened.
- Each change is queued in an **outbox** and replayed to the server
  automatically when you're back online (on reconnect, on next launch, and on a
  retry timer). The header badge shows the live state: **Synced**, **N to
  sync**, **Syncing…**, or **Offline · N queued**.

Recommended flow: open the app while you have signal (it pulls the latest
data), then tag away in airplane mode. It all syncs back when you land.

## Updating the seed data

The original sheet lives in [`scripts/source-data.md`](scripts/source-data.md).
Re-parse it into JSON with:

```bash
npm run parse
```

Flight ids are preserved across runs so they stay stable. The icon is generated
with `node scripts/make-icon.mjs`.
