#!/usr/bin/env bash
set -uo pipefail

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
die() { log "FATAL: $*"; exit 1; }

# ---------------------------------------------------------------------------
# Configuration (env vars)
# ---------------------------------------------------------------------------
VPN_DOMAIN="${VPN_DOMAIN:-}"            # public hostname (or IP) clients connect to — required
VPN_USERNAME="${VPN_USERNAME:-}"        # first VPN user — required
VPN_PASSWORD="${VPN_PASSWORD:-}"        # first VPN user's password — required
VPN_USERS="${VPN_USERS:-}"              # optional extra users: "alice:pw1,bob:pw2"
VPN_POOL="${VPN_POOL:-10.53.53.0/24}"   # virtual IPs handed to VPN clients
ALLOWED_SUBNETS="${ALLOWED_SUBNETS:-100.64.0.0/10}"  # what the tunnel carries (traffic selector)
VPN_DNS="${VPN_DNS:-}"                  # optional DNS pushed to clients (e.g. 100.100.100.100 for MagicDNS)

CF_DNS_API_TOKEN="${CF_DNS_API_TOKEN:-}" # Cloudflare token (Zone:DNS:Edit) -> Let's Encrypt cert
ACME_EMAIL="${ACME_EMAIL:-}"
DDNS_UPDATE="${DDNS_UPDATE:-false}"      # keep the Cloudflare A record pointed at this WAN IP

TS_AUTHKEY="${TS_AUTHKEY:-}"
TS_HOSTNAME="${TS_HOSTNAME:-tailscale-ikev2-gateway}"
TS_EXTRA_ARGS="${TS_EXTRA_ARGS:-}"

[ -n "$VPN_DOMAIN" ] || die "VPN_DOMAIN is required (the public hostname clients will connect to)"
[ -n "$VPN_USERNAME" ] || die "VPN_USERNAME is required"
[ -n "$VPN_PASSWORD" ] || die "VPN_PASSWORD is required"

mkdir -p /data/tailscale /data/acme /data/pki /var/run/tailscale
mkdir -p /etc/swanctl/x509 /etc/swanctl/x509ca /etc/swanctl/private

# ---------------------------------------------------------------------------
# Kernel prerequisites
# ---------------------------------------------------------------------------
if [ "$(cat /proc/sys/net/ipv4/ip_forward 2>/dev/null)" != "1" ]; then
  if ! sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1; then
    die "IP forwarding is disabled and cannot be enabled. Add --sysctl net.ipv4.ip_forward=1 to the container's extra parameters."
  fi
fi

# ---------------------------------------------------------------------------
# NAT + forwarding: VPN pool -> tailnet (and anywhere else ALLOWED_SUBNETS points)
# ---------------------------------------------------------------------------
ipt() { iptables -C "$@" 2>/dev/null || iptables -A "$@"; }
iptn() { iptables -t nat -C "$@" 2>/dev/null || iptables -t nat -A "$@"; }
iptm() { iptables -t mangle -C "$@" 2>/dev/null || iptables -t mangle -A "$@"; }

iptn POSTROUTING -s "$VPN_POOL" -o tailscale0 -j MASQUERADE
iptn POSTROUTING -s "$VPN_POOL" -o eth0 -j MASQUERADE
ipt FORWARD -s "$VPN_POOL" -j ACCEPT
ipt FORWARD -d "$VPN_POOL" -j ACCEPT
# tailscale0 has a 1280 MTU; clamp TCP MSS so client connections don't stall
iptm FORWARD -s "$VPN_POOL" -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
iptm FORWARD -d "$VPN_POOL" -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu

# ---------------------------------------------------------------------------
# Tailscale
# ---------------------------------------------------------------------------
log "Starting tailscaled..."
tailscaled \
  --state=/data/tailscale/tailscaled.state \
  --statedir=/data/tailscale \
  --socket=/var/run/tailscale/tailscaled.sock &
TAILSCALED_PID=$!

for _ in $(seq 1 30); do
  [ -S /var/run/tailscale/tailscaled.sock ] && break
  sleep 0.5
done

# Bring the node up. Without an auth key on first run, the login URL is printed
# to the container log — open it to authorize the node; state then persists in /data.
(
  # shellcheck disable=SC2086
  if tailscale up ${TS_AUTHKEY:+--authkey="$TS_AUTHKEY"} --hostname="$TS_HOSTNAME" $TS_EXTRA_ARGS; then
    log "Tailscale is up: $(tailscale ip -4 2>/dev/null | head -1)"
  else
    log "WARNING: 'tailscale up' did not complete — check the log above for a login URL"
  fi
) &

# ---------------------------------------------------------------------------
# Server certificate
# ---------------------------------------------------------------------------
ACME="/opt/acme.sh/acme.sh --home /opt/acme.sh --config-home /data/acme"

