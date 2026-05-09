FROM caddy:2-builder AS builder

RUN xcaddy build \
    --with github.com/caddy-dns/cloudflare

FROM caddy:2

LABEL maintainer="mover5"
LABEL org.opencontainers.image.source="https://github.com/mover5/UnraidContainers"

COPY --from=builder /usr/bin/caddy /usr/bin/caddy

# Python + supervisord for the admin UI sidecar
RUN apk add --no-cache python3 py3-pip supervisor \
    && python3 -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

COPY web/requirements.txt /tmp/requirements.txt
RUN /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY web /app/web

# Default Caddyfile — copied to /etc/caddy/ on first run if none exists
COPY config/Caddyfile /defaults/Caddyfile

COPY supervisord.conf /etc/supervisord.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && mkdir -p /var/log/caddy /var/log/supervisor

EXPOSE 80 443 9999

ENTRYPOINT ["/entrypoint.sh"]
