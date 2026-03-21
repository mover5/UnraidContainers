#!/usr/bin/env bash
set -euo pipefail

if [ -z "${1:-}" ]; then
  echo "Usage: $0 <container-name>"
  echo "Creates a new container directory and GitHub Actions workflow."
  exit 1
fi

NAME="$1"
CONTAINER_DIR="containers/$NAME"
WORKFLOW_FILE=".github/workflows/build-${NAME}.yml"

if [ -d "$CONTAINER_DIR" ]; then
  echo "Error: $CONTAINER_DIR already exists"
  exit 1
fi

mkdir -p "$CONTAINER_DIR"

echo "0.1" > "$CONTAINER_DIR/VERSION"

cat > "$CONTAINER_DIR/Dockerfile" << 'DOCKERFILE'
FROM alpine:3.21

LABEL maintainer="mover5"
LABEL org.opencontainers.image.source="https://github.com/mover5/UnraidContainers"

# Add your setup here

CMD ["echo", "Hello"]
DOCKERFILE

cat > "$WORKFLOW_FILE" << WORKFLOW
name: Build ${NAME}

on:
  push:
    branches: [main]
    paths:
      - "containers/${NAME}/**"
  pull_request:
    paths:
      - "containers/${NAME}/**"

jobs:
  build:
    uses: ./.github/workflows/build-container.yml
    with:
      container_name: ${NAME}
    permissions:
      contents: read
      packages: write
WORKFLOW

echo "Created:"
echo "  $CONTAINER_DIR/Dockerfile"
echo "  $CONTAINER_DIR/VERSION (0.1)"
echo "  $WORKFLOW_FILE"
echo ""
echo "Next steps:"
echo "  1. Edit $CONTAINER_DIR/Dockerfile"
echo "  2. Commit and push to trigger the build"
echo ""
echo "Versioning:"
echo "  - Patch increments automatically on each push"
echo "  - Edit VERSION to set major.minor (patch resets to 0)"
