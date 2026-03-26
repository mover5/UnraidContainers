#!/bin/sh
set -e

CADDYFILE="/etc/caddy/Caddyfile"

# If no Caddyfile exists, copy the default one
if [ ! -f "$CADDYFILE" ]; then
    echo "No Caddyfile found at $CADDYFILE — copying default"
    cp /defaults/Caddyfile "$CADDYFILE"
fi

exec "$@"
