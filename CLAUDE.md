# CLAUDE.md

## What this repo is

Monorepo for all of mover5's Unraid Docker containers. Each container lives in its own subdirectory under `containers/` and is independently built and published to GitHub Container Registry (ghcr.io).

## Repo structure

```
containers/<name>/           # Each container gets its own directory
  Dockerfile                 # Required — the container build
  VERSION                    # Required — contains major.minor (e.g. "1.0"), patch auto-calculated
  entrypoint.sh              # Optional
  config/                    # Optional — supporting config files
  unraid-template.xml        # Optional — Unraid Community Apps template
  icon.png                   # Optional — icon for Unraid template

.github/workflows/
  build-container.yml        # Reusable workflow — all containers call this
  build-<name>.yml           # Per-container workflow — triggers on changes to that container's dir
  build-all.yml              # Manual trigger to rebuild every container
  cleanup-images.yml         # Weekly cleanup of old GHCR image versions
  sync-templates.yml         # Auto-syncs unraid-template.xml to templates/ on push

templates/                   # Flat directory of Unraid XML templates (auto-generated, do not edit directly)

add-container.sh             # Scaffolding script to create a new container + workflow
```

## How builds work

- Each container has a per-container workflow (e.g. `build-claude-worker.yml`) that triggers on pushes to `main` that touch files under `containers/<name>/`.
- These all call the reusable `build-container.yml` workflow, which handles login, build, tag, and push to `ghcr.io/mover5/<name>`.
- PRs build but do not push (validation only).
- `build-all.yml` can be triggered manually from the Actions tab to rebuild everything.

## Versioning (SemVer)

Each container has a `VERSION` file with `major.minor`. The patch number is auto-calculated by counting commits that touched the container's directory since `VERSION` was last changed.

- To bump patch: just push changes (automatic).
- To bump minor: edit `VERSION` (e.g. `1.0` → `1.1`), patch resets to 0.
- To bump major: edit `VERSION` (e.g. `1.1` → `2.0`), patch resets to 0.

Images are tagged with: the semver, `latest` (on main), and the commit SHA.

## Adding a new container

Run `./add-container.sh <name>`. This creates:
- `containers/<name>/Dockerfile`
- `containers/<name>/VERSION` (set to `0.1`)
- `.github/workflows/build-<name>.yml`

Then edit the Dockerfile, commit, and push.

## GHCR storage management

A `cleanup-images.yml` workflow runs weekly (Sunday 3am UTC) and on manual trigger. It prunes old image versions to prevent storage from ballooning:
- Keeps 10 most recent untagged versions, deletes the rest.
- Keeps 20 most recent tagged versions total, deletes the rest.

Docker layer caching uses GitHub Actions Cache (`type=gha`), which is capped at 10GB per repo and self-manages via LRU eviction. No intermediate artifacts are used — images go straight to GHCR.

## Unraid template registration

This repo is added as a Template Repository in Unraid's Docker settings. Unraid scans the `templates/` directory for XML files. A `sync-templates.yml` workflow auto-copies each container's `unraid-template.xml` into `templates/<name>.xml` whenever a template changes on `main`. Do not edit files in `templates/` directly — edit the source in `containers/<name>/unraid-template.xml`.

## Important conventions

- Image names match the container directory name: `containers/foo/` → `ghcr.io/mover5/foo`.
- Every container must have a `Dockerfile` and a `VERSION` file.
- The `build-container.yml` reusable workflow requires `fetch-depth: 0` (full git history) to calculate the patch version.
- `unraid-template.xml` files should reference `ghcr.io/mover5/<name>` as the repository and point support/icon URLs to this repo (UnraidContainers), not individual repos.

## Containers

### claude-worker
Dev environment container with Claude Code, Node.js 22, .NET 9, Python 3, GitHub CLI, Azure CLI, and Playwright. Access via SSH on port 2222 + tmux. Originally migrated from the standalone `UnraidClaudeWorker` repo. Supports PUID/PGID remapping, persistent home/repos volumes, and optional SSH password auth.

### cleanrr
Python-based torrent lifecycle manager for Deluge with a Flask web dashboard (port 9494). Connects to the Deluge Web API, tracks torrents in an SQLite database, and auto-removes them after a configurable seed duration (default 14 days). Features torrent protection, manual removal, countdown timers, and configurable check intervals. Originally migrated from the standalone `Cleanrr` repo.

### database-backup
Python-based scheduled database backup tool with a Flask web dashboard (port 8008). Supports MySQL and Azure SQL as backup sources, with Azure Blob/File Share storage. Includes a scheduler that runs backups on cron schedules, state tracking, and a web UI for managing backup sources. Originally migrated from the standalone `UnraidDatabaseBackup` repo. Has a test suite under `tests/`.

### azurite-azure-storage
Local Azure Storage emulator powered by Azurite with a built-in web UI (sebagomez/azurestorageexplorer). Exposes Blob (10000), Queue (10001), and Table (10002) storage APIs plus a Storage Explorer web dashboard (8080) for browsing blobs, queues, tables, and file shares. Uses supervisord to run both Azurite (Node.js) and the explorer (.NET Blazor) in a single container. Data persists in `/data`.

### caddy-reverse-proxy
Caddy reverse proxy with the Cloudflare DNS plugin for automatic SSL certificate provisioning via DNS-01 challenges. Ideal for servers behind Tailscale or NAT where HTTP-01 challenges cannot reach the server. Routes subdomains to Docker containers with auto-managed SSL certificates. Bundles a Flask admin UI (port 9999) for adding/editing routes, viewing certificate status/expiry, previewing the rendered Caddyfile, and tailing logs — all live-reloaded without restarting the container. Caddy + Flask are run together via supervisord. The UI has a `MockBackend` for local iteration without Docker (`./start_debug_server.sh`); see `containers/caddy-reverse-proxy/web/README.md`. Exposes ports 80, 443, and 9999. Requires a Cloudflare API token with Zone:DNS:Edit permission.

### flight-tracker
Mobile-first flight log with a web dashboard (port 8080). A single container running an Express API that serves a built React/Vite SPA from `./public`. Tap to stamp in-flight event times (gate push / takeoff / land / gate arrive) — works offline and syncs when back online — log timestamped notes, and visualize derived metrics (taxi-out, taxi-in, air time, block time, departure/arrival delays). Persists to an **external** Postgres via `DATABASE_URL` (no bundled DB; the included `docker-compose.yml` spins up a throwaway Postgres for local testing only). Seeds an initial set of flights on first run if the DB is empty (`SEED_ON_EMPTY`). Multi-stage Dockerfile: stage 1 builds the frontend with `VITE_API_URL=/api` baked in, stage 2 installs server deps only. Originally migrated from the standalone `Flight-Tracker` repo.
