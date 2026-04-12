# UnraidContainers

Docker containers for Unraid, published to GitHub Container Registry (ghcr.io).

## Containers

| Container | Description | Build | Latest Image |
|---|---|---|---|
| [claude-worker](containers/claude-worker/) | Dev environment with Claude Code, Node.js, .NET, Python, and SSH access | [![Build](https://github.com/mover5/UnraidContainers/actions/workflows/build-claude-worker.yml/badge.svg)](https://github.com/mover5/UnraidContainers/actions/workflows/build-claude-worker.yml) | [![Version](https://ghcr-badge.egpl.dev/mover5/claude-worker/latest_tag?ignore=latest&trim=major&label=version)](https://github.com/mover5/UnraidContainers/pkgs/container/claude-worker) |
| [cleanrr](containers/cleanrr/) | Torrent lifecycle manager for Deluge with web dashboard | [![Build](https://github.com/mover5/UnraidContainers/actions/workflows/build-cleanrr.yml/badge.svg)](https://github.com/mover5/UnraidContainers/actions/workflows/build-cleanrr.yml) | [![Version](https://ghcr-badge.egpl.dev/mover5/cleanrr/latest_tag?ignore=latest&trim=major&label=version)](https://github.com/mover5/UnraidContainers/pkgs/container/cleanrr) |
| [database-backup](containers/database-backup/) | Scheduled database backups (MySQL, Azure SQL) with web dashboard | [![Build](https://github.com/mover5/UnraidContainers/actions/workflows/build-database-backup.yml/badge.svg)](https://github.com/mover5/UnraidContainers/actions/workflows/build-database-backup.yml) | [![Version](https://ghcr-badge.egpl.dev/mover5/database-backup/latest_tag?ignore=latest&trim=major&label=version)](https://github.com/mover5/UnraidContainers/pkgs/container/database-backup) |
| [azurite-azure-storage](containers/azurite-azure-storage/) | Local Azure Storage emulator (Azurite) with web-based Storage Explorer | [![Build](https://github.com/mover5/UnraidContainers/actions/workflows/build-azurite-azure-storage.yml/badge.svg)](https://github.com/mover5/UnraidContainers/actions/workflows/build-azurite-azure-storage.yml) | [![Version](https://ghcr-badge.egpl.dev/mover5/azurite-azure-storage/latest_tag?ignore=latest&trim=major&label=version)](https://github.com/mover5/UnraidContainers/pkgs/container/azurite-azure-storage) |
| [caddy-reverse-proxy](containers/caddy-reverse-proxy/) | Caddy reverse proxy with automatic HTTPS via Cloudflare DNS-01 challenge | [![Build](https://github.com/mover5/UnraidContainers/actions/workflows/build-caddy-reverse-proxy.yml/badge.svg)](https://github.com/mover5/UnraidContainers/actions/workflows/build-caddy-reverse-proxy.yml) | [![Version](https://ghcr-badge.egpl.dev/mover5/caddy-reverse-proxy/latest_tag?ignore=latest&trim=major&label=version)](https://github.com/mover5/UnraidContainers/pkgs/container/caddy-reverse-proxy) |

## Running a container

All images are available from `ghcr.io/mover5/<container-name>`.

### Pull and run

```bash
docker pull ghcr.io/mover5/claude-worker:latest
docker run -d ghcr.io/mover5/claude-worker:latest
```

### Pin to a version

Each image is tagged with SemVer (e.g. `1.0.0`) and a commit SHA. Use a version tag to pin:

```bash
docker pull ghcr.io/mover5/claude-worker:1.0.0
```

### Unraid

To make all containers available in Unraid's Docker tab:

1. Go to **Docker > Template Repositories**
2. Add: `https://github.com/mover5/UnraidContainers`
3. Click **Save**

All containers from this repo will appear as available templates. When new containers are added to the repo, they automatically show up in Unraid after the next template update.

---

## For maintainers

### Repo structure

```
containers/
  claude-worker/
    Dockerfile
    VERSION          # major.minor — patch auto-increments
    unraid-template.xml
    ...
.github/workflows/
  build-container.yml       # Reusable build & push workflow
  build-claude-worker.yml   # Triggers on changes to claude-worker/
  build-cleanrr.yml         # Triggers on changes to cleanrr/
  build-database-backup.yml # Triggers on changes to database-backup/
  build-azurite-azure-storage.yml # Triggers on changes to azurite-azure-storage/
  build-caddy-reverse-proxy.yml   # Triggers on changes to caddy-reverse-proxy/
  build-all.yml             # Manual trigger to rebuild all containers
  sync-templates.yml        # Auto-syncs unraid-template.xml files to templates/
templates/                  # Flat directory of Unraid templates (auto-generated)
```

### Add a new container

```bash
./add-container.sh my-container
```

This creates:
- `containers/my-container/Dockerfile` — starter Dockerfile
- `containers/my-container/VERSION` — set to `0.1`
- `.github/workflows/build-my-container.yml` — triggers on changes to that container's directory

Edit the Dockerfile, commit, and push. The workflow builds and publishes to `ghcr.io/mover5/my-container`.

### Versioning

Each container has a `VERSION` file containing `major.minor` (e.g. `1.0`). The patch number is calculated automatically from the number of commits that touched the container since `VERSION` was last changed.

| Action | Resulting tag |
|---|---|
| Set `VERSION` to `1.0`, push | `1.0.0` |
| Push another change | `1.0.1` |
| Push again | `1.0.2` |
| Change `VERSION` to `1.1`, push | `1.1.0` |
| Change `VERSION` to `2.0`, push | `2.0.0` |

Every push to `main` also tags with `latest` and the commit SHA.

### Build all containers manually

Go to **Actions > Build All Containers > Run workflow** in GitHub to rebuild every container in the repo.
