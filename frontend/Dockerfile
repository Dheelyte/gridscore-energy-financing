# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# GridScore frontend image — build the SPA with Node, serve static with nginx.
# VITE_API_BASE_URL is baked at build time (Vite inlines env at compile).
# ---------------------------------------------------------------------------
FROM node:22-slim AS builder

WORKDIR /app

# Install deps with a cached layer.
COPY package.json package-lock.json* ./
RUN npm ci || npm install

COPY . .

ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

# ---------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -qO- http://localhost/ >/dev/null 2>&1 || exit 1

CMD ["nginx", "-g", "daemon off;"]
