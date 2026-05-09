#!/bin/sh
set -e

CADDYFILE="/etc/caddy/Caddyfile"

# Seed default Caddyfile on first run
if [ ! -f "$CADDYFILE" ]; then
    echo "No Caddyfile found at $CADDYFILE — copying default"
    cp /defaults/Caddyfile "$CADDYFILE"
fi

mkdir -p /var/log/caddy /var/log/supervisor

# Allow ad-hoc overrides (e.g. running mock backend in dev compose):
#   docker run ... -e CADDY_BACKEND=mock ...
# By default supervisord launches Caddy + the admin UI together.
if [ "$1" = "" ] || [ "$1" = "supervisord" ]; then
    exec /usr/bin/supervisord -c /etc/supervisord.conf
fi

# Otherwise allow direct command override (e.g. for debugging)
exec "$@"