issue_letsencrypt() {
  export CF_Token="$CF_DNS_API_TOKEN"
  log "Requesting/renewing Let's Encrypt certificate for $VPN_DOMAIN (Cloudflare DNS-01)..."
  $ACME --issue --dns dns_cf -d "$VPN_DOMAIN" --server letsencrypt --keylength 2048 \
    ${ACME_EMAIL:+--accountemail "$ACME_EMAIL"}
  rc=$?
  # 0 = issued, 2 = still valid / renewal skipped — both fine
  [ $rc -eq 0 ] || [ $rc -eq 2 ] || die "acme.sh failed (exit $rc). Check CF_DNS_API_TOKEN and that $VPN_DOMAIN's DNS zone is on Cloudflare."
  $ACME --install-cert -d "$VPN_DOMAIN" \
    --key-file /etc/swanctl/private/server.key \
    --cert-file /etc/swanctl/x509/server.pem \
    --ca-file /etc/swanctl/x509ca/chain.pem \
    --reloadcmd "swanctl --load-creds >/dev/null 2>&1 || true" \
    || die "acme.sh --install-cert failed"
  log "Certificate installed (publicly trusted — no cert import needed on Windows)."
}

issue_selfsigned() {
  local pki=/data/pki san
  if printf '%s' "$VPN_DOMAIN" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
    san="IP:$VPN_DOMAIN"
  else
    san="DNS:$VPN_DOMAIN"
  fi
  if [ ! -f "$pki/ca.key" ]; then
    log "Generating self-signed CA (persisted in /data/pki)..."
    openssl req -x509 -newkey rsa:4096 -nodes -days 3650 \
      -keyout "$pki/ca.key" -out "$pki/ca.crt" \
      -subj "/CN=Tailscale IKEv2 Gateway CA" || die "CA generation failed"
  fi
  if [ ! -f "$pki/server.crt" ] || ! openssl x509 -in "$pki/server.crt" -noout -text | grep -q "$VPN_DOMAIN"; then
    log "Generating server certificate for $VPN_DOMAIN..."
    openssl req -newkey rsa:2048 -nodes \
      -keyout "$pki/server.key" -out "$pki/server.csr" \
      -subj "/CN=$VPN_DOMAIN" || die "CSR generation failed"
    openssl x509 -req -in "$pki/server.csr" -days 1825 \
      -CA "$pki/ca.crt" -CAkey "$pki/ca.key" -CAcreateserial \
      -out "$pki/server.crt" \
      -extfile <(printf 'subjectAltName=%s\nextendedKeyUsage=serverAuth,1.3.6.1.5.5.8.2.2\nbasicConstraints=CA:FALSE\n' "$san") \
      || die "server certificate signing failed"
  fi
  cp "$pki/server.key" /etc/swanctl/private/server.key
  cp "$pki/server.crt" /etc/swanctl/x509/server.pem
  cp "$pki/ca.crt" /etc/swanctl/x509ca/chain.pem
  log "Self-signed certificate in use. Windows clients must import the CA once:"
  log "  /data/pki/ca.crt -> Local Computer > Trusted Root Certification Authorities (requires admin)."
  log "Tip: set CF_DNS_API_TOKEN to switch to Let's Encrypt and skip the import entirely."
}

if [ -n "$CF_DNS_API_TOKEN" ]; then
  issue_letsencrypt
else
  issue_selfsigned
fi

# ---------------------------------------------------------------------------
# strongSwan configuration
# ---------------------------------------------------------------------------
cat > /etc/strongswan.d/zz-container.conf <<'EOF'
charon {
    filelog {
        stderr {
            default = 1
            ike_name = yes
        }
    }
}
EOF

# EAP secrets: VPN_USERNAME/VPN_PASSWORD plus optional VPN_USERS ("u1:p1,u2:p2")
secrets=""
n=0
add_user() {
  n=$((n + 1))
  secrets="$secrets
        eap-$n {
            id = \"$1\"
            secret = \"$2\"
        }"
}
add_user "$VPN_USERNAME" "$VPN_PASSWORD"
if [ -n "$VPN_USERS" ]; then
  IFS=',' read -ra extra <<< "$VPN_USERS"
  for entry in "${extra[@]}"; do
    u="${entry%%:*}"; p="${entry#*:}"
    [ -n "$u" ] && [ -n "$p" ] && add_user "$u" "$p"
  done
fi

