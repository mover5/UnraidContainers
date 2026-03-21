#!/bin/bash
set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}

echo "──────────────────────────────────────────"
echo "  Claude Worker starting..."
echo "  PUID=${PUID}  PGID=${PGID}"
echo "──────────────────────────────────────────"

# ── PUID/PGID remapping ──────────────────────────────────────────────
if [ "$(id -g claude)" != "$PGID" ]; then
    groupmod -g "$PGID" claude
fi
if [ "$(id -u claude)" != "$PUID" ]; then
    usermod -u "$PUID" claude
fi

# ── Fix ownership ────────────────────────────────────────────────────
chown claude:claude /home/claude /repos
# Only fix top-level dotfiles/dirs, not deep recursion (slow on large volumes)
chown claude:claude /home/claude/.* 2>/dev/null || true
chown -R claude:claude /home/claude/.ssh 2>/dev/null || true
chown -R claude:claude /home/claude/.claude 2>/dev/null || true
chown -R claude:claude /home/claude/.config 2>/dev/null || true
chown -R claude:claude /home/claude/.local 2>/dev/null || true

# ── Ensure essential dirs exist (volume mount may be empty) ───────────
su - claude -c "mkdir -p ~/.ssh ~/.claude ~/.config ~/.local/bin ~/.cache/ms-playwright"

# ── Git config ────────────────────────────────────────────────────────
if [ -n "$GIT_USER_NAME" ]; then
    su - claude -c "git config --global user.name '$GIT_USER_NAME'"
fi
if [ -n "$GIT_USER_EMAIL" ]; then
    su - claude -c "git config --global user.email '$GIT_USER_EMAIL'"
fi

# ── SSH host keys (persistent across image upgrades) ──────────────────
SSH_HOST_KEY_DIR="/home/claude/.ssh-host-keys"
mkdir -p "$SSH_HOST_KEY_DIR"

if [ ! -f "$SSH_HOST_KEY_DIR/ssh_host_rsa_key" ]; then
    echo "Generating SSH host keys (first run)..."
    ssh-keygen -t rsa -b 4096 -f "$SSH_HOST_KEY_DIR/ssh_host_rsa_key" -N ""
    ssh-keygen -t ed25519 -f "$SSH_HOST_KEY_DIR/ssh_host_ed25519_key" -N ""
fi
chown -R root:root "$SSH_HOST_KEY_DIR"
chmod 600 "$SSH_HOST_KEY_DIR"/*_key
chmod 644 "$SSH_HOST_KEY_DIR"/*.pub

# ── Unlock account for SSH key auth (locked accounts reject all auth) ─
usermod -p '*' claude

# ── SSH password auth (optional) ──────────────────────────────────────
if [ -n "$SSH_PASSWORD" ]; then
    echo "claude:$SSH_PASSWORD" | chpasswd
    sed -i 's/^PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config
    sed -i 's/^KbdInteractiveAuthentication no/KbdInteractiveAuthentication yes/' /etc/ssh/sshd_config
    echo "SSH password auth: ENABLED"
else
    echo "SSH password auth: disabled (set SSH_PASSWORD to enable, or use key auth)"
fi

# ── SSH directory permissions ─────────────────────────────────────────
chmod 700 /home/claude/.ssh
[ -f /home/claude/.ssh/authorized_keys ] && chmod 600 /home/claude/.ssh/authorized_keys

# ── Persistent software installs ─────────────────────────────────────
STARTUP_PACKAGES="/home/claude/.startup-packages"
APT_CACHE_DIR="/home/claude/.apt-cache"
APT_HASH_FILE="/home/claude/.apt-cache/.installed-hash"
if [ -f "$STARTUP_PACKAGES" ] && [ -s "$STARTUP_PACKAGES" ]; then
    CURRENT_HASH=$(sort "$STARTUP_PACKAGES" | md5sum | awk '{print $1}')
    PREVIOUS_HASH=""
    [ -f "$APT_HASH_FILE" ] && PREVIOUS_HASH=$(cat "$APT_HASH_FILE")

    # Check if all packages are already installed (dpkg query)
    ALL_INSTALLED=true
    while IFS= read -r pkg || [ -n "$pkg" ]; do
        pkg=$(echo "$pkg" | xargs)  # trim whitespace
        [ -z "$pkg" ] && continue
        [[ "$pkg" == \#* ]] && continue
        if ! dpkg -s "$pkg" >/dev/null 2>&1; then
            ALL_INSTALLED=false
            break
        fi
    done < "$STARTUP_PACKAGES"

    if [ "$ALL_INSTALLED" = true ]; then
        echo "All packages from ~/.startup-packages already installed, skipping."
    else
        echo "Installing packages from ~/.startup-packages..."
        mkdir -p "$APT_CACHE_DIR"
        # Use persistent cache to avoid re-downloading
        apt-get update
        apt-get install -y -o dir::cache::archives="$APT_CACHE_DIR" $(grep -v '^\s*#' "$STARTUP_PACKAGES" | xargs)
        rm -rf /var/lib/apt/lists/*
        echo "$CURRENT_HASH" > "$APT_HASH_FILE"
        echo "Package installation complete."
    fi
fi

STARTUP_SCRIPT="/home/claude/.startup-script.sh"
if [ -f "$STARTUP_SCRIPT" ] && [ -x "$STARTUP_SCRIPT" ]; then
    echo "Running ~/.startup-script.sh..."
    bash "$STARTUP_SCRIPT"
    echo "Startup script complete."
fi

# ── Persistent npm global prefix (survives restarts) ─────────────────
su - claude -c "mkdir -p ~/.npm-global && npm config set prefix ~/.npm-global"

# ── Ensure shell profile files exist (volume may lack skeleton files) ─
if [ ! -f /home/claude/.profile ]; then
    cp /etc/skel/.profile /home/claude/.profile 2>/dev/null || cat > /home/claude/.profile <<'PROF'
if [ -n "$BASH_VERSION" ]; then
    if [ -f "$HOME/.bashrc" ]; then
        . "$HOME/.bashrc"
    fi
fi
if [ -d "$HOME/.local/bin" ] ; then
    PATH="$HOME/.local/bin:$PATH"
fi
PROF
    chown claude:claude /home/claude/.profile
fi

# ── Ensure PATH and env vars in bashrc (for tmux) ──
if ! grep -q 'npm-global/bin' /home/claude/.bashrc 2>/dev/null; then
    echo 'export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$PATH"' >> /home/claude/.bashrc
    chown claude:claude /home/claude/.bashrc
fi
if ! grep -q 'PLAYWRIGHT_BROWSERS_PATH' /home/claude/.bashrc 2>/dev/null; then
    echo 'export PLAYWRIGHT_BROWSERS_PATH="$HOME/.cache/ms-playwright"' >> /home/claude/.bashrc
    chown claude:claude /home/claude/.bashrc
fi

# ── Timezone ──────────────────────────────────────────────────────────
if [ -n "$TZ" ]; then
    ln -snf "/usr/share/zoneinfo/$TZ" /etc/localtime
    echo "$TZ" > /etc/timezone
fi

# ── Start SSH daemon ─────────────────────────────────────────────────
echo "Starting SSH server on port 2222..."
/usr/sbin/sshd

echo "──────────────────────────────────────────"
echo "  Claude Worker ready."
echo "  SSH:  ssh claude@<host> -p 2222"
echo "  Repos: /repos"
echo "──────────────────────────────────────────"

# ── Idle (PID 1) — user connects via SSH ──────────────────────────────
exec tail -f /dev/null
