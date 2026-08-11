# tailscale-ikev2-gateway

An IKEv2 VPN gateway into your **Tailscale tailnet**, for machines that can't run the
Tailscale client. Clients connect with the VPN support **built into Windows** (also works
with macOS/iOS/Android built-in VPN) — no extra software — and split-tunnel **only the
Tailscale IP range** (`100.64.0.0/10`) through it.

```
Windows built-in VPN ──IKEv2 (UDP 500/4500)──▶ router port-forward ──▶ this container
                                                                        ├─ strongSwan (IKEv2 + EAP-MSCHAPv2)
                                                                        └─ tailscaled  ──▶ your tailnet
```

The container joins your tailnet as a regular node. Traffic from VPN clients destined for
`100.64.0.0/10` is NATed out the `tailscale0` interface, so clients can reach every tailnet
node your ACLs let *this node* reach. No subnet routing or ACL advertisement is needed.

## Setup

### 1. Container (Unraid)

Install from the template, or:

```bash
docker run -d --name tailscale-ikev2-gateway \
  --cap-add=NET_ADMIN --device=/dev/net/tun --sysctl net.ipv4.ip_forward=1 \
  -p 500:500/udp -p 4500:4500/udp \
  -v /mnt/user/appdata/tailscale-ikev2-gateway:/data \
  -e VPN_DOMAIN=vpn.example.com \
  -e VPN_USERNAME=me -e VPN_PASSWORD='a-strong-password' \
  -e CF_DNS_API_TOKEN=... \
  -e TS_AUTHKEY=tskey-auth-... \
  ghcr.io/mover5/tailscale-ikev2-gateway:latest
```

If `TS_AUTHKEY` is not set, check the container log on first start for a Tailscale login
URL. Node state persists in `/data`, so this is a one-time step.

### 2. DNS + certificate

The recommended path needs a domain whose DNS is on Cloudflare:

1. Create an **A record** (e.g. `vpn.example.com`) pointing at your home public IP —
   **DNS only / grey cloud**, not proxied (Cloudflare doesn't proxy UDP). Or set
   `DDNS_UPDATE=true` and the container creates/updates the record itself every 5 minutes.
2. Set `CF_DNS_API_TOKEN` to a Cloudflare API token with **Zone → DNS → Edit** on that zone
   (the same kind of token caddy-reverse-proxy uses). The container gets a **Let's Encrypt**
   certificate via DNS-01 and renews it automatically. Windows trusts it out of the box —
   **no certificate import needed on the client.**

Without a Cloudflare token, the container generates a self-signed CA in `/data/pki/ca.crt`,
which each client must import once into **Local Computer → Trusted Root Certification
Authorities** (requires admin on the client — avoid this path if the machine is locked down).

### 3. Router (Netgear Nighthawk)

Forward two UDP ports to your Unraid box (`192.168.1.30`):

- **Advanced → Advanced Setup → Port Forwarding / Port Triggering**
- Add custom service: **UDP 500 → 192.168.1.30:500**
- Add custom service: **UDP 4500 → 192.168.1.30:4500**

If the client sits *inside* your LAN, Nighthawk NAT loopback usually lets `vpn.example.com`
work from inside too; if not, connect to `192.168.1.30` directly (self-signed cert mode with
an IP SAN, or add a local DNS override for the domain).

### 4. Windows client (no extra software)

Run in **PowerShell as the normal user** (no admin needed — this creates a per-user VPN
profile):

```powershell
Add-VpnConnection -Name "Tailnet" -ServerAddress "vpn.example.com" `
  -TunnelType IKEv2 -AuthenticationMethod EAP -EncryptionLevel Required `
  -SplitTunneling -RememberCredential

# Split tunnel: ONLY the Tailscale range goes through the VPN
Add-VpnConnectionRoute -ConnectionName "Tailnet" -DestinationPrefix "100.64.0.0/10"

# Upgrade crypto from Windows' weak IKEv2 defaults (recommended)
Set-VpnConnectionIPsecConfiguration -ConnectionName "Tailnet" `
  -EncryptionMethod AES256 -IntegrityCheckMethod SHA256 -DHGroup Group14 `
  -CipherTransformConstants AES256 -AuthenticationTransformConstants SHA256128 `
  -PfsGroup None -Force
```

Then connect from the network flyout / **Settings → Network & Internet → VPN**, entering
`VPN_USERNAME` / `VPN_PASSWORD`. Or script it: `rasdial "Tailnet" me a-strong-password`.

While connected, everything except `100.64.0.0/10` uses the normal network path. Reach
tailnet nodes by their `100.x.y.z` IPs (`tailscale status` on any other device lists them).
For MagicDNS names, set `VPN_DNS=100.100.100.100` on the container and recreate the Windows
connection — note this routes the client's DNS lookups through the tunnel while connected.

If you skip the `Set-VpnConnectionIPsecConfiguration` step the connection still works — the
server also offers the SHA1/modp1024 proposals Windows sends by default.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `VPN_DOMAIN` | *(required)* | Public hostname clients connect to; certificate identity |
| `VPN_USERNAME` / `VPN_PASSWORD` | *(required)* | VPN login (EAP-MSCHAPv2) |
| `VPN_USERS` | — | Extra logins: `alice:pw1,bob:pw2` |
| `CF_DNS_API_TOKEN` | — | Cloudflare token → Let's Encrypt cert (else self-signed) |
| `ACME_EMAIL` | — | Let's Encrypt account email |
| `DDNS_UPDATE` | `false` | Keep the A record pointed at your current public IP |
| `TS_AUTHKEY` | — | Tailscale auth key; omit for interactive login via log URL |
| `TS_HOSTNAME` | `tailscale-ikev2-gateway` | Node name in the tailnet |
| `TS_EXTRA_ARGS` | — | Extra `tailscale up` flags (e.g. `--accept-routes`) |
| `ALLOWED_SUBNETS` | `100.64.0.0/10` | Subnets the tunnel carries; add `192.168.1.0/24` to expose the LAN too (then add a matching `Add-VpnConnectionRoute` on the client) |
| `VPN_POOL` | `10.53.53.0/24` | Virtual IPs for VPN clients |
| `VPN_DNS` | — | DNS pushed to clients (`100.100.100.100` = MagicDNS) |

## Troubleshooting

- **Error 13801 / certificate errors on Windows** — the `ServerAddress` in the client
  profile must exactly match `VPN_DOMAIN` (that's the name in the cert). With self-signed
  certs, the CA must be in the *machine* (not user) Trusted Root store.
- **Error 809 / timeout** — UDP 500/4500 aren't reaching the container. Check the Nighthawk
  port forwards, and that your ISP doesn't CGNAT you (the WAN IP on the router should match
  `curl ifconfig.me`; if it doesn't, inbound connections can't reach you).
- **Connects but tailnet IPs don't respond** — check `tailscale status` inside the container
  (`docker exec tailscale-ikev2-gateway tailscale status`); confirm your tailnet ACLs allow
  this node to reach the target; confirm the client route exists (`Get-VpnConnectionRoute`).
- **charon fails to start / no IPsec** — the host kernel needs standard XFRM/ESP support.
  Unraid ships these; if you see algorithm/module errors, `modprobe esp4 xfrm_user` on the
  host.
