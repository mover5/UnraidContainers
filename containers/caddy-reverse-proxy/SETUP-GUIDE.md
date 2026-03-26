# Caddy Reverse Proxy Setup Guide

Complete guide for routing subdomains to Docker containers with automatic HTTPS, behind Tailscale.

---

## Step 1: Move DNS to Cloudflare

GoDaddy's API is unreliable for automated cert management. Move DNS management (not domain registration) to Cloudflare.

1. Create a free account at [cloudflare.com](https://dash.cloudflare.com/sign-up)
2. Click **Add a site** and enter your domain (e.g. `yourdomain.com`)
3. Select the **Free** plan
4. Cloudflare will scan and import your existing DNS records — review them and confirm
5. Cloudflare gives you two nameservers (e.g. `anna.ns.cloudflare.com`, `bob.ns.cloudflare.com`)
6. In GoDaddy: go to **My Domains > your domain > DNS > Nameservers > Change**
7. Replace GoDaddy's nameservers with Cloudflare's two nameservers
8. Back in Cloudflare, click **Done, check nameservers**
9. Wait for propagation (usually 15 min to a few hours)

**Important Cloudflare setting:** Once active, go to **SSL/TLS** in Cloudflare and set the mode to **Full (strict)**. Since Caddy manages its own certs, you don't want Cloudflare proxying or downgrading your traffic. Also, make sure the DNS records you create in the next step have the **proxy toggle OFF** (grey cloud, DNS only) — Cloudflare's proxy can't reach your Tailscale IP.

## Step 2: Create DNS Records in Cloudflare

In Cloudflare dashboard > **DNS > Records**, add:

| Type | Name | Content | Proxy status |
|------|------|---------|--------------|
| A | `@` | `100.x.x.x` (your Tailscale IP) | **DNS only** (grey cloud) |
| A | `*` | `100.x.x.x` (your Tailscale IP) | **DNS only** (grey cloud) |

The wildcard (`*`) record means any subdomain resolves to your server — you won't need to touch DNS when adding new services.

To find your server's Tailscale IP:
```bash
tailscale ip -4
```

**Important:** The proxy toggle MUST be off (grey cloud / "DNS only"). Cloudflare's proxy cannot route to Tailscale IPs. If the orange cloud is on, requests go through Cloudflare's servers first, which can't reach your private network.

## Step 3: Create a Cloudflare API Token

Caddy needs an API token to create the DNS TXT records for certificate verification.

1. Go to [Cloudflare API Tokens](https://dash.cloudflare.com/profile/api-tokens)
2. Click **Create Token**
3. Use the **Edit zone DNS** template, or create a custom token with:
   - **Permissions:** Zone > DNS > Edit
   - **Zone Resources:** Include > Specific zone > `yourdomain.com`
4. Click **Continue to summary > Create Token**
5. Copy the token — you'll need it for the Unraid container config

## Step 4: Install the Caddy Container on Unraid

If you're using this repo's Unraid template system, the container will show up in Docker > Add Container after syncing templates.

Otherwise, create the container manually in Unraid:

- **Repository:** `ghcr.io/mover5/caddy-reverse-proxy:latest`
- **Network Type:** Choose `host` if your containers use host networking, or `br0`/custom if you need Caddy on a specific IP. Using `host` is simplest — it binds ports 80/443 directly on the Unraid host.
- **Port mappings (if not host network):**
  - `80` -> `80` (HTTP, redirects to HTTPS)
  - `443` -> `443` (HTTPS)
- **Variables:**
  - `CF_API_TOKEN` = the token from Step 3
- **Volumes:**
  - `/mnt/user/appdata/caddy-reverse-proxy/config` -> `/etc/caddy` (your Caddyfile lives here)
  - `/mnt/user/appdata/caddy-reverse-proxy/data` -> `/data` (SSL certs and Caddy state)

Start the container once to let it create the default Caddyfile.

## Step 5: Configure the Caddyfile

Edit `/mnt/user/appdata/caddy-reverse-proxy/config/Caddyfile` on your Unraid server.

Here's a real example assuming your Unraid server's local IP is `192.168.1.100`:

```Caddyfile
# Use Cloudflare DNS-01 for all certificates
{
    acme_dns cloudflare {env.CF_API_TOKEN}
}

# Cleanrr — torrent manager dashboard
cleanrr.yourdomain.com {
    reverse_proxy 192.168.1.100:9494
}

# Database Backup — backup dashboard
backups.yourdomain.com {
    reverse_proxy 192.168.1.100:8008
}

# Azurite — storage explorer
azurite.yourdomain.com {
    reverse_proxy 192.168.1.100:8080
}
```

### What IP to use for `reverse_proxy`

This depends on your networking setup:

- **Caddy in host network mode:** Use `127.0.0.1:<port>` or `192.168.1.x:<port>` (your LAN IP)
- **Caddy in bridge/custom network:** Use the container's LAN IP or Unraid's IP — the container needs a route to the target port
- **Docker compose with a shared network:** Use the container name as hostname (e.g. `reverse_proxy grafana:3000`)

For Unraid where each container is configured separately, using your server's LAN IP (e.g. `192.168.1.100:<port>`) is the simplest and most reliable option.

### Adding a new service

Just add a block to the Caddyfile and restart the Caddy container:

```Caddyfile
newservice.yourdomain.com {
    reverse_proxy 192.168.1.100:PORTNUMBER
}
```

No DNS changes needed (the wildcard record covers it). Caddy automatically gets an SSL cert on first request.

## Step 6: Restart and Verify

1. Restart the Caddy container in Unraid
2. From a device on your Tailscale network, open `https://cleanrr.yourdomain.com` (or whatever you configured)
3. You should see a valid SSL certificate and your service

Check Caddy's logs if something isn't working:
```bash
docker logs caddy-reverse-proxy
```

Common issues:
- **"permission denied" or "unauthorized" in logs:** Your CF_API_TOKEN is wrong or doesn't have DNS edit permissions for the right zone
- **Cert takes a minute:** First-time cert issuance via DNS-01 can take 30-90 seconds while the TXT record propagates
- **Connection refused:** Make sure the target container is running and the port is correct. Try `curl http://192.168.1.100:<port>` from the Unraid terminal to verify

---

## Quick Reference

| Task | What to do |
|------|------------|
| Add a new service | Add block to Caddyfile, restart Caddy |
| Change a port | Edit the `reverse_proxy` line in Caddyfile, restart |
| Add a new subdomain | Nothing — wildcard DNS handles it |
| Renew SSL certs | Nothing — Caddy auto-renews |
| Check cert status | `docker exec caddy-reverse-proxy caddy list-certificates` |
| Reload without restart | `docker exec caddy-reverse-proxy caddy reload --config /etc/caddy/Caddyfile` |
