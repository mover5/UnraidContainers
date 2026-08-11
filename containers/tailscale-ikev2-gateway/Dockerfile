# Tailscale binaries come from the official image — Alpine's package lags
# months behind and gets flagged in the admin console for known CVEs
FROM tailscale/tailscale:stable AS tailscale

FROM alpine:3.22

LABEL maintainer="mover5"
LABEL org.opencontainers.image.source="https://github.com/mover5/UnraidContainers"

# strongswan  — IKEv2 server (what the built-in Windows VPN client speaks)
# acme.sh     — Let's Encrypt via Cloudflare DNS-01 so Windows needs no cert import
RUN apk add --no-cache \
    bash \
    ca-certificates \
    curl \
    iptables \
    jq \
    openssl \
    strongswan

COPY --from=tailscale /usr/local/bin/tailscaled /usr/local/bin/tailscaled
COPY --from=tailscale /usr/local/bin/tailscale /usr/local/bin/tailscale

ARG ACME_SH_VERSION=3.1.1
RUN apk add --no-cache --virtual .build-deps git \
    && git clone --depth 1 --branch "${ACME_SH_VERSION}" \
        https://github.com/acmesh-official/acme.sh /tmp/acme.sh \
    && cd /tmp/acme.sh \
    && ./acme.sh --install --home /opt/acme.sh --nocron --noprofile \
    && rm -rf /tmp/acme.sh \
    && apk del .build-deps

# Fail the build, not the runtime, if Alpine ever moves the charon daemon
RUN test -x /usr/lib/strongswan/charon

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# IKE + NAT-T
EXPOSE 500/udp 4500/udp

ENTRYPOINT ["/entrypoint.sh"]
