# claude-worker

Dev environment container with Claude Code, Node.js 22, .NET 9, Python 3, GitHub CLI, Azure CLI, and Playwright. Accessed via SSH on port 2222 with tmux for session management.

## Architecture

**Base image:** Ubuntu 24.04

**Installed toolchain:** Claude Code (native installer), Node.js 22, .NET SDK 9, Python 3 + pip/venv, GitHub CLI, Azure CLI, Playwright (chromium), MySQL client, build-essential, standard utilities (curl, wget, jq, vim, nano, etc.)

**User:** `claude` (UID/GID 1000, remappable via PUID/PGID)

**Volumes:**
- `/home/claude` — config persistence (Claude auth, SSH keys, git config, startup scripts, npm packages)
- `/repos` — source code repositories

## Startup Flow (entrypoint.sh)

1. **UID/GID remapping** — applies PUID/PGID env vars
2. **SSH host keys** — generates and persists in `/home/claude/.ssh-host-keys` (stable fingerprints across restarts)
3. **Git config** — applies GIT_USER_NAME/GIT_USER_EMAIL if set
4. **Startup packages** — installs APT packages listed in `~/.startup-packages` (cached in `~/.apt-cache`)
5. **Startup script** — runs `~/.startup-script.sh` if present and executable
6. **Idle** — `tail -f /dev/null` as PID 1, waits for SSH connections

## Key Design Decisions

- **SSH password auth is off by default.** Set `SSH_PASSWORD` env var to enable it. Public key auth is always available.
- **Claude Code binary is copied to /usr/local/bin** so it persists even when `/home/claude` is a fresh volume mount.
- **Playwright browsers path** is set to `~/.cache/ms-playwright` (user-writable, no sudo needed).
- **PATH is set in three places** to cover all shell contexts: Docker ENV (entrypoint processes), `/etc/profile.d/claude-path.sh` (SSH login shells), and `~/.bashrc` append (tmux sessions).

## Config Files

- `config/sshd_config` — SSH server config (port 2222, no root login, no X11, sftp enabled)
- `config/tmux.conf` — 256-color, mouse support, 50k scrollback, base index 1, `|`/`-` for splits

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| PUID | 1000 | User ID for file permissions |
| PGID | 1000 | Group ID for file permissions |
| GIT_USER_NAME | (empty) | Git commit author name |
| GIT_USER_EMAIL | (empty) | Git commit author email |
| SSH_PASSWORD | (empty) | Set to enable SSH password auth |
| TZ | America/New_York | Container timezone |