# Proposal lists include both the strong set (for clients configured via
# Set-VpnConnectionIPsecConfiguration) and the weaker Windows defaults so an
# out-of-the-box connection still works.
cat > /etc/swanctl/swanctl.conf <<EOF
connections {
    ikev2-eap {
        version = 2
        proposals = aes256-sha256-modp2048,aes256-sha384-modp2048,aes256-sha1-modp1024,aes128-sha1-modp1024
        rekey_time = 0s
        pools = vpn-pool
        fragmentation = yes
        dpd_delay = 30s
        send_cert = always
        local {
            auth = pubkey
            certs = server.pem
            id = @$VPN_DOMAIN
        }
        remote {
            auth = eap-mschapv2
            eap_id = %any
        }
        children {
            tailnet {
                local_ts = $ALLOWED_SUBNETS
                esp_proposals = aes256gcm16,aes128gcm16,aes256-sha256,aes256-sha1,aes128-sha1
                dpd_action = clear
            }
        }
    }
}

pools {
    vpn-pool {
        addrs = $VPN_POOL${VPN_DNS:+
        dns = $VPN_DNS}
    }
}

secrets {$secrets
}
EOF

# ---------------------------------------------------------------------------
# charon (IKEv2 daemon)
# ---------------------------------------------------------------------------
CHARON=""
for c in /usr/lib/ipsec/charon /usr/libexec/ipsec/charon; do
  [ -x "$c" ] && CHARON="$c" && break
done
[ -n "$CHARON" ] || die "charon binary not found"

log "Starting charon..."
"$CHARON" &
CHARON_PID=$!

for _ in $(seq 1 30); do
  [ -S /var/run/charon.vici ] && break
  sleep 0.5
done
swanctl --load-all || die "swanctl --load-all failed — check the generated /etc/swanctl/swanctl.conf"
log "IKEv2 gateway ready on UDP 500/4500 as '$VPN_DOMAIN' (tunnel carries: $ALLOWED_SUBNETS)"

# ---------------------------------------------------------------------------
# Background loops: cert renewal + optional Cloudflare DDNS
# ---------------------------------------------------------------------------
if [ -n "$CF_DNS_API_TOKEN" ]; then
  (
    while sleep 86400; do
      export CF_Token="$CF_DNS_API_TOKEN"
      $ACME --cron >/dev/null 2>&1
      swanctl --load-creds >/dev/null 2>&1
    done
  ) &
fi

cf_api() { # method path [json-body]
  curl -fs -X "$1" "https://api.cloudflare.com/client/v4$2" \
    -H "Authorization: Bearer $CF_DNS_API_TOKEN" \
    -H "Content-Type: application/json" \
    ${3:+--data "$3"}
}

if [ "$DDNS_UPDATE" = "true" ] && [ -n "$CF_DNS_API_TOKEN" ]; then
  (
    # Find the zone: strip labels off VPN_DOMAIN until a zone matches
    zone_id="" zone_name="$VPN_DOMAIN"
    while [ -n "$zone_name" ]; do
      zone_id=$(cf_api GET "/zones?name=$zone_name" | jq -r '.result[0].id // empty')
      [ -n "$zone_id" ] && break
      case "$zone_name" in *.*) zone_name="${zone_name#*.}" ;; *) zone_name="" ;; esac
    done
    if [ -z "$zone_id" ]; then
      log "DDNS: no Cloudflare zone found for $VPN_DOMAIN (token may lack Zone:Read) — DDNS disabled"
      exit 0
    fi
    log "DDNS: managing A record for $VPN_DOMAIN in zone $zone_name"
    last_ip=""
    while true; do
      ip=$(curl -fs --max-time 10 https://api.ipify.org || true)
      if printf '%s' "$ip" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' && [ "$ip" != "$last_ip" ]; then
        rec=$(cf_api GET "/zones/$zone_id/dns_records?type=A&name=$VPN_DOMAIN" | jq -r '.result[0].id // empty')
        body="{\"type\":\"A\",\"name\":\"$VPN_DOMAIN\",\"content\":\"$ip\",\"ttl\":120,\"proxied\":false}"
        if [ -n "$rec" ]; then
          cf_api PUT "/zones/$zone_id/dns_records/$rec" "$body" >/dev/null && log "DDNS: $VPN_DOMAIN -> $ip"
        else
          cf_api POST "/zones/$zone_id/dns_records" "$body" >/dev/null && log "DDNS: created $VPN_DOMAIN -> $ip"
        fi
        last_ip="$ip"
      fi
      sleep 300
    done
  ) &
fi

# ---------------------------------------------------------------------------
# Supervise: exit if either core daemon dies; forward SIGTERM for clean stop
# ---------------------------------------------------------------------------
shutdown() {
  log "Shutting down..."
  kill "$CHARON_PID" 2>/dev/null
  tailscale down 2>/dev/null
  kill "$TAILSCALED_PID" 2>/dev/null
  # shellcheck disable=SC2046
  kill $(jobs -p) 2>/dev/null
  exit 0
}
trap shutdown TERM INT

while true; do
  kill -0 "$CHARON_PID" 2>/dev/null || die "charon exited"
  kill -0 "$TAILSCALED_PID" 2>/dev/null || die "tailscaled exited"
  sleep 5 &
  wait $!
done
