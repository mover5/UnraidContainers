FROM caddy:2-builder AS builder

RUN xcaddy build \
    --with github.com/caddy-dns/cloudflare

FROM caddy:2

LABEL maintainer="mover5"
LABEL org.opencontainers.image.source="https://github.com/mover5/UnraidContainers"

COPY --from=builder /usr/bin/caddy /usr/bin/caddy

# Default Caddyfile — copied to /etc/caddy/ on first run if none exists
COPY config/Caddyfile /defaults/Caddyfile

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80 443

ENTRYPOINT ["/entrypoint.sh"]
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
