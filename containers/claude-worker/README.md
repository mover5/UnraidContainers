# Claude Worker

Docker container that serves as a full development workstation with Claude Code, running on Unraid. Access via SSH + tmux from any machine on your network.

## What's Inside

- **Claude Code** — AI coding assistant (native installer)
- **Node.js 22 LTS** + npm
- **.NET SDK 8** (LTS)
- **Python 3** + pip + venv
- **GitHub CLI** (`gh`) — clone repos, create PRs, manage issues
- **Azure CLI** (`az`) — Azure Storage and services
- **MySQL client**
- **Playwright + Chromium** — headless browser for testing/screenshots
- **tmux** — terminal multiplexer for persistent sessions
- **SSH server** on port 2222
- **Build tools** — gcc, make, etc.

## Quick Start (Unraid)

### Option 1: Unraid Template

1. In Unraid, go to **Docker → Add Container → Template**
2. Import the XML template URL: `https://raw.githubusercontent.com/mover5/UnraidClaudeWorker/main/unraid-template.xml`
3. Fill in your git name/email and optional SSH password
4. Click **Apply**

### Option 2: Manual Docker Run

```bash
docker run -d \
  --name claude-worker \
  --net=host \
  -e PUID=1000 \
  -e PGID=1000 \
  -e GIT_USER_NAME="Your Name" \
  -e GIT_USER_EMAIL="you@example.com" \
  -e SSH_PASSWORD="your-password" \
  -e TZ="America/New_York" \
  -v /mnt/user/appdata/claude-worker/home:/home/claude \
  -v /mnt/user/appdata/claude-worker/repos:/repos \
  ghcr.io/mover5/unraidclaudeworker:latest
```

## Connecting (from Windows 11)

No WSL needed — just Windows Terminal + SSH.

```bash
ssh claude@<unraid-ip> -p 2222
```

**Recommended:** Add to your SSH config (`C:\Users\<you>\.ssh\config`):

```
Host claude-dev
    HostName <unraid-ip>
    Port 2222
    User claude
```

Then connect with: `ssh claude-dev`

## Daily Workflow

```bash
# Connect
ssh claude-dev

# First time: create a tmux session
tmux new -s work

# Subsequent times: reattach
tmux a

# Inside tmux — common shortcuts:
# Ctrl+B, c        → new window (tab)
# Ctrl+B, 1/2/3    → switch windows
# Ctrl+B, |        → split pane vertically
# Ctrl+B, -        → split pane horizontally
# Ctrl+B, d        → detach (leave running)
```

### Typical Layout

- **Window 1**: Claude session in repo A — `cd /repos/my-api && claude`
- **Window 2**: Dev server — `cd /repos/my-frontend && npm run dev -- --host`
- **Window 3**: Claude session in repo B — `cd /repos/my-other-project && claude`

Everything keeps running when you disconnect. `tmux a` to come back.

## GitHub Setup

Run once after first start:

```bash
ssh claude-dev
gh auth login
```

Follow the interactive prompts. Your token persists in the home volume — survives restarts and image upgrades.

Clone repos:

```bash
cd /repos
gh repo clone owner/repo-name
```

## Dev Servers on LAN

Since the container uses `--net=host`, any dev server is reachable from your network. The only thing to remember: **bind to `0.0.0.0`**, not `localhost`.

| Framework | Command |
|---|---|
| Vite | `npm run dev -- --host` |
| Next.js | `next dev -H 0.0.0.0` |
| .NET | `dotnet run --urls http://0.0.0.0:5000` |
| Generic | Check framework docs for host/bind option |

Then visit `http://<unraid-ip>:<port>` from any machine on your network.

## Playwright Screenshots

Claude can take screenshots of your dev servers for visual verification:

```bash
# Inside a Claude session, Claude can run:
npx playwright screenshot --url http://localhost:3000 screenshot.png
```

Chromium is pre-installed. No setup needed.

## Persistent Software Installs

Software installed via `apt` is lost on image upgrade. To make installs permanent:

### Method 1: Startup Packages (apt)

```bash
# Add package names to this file (one per line)
echo "redis-tools" >> ~/.startup-packages
echo "postgresql-client" >> ~/.startup-packages
```

These get installed automatically on every container start.

### Method 2: Startup Script (anything)

```bash
# Create a startup script for non-apt installs
cat > ~/.startup-script.sh << 'EOF'
#!/bin/bash
pip3 install httpie
cargo install ripgrep
EOF
chmod +x ~/.startup-script.sh
```

### Method 3: Manual Binaries

Place binaries in `~/.local/bin/` — it's on PATH and persists in the home volume.

## SSH Key Setup

SSH key auth is the default (and recommended) way to connect. No passwords needed.

### Step 1: Generate a key pair (if you don't have one)

**Windows** (PowerShell or Windows Terminal):
```powershell
ssh-keygen -t ed25519
```

Press Enter to accept the default location (`C:\Users\<you>\.ssh\id_ed25519`). Optionally set a passphrase.

**macOS / Linux**:
```bash
ssh-keygen -t ed25519
```

This creates two files:
- `id_ed25519` — your **private** key (never share this)
- `id_ed25519.pub` — your **public** key (this goes on the container)

### Step 2: Add your public key to the container

**Option A — Via Unraid file manager or SMB share:**

1. Navigate to your Unraid share: `\\<unraid-ip>\appdata\claude-worker\home\.ssh\` (or the path you configured for `/home/claude`)
2. Open or create the file `authorized_keys` (no extension)
3. Paste the contents of your `id_ed25519.pub` file into it (one key per line)
4. Save the file

> **Important:** `authorized_keys` must be a **file**, not a folder. Each key goes on its own line.

**Option B — From the command line (requires password auth or Unraid terminal):**

Windows:
```powershell
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh claude@<unraid-ip> -p 2222 "cat >> ~/.ssh/authorized_keys"
```

macOS / Linux:
```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub -p 2222 claude@<unraid-ip>
```

### Step 3: Connect

```bash
ssh claude@<unraid-ip> -p 2222
```

### Adding keys from multiple machines

Each machine needs its own key pair. Repeat steps 1-2 for each machine, adding each public key on a new line in `authorized_keys`. For example:

```
ssh-ed25519 AAAA...key1... user@desktop
ssh-ed25519 AAAA...key2... user@laptop
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PUID` | `1000` | User ID for file permissions |
| `PGID` | `1000` | Group ID for file permissions |
| `GIT_USER_NAME` | *(none)* | Name for git commits |
| `GIT_USER_EMAIL` | *(none)* | Email for git commits |
| `SSH_PASSWORD` | *(none)* | Set to enable SSH password auth |
| `TZ` | *(none)* | Timezone (e.g., `America/New_York`) |

## Volumes

| Container Path | Purpose |
|---|---|
| `/home/claude` | Config: Claude auth, SSH keys, git config, tmux, gh token, startup scripts |
| `/repos` | Source code repositories |
