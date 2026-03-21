# CLAUDE.md

## What this repo is

Monorepo for all of mover5's Unraid Docker containers. Each container lives in its own subdirectory under `containers/` and is independently built and published to GitHub Container Registry (ghcr.io).

## Repo structure

```
containers/<name>/           # Each container gets its own directory
  Dockerfile                 # Required — the container build
  VERSION                    # Required — contains major.minor (e.g. "1.0"), patch auto-calculated
  entrypoint.sh              # Optional
  config/                    # Optional — supporting config files
  unraid-template.xml        # Optional — Unraid Community Apps template
  icon.png                   # Optional — icon for Unraid template

.github/workflows/
  build-container.yml        # Reusable workflow — all containers call this
  build-<name>.yml           # Per-container workflow — triggers on changes to that container's dir
  build-all.yml              # Manual trigger to rebuild every container
  cleanup-images.yml         # Weekly cleanup of old GHCR image versions

add-container.sh             # Scaffolding script to create a new container + workflow
```

## How builds work

- Each container has a per-container workflow (e.g. `build-claude-worker.yml`) that triggers on pushes to `main` that touch files under `containers/<name>/`.
- These all call the reusable `build-container.yml` workflow, which handles login, build, tag, and push to `ghcr.io/mover5/<name>`.
- PRs build but do not push (validation only).
- `build-all.yml` can be triggered manually from the Actions tab to rebuild everything.

## Versioning (SemVer)

Each container has a `VERSION` file with `major.minor`. The patch number is auto-calculated by counting commits that touched the container's directory since `VERSION` was last changed.

- To bump patch: just push changes (automatic).
- To bump minor: edit `VERSION` (e.g. `1.0` → `1.1`), patch resets to 0.
- To bump major: edit `VERSION` (e.g. `1.1` → `2.0`), patch resets to 0.

Images are tagged with: the semver, `latest` (on main), and the commit SHA.

## Adding a new container

Run `./add-container.sh <name>`. This creates:
- `containers/<name>/Dockerfile`
- `containers/<name>/VERSION` (set to `0.1`)
- `.github/workflows/build-<name>.yml`

Then edit the Dockerfile, commit, and push.

## GHCR storage management

A `cleanup-images.yml` workflow runs weekly (Sunday 3am UTC) and on manual trigger. It prunes old image versions to prevent storage from ballooning:
- Keeps 10 most recent untagged versions, deletes the rest.
- Keeps 20 most recent tagged versions total, deletes the rest.

Docker layer caching uses GitHub Actions Cache (`type=gha`), which is capped at 10GB per repo and self-manages via LRU eviction. No intermediate artifacts are used — images go straight to GHCR.

## Important conventions

- Image names match the container directory name: `containers/foo/` → `ghcr.io/mover5/foo`.
- Every container must have a `Dockerfile` and a `VERSION` file.
- The `build-container.yml` reusable workflow requires `fetch-depth: 0` (full git history) to calculate the patch version.
- `unraid-template.xml` files should reference `ghcr.io/mover5/<name>` as the repository and point support/icon URLs to this repo (UnraidContainers), not individual repos.

## Containers

### claude-worker
Dev environment container with Claude Code, Node.js 22, .NET 9, Python 3, GitHub CLI, Azure CLI, and Playwright. Access via SSH on port 2222 + tmux. Originally migrated from the standalone `UnraidClaudeWorker` repo. Supports PUID/PGID remapping, persistent home/repos volumes, and optional SSH password auth.
