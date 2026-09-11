# Production image for the Ketabdaneh web app (Task 5.11; docs/01 §12).
#
# Multi-stage on Next.js standalone output (next.config.ts):
#   deps    — npm ci from the lockfile only
#   build   — next build (production; NEXT_PUBLIC_API_BASE_URL is a
#             BUILD-TIME, public value — the browser calls the API
#             directly, docs/01 §4 — never a secret, so a build arg is
#             the correct mechanism)
#   runtime — only server.js, the traced files, static assets, and the
#             i18n message catalogs; runs `next start`-equivalent as a
#             non-root user. No next dev, no watchers, no hot reload.
#
# No backend secret ever enters this image: the web app holds none
# (bearer tokens live in the browser's storage at runtime, not in the
# bundle). Build context: apps/web/ (see .dockerignore).

# syntax=docker/dockerfile:1

# ---- dependencies ------------------------------------------------------------
FROM node:22-alpine AS deps

WORKDIR /app

# Match the npm major that generated/maintains package-lock.json (the
# local toolchain is npm 11; the one bundled with node:22 is older and
# resolves the lock differently).
RUN npm install -g npm@11

COPY package.json package-lock.json ./
RUN npm ci

# ---- build --------------------------------------------------------------------
FROM node:22-alpine AS build

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Public, build-time frontend configuration (see header). Defaults to the
# local convention; docker-compose.prod.yml passes the deployment's value.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}

RUN npm run build

# ---- runtime -------------------------------------------------------------------
FROM node:22-alpine

WORKDIR /app

ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Non-root runtime user.
RUN addgroup -S -g 1001 nodejs && adduser -S -u 1001 -G nodejs nextjs

# Standalone server + traced files, then the two things output tracing is
# known to miss: static assets and the i18n message catalogs (loaded via
# a dynamic import, see next.config.ts outputFileTracingIncludes and
# apps/web/i18n/request.ts). There is no public/ directory in this app.
COPY --from=build --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=build --chown=nextjs:nodejs /app/messages ./messages

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
