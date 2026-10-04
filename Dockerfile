# ==============================================================================
# PracPrep Frontend Dockerfile (Multi-Stage Build)
# Node.js 20 Alpine (Vite + React Build) -> Nginx 1.27 Alpine (Static Serving & Reverse Proxy)
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build Static Web Application
# ------------------------------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependency manifests first to leverage Docker layer caching
COPY package.json package-lock.json ./

# Install exact npm dependencies cleanly
RUN npm ci

# Copy configuration, typing, and source files required for production bundle
COPY index.html tsconfig.json tsconfig.app.json tsconfig.node.json vite.config.ts components.json ./
COPY public/ public/
COPY src/ src/

# Build argument for same-origin API requests (defaults to empty string for Nginx reverse proxy)
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# Compile TypeScript and build production bundle using Vite
RUN npm run build


# ------------------------------------------------------------------------------
# Stage 2: Production Nginx Server
# ------------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

# Remove default Nginx site configuration
RUN rm -f /etc/nginx/conf.d/default.conf

# Copy custom Nginx configuration with SPA fallback and API reverse proxy
COPY deployment/nginx/default.conf /etc/nginx/conf.d/default.conf

# Copy compiled static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

# Health check verifying Nginx is responding on HTTP port 80
HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=5s \
    CMD wget -q --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
