# syntax=docker/dockerfile:1

# ---- Stage 1: build the frontend ----
FROM node:22-bookworm-slim AS frontend
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Bake the API base URL so the SPA syncs with this container's own /api.
ENV VITE_API_URL=/api
RUN npm run build

# ---- Stage 2: server deps (compiles better-sqlite3 if no prebuild) ----
FROM node:22-bookworm-slim AS deps
WORKDIR /app
# Toolchain only for compiling better-sqlite3's native addon when no prebuilt
# binary matches this platform. Kept out of the runtime image.
RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 make g++ \
  && rm -rf /var/lib/apt/lists/*
COPY server/package.json server/package-lock.json ./
RUN npm ci --omit=dev

# ---- Stage 3: runtime ----
FROM node:22-bookworm-slim
LABEL maintainer="mover5"
LABEL org.opencontainers.image.source="https://github.com/mover5/UnraidContainers"

WORKDIR /app
ENV NODE_ENV=production \
    PORT=8080 \
    DB_PATH=/data/stitch.db

COPY --from=deps /app/node_modules ./node_modules
COPY server/package.json server/index.js server/app.js server/project.js ./
COPY --from=frontend /app/dist ./public

# SQLite database lives here — map this to a persistent host path on Unraid.
VOLUME ["/data"]

EXPOSE 8080
HEALTHCHECK --interval=60s --timeout=5s --start-period=10s \
  CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||8080)+'/api/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "index.js"]
