# caddy-reverse-proxy admin UI

Flask sidecar that runs alongside Caddy in the container and provides a web UI
on port **9999** for managing routes, viewing certificate status, previewing
the rendered Caddyfile, and tailing logs.

## Architecture

```
[container]
 ├─ caddy            ports 80, 443 (admin API on 127.0.0.1:2019)
 └─ flask (this)     port 9999
       │
       ▼
   /etc/caddy/routes.json    ← source of truth
       │
       ▼ rendered
   /etc/caddy/Caddyfile      ← regenerated on every change, then `caddy reload`
```

The Flask app never edits Caddy state directly. Everything goes through a
`Backend` (see `backend.py`):

- **`backend_real.py`** — production. Reads/writes `routes.json`, runs
  `caddy validate` / `caddy reload`, parses certs from `/data/caddy/certificates`,
  tails `/var/log/caddy/caddy.log`.
- **`backend_mock.py`** — in-memory, seeded from `fixtures/mock_data.json`.
  Used for local dev so the UI can be exercised end-to-end without Caddy,
  a real domain, or Cloudflare credentials.

Selected at startup via `CADDY_BACKEND=real|mock`.

## Local development (no Docker)

```bash
./start_debug_server.sh
# → http://localhost:9999
```

The script (in the container directory, one level up from `web/`) creates a
venv on first run, installs requirements, and starts Flask with
`CADDY_BACKEND=mock FLASK_DEBUG=1`. Re-runs are instant — it only reinstalls
when `requirements.txt` changes.

Hot-reload is on:
- `.py` change → server restarts (refresh browser)
- template change → next request picks it up
- CSS change → next request picks it up; hard-refresh the browser to bypass
  its cache

The mock backend ships with:
- 6 routes (varied: IP upstream, hostname upstream, disabled, with extras)
- 5 cert states (ok, warning, expired, missing for an enabled route)
- ~15 lines of canned log output

A **"Reset mocks"** button is shown in the top bar in mock mode. It re-seeds
state from `fixtures/mock_data.json`, so you can break things by clicking
around and snap back.

## Local development (Docker, mock mode)

```bash
docker compose -f docker-compose.dev.yml up --build
# → http://localhost:9999
```

Builds the real production image but runs only the Flask UI with
`CADDY_BACKEND=mock`, so the container build is exercised without touching
real Caddy or real certs.

## Forcing the error path

The mock backend's `validate()` deliberately rejects:
- upstreams missing a port (`192.168.1.100`)
- non-numeric ports (`192.168.1.100:abc`)
- ports out of range (`192.168.1.100:99999`)
- subdomains without a dot (`grafana`)

Submit any of these in the New Route form to see the inline error display.

## File layout

```
web/
├── app.py                  # Flask routes
├── backend.py              # factory + Protocol
├── backend_mock.py         # in-memory dev backend
├── backend_real.py         # talks to Caddy + filesystem
├── caddyfile_render.py     # routes.json → Caddyfile string
├── caddyfile_parser.py     # legacy Caddyfile → routes (for import on upgrade)
├── models.py               # dataclasses (Route, GlobalSettings, CertInfo, ReloadResult)
├── requirements.txt
├── fixtures/
│   └── mock_data.json
├── templates/              # Jinja templates
└── static/
    └── style.css
```
