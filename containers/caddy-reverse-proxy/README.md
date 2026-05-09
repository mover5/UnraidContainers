# caddy-reverse-proxy

[![Build](https://github.com/mover5/UnraidContainers/actions/workflows/build-caddy-reverse-proxy.yml/badge.svg)](https://github.com/mover5/UnraidContainers/actions/workflows/build-caddy-reverse-proxy.yml)
[![Version](https://ghcr-badge.egpl.dev/mover5/caddy-reverse-proxy/latest_tag?ignore=latest,sha-*&trim=major&label=version)](https://github.com/mover5/UnraidContainers/pkgs/container/caddy-reverse-proxy)

Caddy reverse proxy with automatic HTTPS via the Cloudflare DNS-01 challenge,
plus a bundled web UI for managing routes, viewing certificate status, and
tailing logs — all without restarting the container.

Designed for Unraid hosts behind Tailscale or NAT, where the standard
HTTP-01 ACME challenge can't reach the server.

## What it does

- **Reverse proxy** — maps subdomains (`grafana.yourdomain.com`) to internal
  services (`192.168.1.100:3000`).
- **Automatic SSL** — Caddy obtains and renews Let's Encrypt certs via
  Cloudflare DNS-01. No port 80 from the public internet required, so this
  works behind Tailscale, a NAT firewall, or anything that can't accept
  inbound HTTP-01 traffic.
- **Live config** — add, edit, enable/disable, or delete routes from the UI.
  Each save runs `caddy validate` and `caddy reload`. No restart, no
  dropped connections.
- **Cert visibility** — see expiry, issuer, and a color-coded status
  (ok / warning < 30d / expired / not yet issued) for every domain Caddy
  manages.
- **Manual mode** — if you'd rather hand-edit the Caddyfile, you can. The
  UI detects an unmanaged file and stays out of the way.

## Architecture

```
[container]
 ├─ caddy             ports 80, 443    (admin API on 127.0.0.1:2019)
 └─ flask admin UI    port 9999
        │ writes
        ▼
   /etc/caddy/routes.json     ← source of truth (managed by the UI)
        │ rendered
        ▼
   /etc/caddy/Caddyfile       ← regenerated on every change → caddy reload
```

Caddy and Flask run side-by-side under supervisord. The UI never edits
Caddy's runtime state directly — it writes `routes.json`, renders a fresh
Caddyfile, validates it, then asks Caddy to hot-reload.

## Quick start (Unraid)

1. **Set up Cloudflare DNS and an API token.** This is the part most people
   trip on. Follow [SETUP-GUIDE.md](./SETUP-GUIDE.md) once — moving DNS to
   Cloudflare, adding the wildcard A record, creating a scoped API token.
2. **Install the container** from this repo's template (`caddy-reverse-proxy`
   shows up in Docker → Add Container if you've added the repo as a template
   source). Or pull manually from `ghcr.io/mover5/caddy-reverse-proxy:latest`.
3. **Set `CF_API_TOKEN`** in the container config to the token from step 1.
4. **Start the container.** The default Caddyfile will be created on first
   run.
5. **Open the admin UI** at `http://<unraid-ip>:9999` and start adding
   routes. Each save reloads Caddy live.

The full walkthrough — including DNS records, Cloudflare proxy settings,
and what IP to use for upstreams — is in [SETUP-GUIDE.md](./SETUP-GUIDE.md).

## Web UI

| Tab | What it does |
|---|---|
| **Routes** | Add, edit, toggle, or delete subdomain → upstream mappings. Live upstream reachability check (TCP connect with 2s timeout) shows ✓/✕ as you type. Validation runs server-side before saving; bad config is rejected with an inline error and the previous state is preserved. |
| **Certificates** | One row per domain Caddy holds a cert for, plus any enabled route that doesn't have one yet. Shows issuer, not-after, days remaining, and a status pill (ok, warning, expired, missing). |
| **Settings** | Global ACME email and DNS provider. Only Cloudflare is bundled in the image — other providers need a rebuilt image with the matching `caddy-dns/<provider>` plugin. |
| **Caddyfile** | Read-only preview of the file Caddy is currently running. |
| **Logs** | Tail of `/var/log/caddy/caddy.log` (50, 200, or 1000 lines). |
| **Reload** (top right) | Manual validate-and-reload trigger. Useful after changing the upstream service, not the route. |

### Importing an existing Caddyfile

If you upgrade from an earlier version (or you set up routes by hand
before opening the UI), the Routes tab shows a one-time import banner.
It pulls simple `host { reverse_proxy ip:port }` blocks into the UI;
anything more complex is left untouched and you can re-add it via the
form's "extra directives" field.

Dismissing the banner keeps the UI in **manual mode** — it shows config
read-only and never overwrites the Caddyfile.

## Local development

The UI runs entirely on your host machine in **mock mode** — no Docker,
no Caddy, no Cloudflare credentials, no real domain.

```bash
./start_debug_server.sh
# → http://localhost:9998
```

The script creates a venv on first run, installs requirements, and starts
Flask with `CADDY_BACKEND=mock` and `FLASK_DEBUG=1`. Defaults to port 9998
so it doesn't collide with the real container on 9999; override with
`FLASK_PORT=…`. Hot-reload is on:

| Change | Reload |
|---|---|
| `.py` file | server restarts; refresh browser |
| Jinja template | next request picks it up |
| CSS / JS | next request, but **hard-refresh** (`Cmd-Shift-R` / `Ctrl-Shift-R`) to bypass browser cache |
| `fixtures/mock_data.json` | click **Reset mocks** in the top bar |

The mock backend ships with 6 routes and 5 cert states (ok, warning,
expired, missing, fixture). To deliberately trigger error paths:

| Input | Result |
|---|---|
| upstream port `9999` | reachability check fails (red ✕) |
| upstream host containing `down` or `fail` | reachability check fails |
| upstream `192.168.1.50:abc` | save fails inline ("non-numeric port") |
| upstream `192.168.1.50` (no port) | save fails inline ("missing port") |
| subdomain `nodot` | save fails inline ("must contain a dot") |

For more on the backend split (Mock vs Real, fixtures, error paths), see
[`web/README.md`](./web/README.md).

To exercise the production image with the mock backend (verifies the
container build works end-to-end without touching Caddy):

```bash
docker compose -f docker-compose.dev.yml up --build
```

## Configuration

### Ports

| Port | Purpose |
|---|---|
| 80 | HTTP — Caddy redirects to HTTPS |
| 443 | HTTPS — terminates TLS, proxies to upstreams |
| 9999 | Admin web UI |

### Environment variables

| Name | Required | Default | Purpose |
|---|---|---|---|
| `CF_API_TOKEN` | yes | — | Cloudflare API token with `Zone:DNS:Edit` for the zone(s) you're issuing certs for. Used by Caddy for the DNS-01 challenge. |

### Volumes

| Mount | Default (Unraid) | Purpose |
|---|---|---|
| `/etc/caddy` | `/mnt/user/appdata/caddy-reverse-proxy/config` | Caddyfile + `routes.json` (managed by the UI) |
| `/data` | `/mnt/user/appdata/caddy-reverse-proxy/data` | Caddy's persistent state — issued certs, ACME account keys |
| `/var/log/caddy` | `/mnt/user/appdata/caddy-reverse-proxy/logs` | Log file tailed by the UI's Logs tab. Optional. |

`/data` is the important one — losing it means losing your issued certs
and Caddy will need to re-acquire them from Let's Encrypt (which is
rate-limited, so back this up if you have many domains).

## Troubleshooting

**UI shows but reloads fail with "validation failed."**
Click into the Caddyfile tab and look at the rendered output. The error
detail in the flash message is verbatim from `caddy validate` — usually
a missing/extra directive or a typo in the upstream.

**Cert status is "missing" for an enabled route.**
Caddy issues certs lazily, on the first matching request. Hit the URL
once (`curl -k https://<subdomain>`) and the cert should appear within
30–90 seconds. Watch the Logs tab while it happens.

**Cert status is "expired."**
Caddy auto-renews 30 days before expiry. If a cert has gone past its
expiry, something is broken — check the Logs tab for ACME errors.
Common causes: `CF_API_TOKEN` got rotated, Cloudflare zone was moved,
or the network can't reach `acme-v02.api.letsencrypt.org`.

**Permission denied / unauthorized in logs.**
The `CF_API_TOKEN` is missing or doesn't have DNS edit permissions for
the right zone. Verify in Cloudflare → My Profile → API Tokens.

**The Logs tab says "no logs available yet."**
Caddy hasn't written to the log file yet. The default Caddyfile
configures `output file /var/log/caddy/caddy.log` — if you've replaced
the global block via the UI's Settings tab and removed the `log`
directive, that's why. Reload should restore it. (The container also
streams to stdout, so `docker logs caddy-reverse-proxy` always works.)

## See also

- [SETUP-GUIDE.md](./SETUP-GUIDE.md) — full Cloudflare DNS setup walkthrough
- [web/README.md](./web/README.md) — admin UI architecture, mock backend, fixture format
