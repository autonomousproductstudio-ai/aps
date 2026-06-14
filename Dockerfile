# Single same-origin image: build the Vite SPA, then serve it from FastAPI alongside the API.
# Stage 1 compiles frontend/dist; stage 2 is the Python runtime that imports aps.api.main:app
# (which serves that dist — see the SPA catch-all in src/aps/api/main.py).

# ---- Stage 1: build the React/Vite SPA ----
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./

# Firebase web config — Vite inlines VITE_* vars present in the env at build time. Pass these
# as Railway build variables (Settings -> Variables, available to the build) and they flow
# through these ARGs. Unset -> empty (Firebase auth simply stays uninitialized, API still works).
ARG VITE_FIREBASE_API_KEY=""
ARG VITE_FIREBASE_AUTH_DOMAIN=""
ARG VITE_FIREBASE_PROJECT_ID=""
ARG VITE_FIREBASE_STORAGE_BUCKET=""
ARG VITE_FIREBASE_MESSAGING_SENDER_ID=""
ARG VITE_FIREBASE_APP_ID=""
# Optional: override to point the SPA at a different API host. Empty -> relative same-origin.
ARG VITE_API_BASE=""
ENV VITE_FIREBASE_API_KEY=$VITE_FIREBASE_API_KEY \
    VITE_FIREBASE_AUTH_DOMAIN=$VITE_FIREBASE_AUTH_DOMAIN \
    VITE_FIREBASE_PROJECT_ID=$VITE_FIREBASE_PROJECT_ID \
    VITE_FIREBASE_STORAGE_BUCKET=$VITE_FIREBASE_STORAGE_BUCKET \
    VITE_FIREBASE_MESSAGING_SENDER_ID=$VITE_FIREBASE_MESSAGING_SENDER_ID \
    VITE_FIREBASE_APP_ID=$VITE_FIREBASE_APP_ID \
    VITE_API_BASE=$VITE_API_BASE

# Relative API base (VITE_API_BASE unset -> '') so the SPA calls /v1 + /api on this same host.
RUN npm run build

# ---- Stage 2: Python runtime ----
FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

# Deps first for layer caching. requirements.txt mirrors pyproject's runtime deps.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# App source (src layout -> importable via PYTHONPATH=/app/src) + built SPA from stage 1.
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY --from=frontend /app/frontend/dist ./frontend/dist

EXPOSE 8011
# Railway injects $PORT; default 8011 for local `docker run`.
CMD ["sh", "-c", "uvicorn aps.api.main:app --host 0.0.0.0 --port ${PORT:-8011}"]
