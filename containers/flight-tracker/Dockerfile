# syntax=docker/dockerfile:1

# ---- Stage 1: build the frontend ----
FROM node:22-alpine AS frontend
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Bake the API base URL so the SPA talks to this container's own /api.
ENV VITE_API_URL=/api
RUN npm run build

# ---- Stage 2: runtime (API server + static frontend) ----
FROM node:22-alpine
LABEL maintainer="mover5"
LABEL org.opencontainers.image.source="https://github.com/mover5/UnraidContainers"

WORKDIR /app
ENV NODE_ENV=production \
    PORT=8080

# Server dependencies only (express, pg) — keeps the image small.
COPY server/package.json server/package-lock.json ./
RUN npm ci --omit=dev

# Server code, the built frontend, and the seed data.
COPY server/ ./
COPY --from=frontend /app/dist ./public
COPY src/data/seedFlights.json ./seed/flights.json

EXPOSE 8080
CMD ["node", "index.js"]
