# ip-directory

Names every IP seen on the network. Scans the sFlow samples telegraf writes to InfluxDB, resolves each IP to a
name from several sources, writes the names back to InfluxDB (`ip_labels`) for the Grafana "LAN Traffic (sFlow)"
dashboard, and serves a Flask web UI on port 9595 to browse and edit them. No login — LAN/Tailscale only.

Design doc: `Designs/network/ip-directory-plan.md` (outside this repo).

## Development

```bash
cd containers/ip-directory
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q

# Run against the real InfluxDB (other sources optional)
INFLUX_TOKEN=<token> CONFIG_PATH=./config python run.py
```

UI at `http://localhost:9595`. The tests fake InfluxDB, so they run anywhere.

## Architecture

```
run.py → app/main.py (Flask routes, waitress server)
           ├→ config.py        env vars
           ├→ db.py            SQLite at {CONFIG_PATH}/ip-directory.db; seeds known MACs/IPs and owner rules once
           ├→ influx.py        Flux: scan sFlow, per-IP traffic/peers/ports, write ip_labels
           ├→ resolver.py      pure: one name per IP from all sources (unit-tested)
           ├→ refresher.py     APScheduler job every REFRESH_MINUTES
           │     maxmind → vendors → sFlow scan → tautulli → adguard → reverse DNS → resolve all → write changed labels
           └→ sources/         tautulli.py, adguard.py, geoip.py (MaxMind), vendor.py (Wireshark manuf), rdns.py
```

**Frontend:** server-rendered Jinja pages + one small vanilla JS file for the IP detail page's live charts. No build step.

## Naming priority

manual IP → manual MAC (LAN only) → manual range (most specific CIDR) → Tautulli → AdGuard (by IP, then MAC) →
automatic: multicast/broadcast names · randomized MAC = "Unknown phone (xx:xx)" · `<vendor> device (xx:xx)` ·
"Unknown LAN device" · public = `<owner> · <city, region>` (owner rename rules applied) · "Unknown".

Names from `auto`, `vendor`, `geoip`, `rdns` are "automatic" and feed the Inbox until reviewed or named.

## Key decisions

- **Runs on `lcarsnet`** and reaches InfluxDB/Tautulli by container name, so their (dynamic) container IPs don't matter.

- **LAN devices are named by MAC.** An IP's MAC is the dominant `in_src_mac` among samples where it is the *source*
  over the last 7 days (`ip_mac_daily`). Majority vote matters: the switch emits stray one-off samples with the
  wrong MAC.
- **Randomized MAC** = locally-administered bit set, excluding Docker's `02:42:*`.
- **Label writes are minimal:** a label is written when its hash changes, or once a day while the IP is still being
  seen. Grafana looks back 31 days with `last()`. `ip_labels` is tagged by `ip`, so series count = distinct IPs.
- **Scan bookkeeping** (`kv.scan_until`) commits in the same transaction as the counts — a crash can't double-count.
- **SQLite:** one connection per thread, WAL, `synchronous=NORMAL`. Opening/closing per call made every commit
  cost ~250 ms on the array.
- **Manual edits** update SQLite immediately (`Refresher.apply_edits`) and push to InfluxDB in a background thread.
- **MaxMind:** databases re-downloaded every 3 days and replaced in place (GeoLite2 EULA: use current data,
  delete old copies).
- **sFlow quirks** (see the KB): `src`/`dst` are fields, so queries `pivot()` first; bytes = `l2_bytes × sampling_interval`.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `INFLUX_URL` | `http://InfluxDB:8086` | InfluxDB v2 — container name + internal port (container runs on `lcarsnet`) |
| `INFLUX_TOKEN` | — | Read + write on the bucket (required) |
| `INFLUX_ORG` / `INFLUX_BUCKET` | `LCARS` / `unraid` | |
| `NETFLOW_MEASUREMENT` / `LABELS_MEASUREMENT` | `netflow` / `ip_labels` | |
| `TAUTULLI_URL` / `TAUTULLI_API_KEY` | — | Optional |
| `ADGUARD_URL` / `ADGUARD_USER` / `ADGUARD_PASSWORD` | — | Optional. A `br0` (macvlan) AdGuard is unreachable from `lcarsnet` even with "Host access to custom networks"; attach AdGuard to `lcarsnet` as a second network |
| `MAXMIND_ACCOUNT_ID` / `MAXMIND_LICENSE_KEY` | — | Optional |
| `REFRESH_MINUTES` | `15` | |
| `INITIAL_SCAN_DAYS` | `7` | How far back the first scan reaches |
| `LAN_CIDRS` | `192.168.0.0/16,10.0.0.0/8,172.16.0.0/12` | Named by MAC |
| `ALLOWED_HOSTS` | — | Hostnames the UI may be opened by; IPs and localhost always work (blocks DNS rebinding) |
| `PORT` | `9595` | |
| `CONFIG_PATH` | `/config` | SQLite, GeoLite2 files, manuf list |
