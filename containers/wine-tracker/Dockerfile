# syntax=docker/dockerfile:1

# ---- Stage 1: install deps (compiles better-sqlite3 if no prebuild) ----
FROM node:22-bookworm-slim AS deps
WORKDIR /app
# Build toolchain is only needed to compile better-sqlite3's native addon when a
# prebuilt binary isn't available for this platform. Kept out of the runtime.
RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 make g++ \
  && rm -rf /var/lib/apt/lists/*
COPY package.json package-lock.json* ./
RUN npm install --omit=dev

# ---- Stage 2: runtime ----
FROM node:22-bookworm-slim
LABEL maintainer="mover5"
LABEL org.opencontainers.image.source="https://github.com/mover5/UnraidContainers"

WORKDIR /app
ENV NODE_ENV=production \
    PORT=8080 \
    DB_PATH=/data/wine.db

COPY --from=deps /app/node_modules ./node_modules
COPY package.json server.js ./
COPY public ./public

# SQLite database lives here — map this to a persistent host path on Unraid.
VOLUME ["/data"]

EXPOSE 8080
CMD ["node", "server.js"]
