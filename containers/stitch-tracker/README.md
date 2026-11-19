# Stitch Tracker

A mobile-first knitting tracker. Add a project, paste in the pattern, and tap
**Row done** as you knit — it tracks where you are, shows the instruction for
the current row, and tells you when to change colors.

## Features

- **Projects** with a name, description, and free-form notes/instructions
  (cast on, stitch, gauge…).
- **Yarn colors** — a palette per project. Common color words (purple, camel,
  mustard, rust, heather grey…) get a sensible swatch automatically; tap a
  swatch to fine-tune it.
- **Patterns as steps** — each step is a run of rows with an optional color and
  instruction. Edit, reorder, duplicate, or delete steps.
- **Paste import** — paste a pattern from your notes app and it's parsed into
  steps and colors. Understands `8 Purple`, `12 rows in Rust`, `Purple: 8`,
  `12 Rust - slip first st`, `Row 5: k2, p2`, `Rows 6-9: knit`. Lines it can't
  read (title, "Cast on 60") are listed and can be copied into the name/notes
  in one tap.
- **Knitting view** — big thumb-sized **Row done** button tinted with the
  current yarn, undo, "last Purple row — Camel is next" and "switch to Camel"
  alerts, a stripe bar of the whole pattern, and a step list you can tap to
  jump to. Optional keep-screen-on (needs HTTPS).
- **Plain row counter** for projects without a pattern.
- **Offline-first** — every edit and row tap is saved on the device
  (localStorage) and synced to the server when it's reachable: on load, when
  the browser comes back online, when you reopen the app, and every 30s while
  anything is pending. Installable as a PWA so the app itself loads offline.

## How sync works

Each project is a JSON document. Every field (name, notes, colors, steps,
rows done, status, deleted) carries its own last-modified timestamp, and the
server and client both merge **per field, newest wins**. So counting rows on
your phone offline won't clobber a notes edit made on your laptop, and vice
versa. Deletes are tombstones so they propagate too. There's no login — like
the other containers here, it assumes trusted LAN/Tailscale access.

> **Offline app shell needs HTTPS.** Browsers only run service workers on
> HTTPS (or localhost). Serve it through Caddy (e.g. `stitches.<domain>`) so the
> app opens with no connection. Over plain HTTP your data still saves locally,
> but the page itself needs the server to load.

## Run

| Env | Default | Purpose |
|---|---|---|
| `PORT` | `8080` | HTTP port |
| `DB_PATH` | `/data/stitch.db` | SQLite database file |

Map `/data` to `/mnt/user/appdata/stitch-tracker` on Unraid.

```bash
docker compose up --build        # http://localhost:8080
```

## Develop

```bash
npm install && (cd server && npm install)
npm test                         # parser/pattern/merge + server API tests
(cd server && DB_PATH=./data/dev.db PUBLIC_DIR=../dist npm start)   # API on :8080
VITE_API_URL=/api npm run dev    # UI with /api proxied to :8080
npm run dev                      # UI only, local-only mode (no server)
node scripts/make-icons.cjs      # re-render PNG icons from public/favicon.svg
```

Layout: `src/lib/` holds the data model (`types.ts`), pattern math
(`pattern.ts`), paste parser (`parse.ts`), local store (`store.ts`), and sync
engine (`sync.ts`). `server/project.js` mirrors the merge rule from
`src/lib/merge.ts` — change both together.
