#!/usr/bin/env bash
#
# Deploy HomeCam Server — called by GitHub Actions on the self-hosted runner.
#
# Usage: deploy.sh <commit-sha>
#
# Env:
#   IMAGE_REGISTRY  — GHCR path, e.g. ghcr.io/rizqikevin/homecam-server
#
# Behaviour:
#   1. Refuse to deploy while camera is recording.
#   2. Pull exact SHA-pinned images from GHCR.
#   3. Recreate containers via docker compose (prod override).
#   4. Wait for health check (up to 60 s).
#   5. Rollback to previous images on failure.
#
set -euo pipefail

SHA="${1:?Usage: deploy.sh <commit-sha>}"
REGISTRY="${IMAGE_REGISTRY:?Set IMAGE_REGISTRY}"

BACKEND_IMAGE="${REGISTRY}/backend:${SHA}"
FRONTEND_IMAGE="${REGISTRY}/frontend:${SHA}"

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
HEALTH_URL="http://127.0.0.1:8005/api/health"
MAX_ATTEMPTS=12
SLEEP_SECONDS=5

# ── Helpers ──────────────────────────────────────────────────────────────

log()  { printf '[deploy] %s\n' "$*"; }
die()  { log "ERROR: $*"; exit 1; }

# ── 1. Recording guard ──────────────────────────────────────────────────

if docker ps --format '{{.Names}}' | grep -q '^homecam-backend$'; then
  RECORDING=$(docker exec homecam-backend python3 -c \
    "import sys; sys.path.insert(0,'/app'); from app.main import camera; print(int(camera.recording))" \
    2>/dev/null || echo 0)
  if [ "$RECORDING" = "1" ]; then
    die "Active recording in progress — deploy aborted"
  fi
  log "Recording guard passed (idle)"
else
  log "Backend container not running — skipping recording guard"
fi

# ── 2. Save previous images for rollback ────────────────────────────────

PREV_BACKEND=$(docker inspect homecam-backend --format='{{.Config.Image}}' 2>/dev/null || echo "")
PREV_FRONTEND=$(docker inspect homecam-frontend --format='{{.Config.Image}}' 2>/dev/null || echo "")

# ── 3. Pull new images ──────────────────────────────────────────────────

log "Pulling ${BACKEND_IMAGE}"
docker pull "$BACKEND_IMAGE"

log "Pulling ${FRONTEND_IMAGE}"
docker pull "$FRONTEND_IMAGE"

# ── 4. Recreate containers ──────────────────────────────────────────────

export BACKEND_IMAGE FRONTEND_IMAGE

log "Starting containers (SHA: ${SHA})"
$COMPOSE up -d --force-recreate --remove-orphans --no-build 2>&1

# ── 5. Health check ─────────────────────────────────────────────────────

log "Waiting for health check (${MAX_ATTEMPTS}×${SLEEP_SECONDS}s)..."
HEALTHY=false
for i in $(seq 1 "$MAX_ATTEMPTS"); do
  STATUS=$(curl -sf "$HEALTH_URL" 2>/dev/null \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" \
    2>/dev/null || echo "")
  if [ "$STATUS" = "ok" ]; then
    log "Health OK after $((i * SLEEP_SECONDS))s"
    HEALTHY=true
    break
  fi
  sleep "$SLEEP_SECONDS"
done

if [ "$HEALTHY" = true ]; then
  log "Deploy successful: ${SHA}"
  exit 0
fi

# ── 6. Rollback ─────────────────────────────────────────────────────────

log "Health check failed after $((MAX_ATTEMPTS * SLEEP_SECONDS))s — rolling back"

if [ -n "$PREV_BACKEND" ] && [ -n "$PREV_FRONTEND" ]; then
  export BACKEND_IMAGE="$PREV_BACKEND"
  export FRONTEND_IMAGE="$PREV_FRONTEND"
  log "Restoring ${PREV_BACKEND} / ${PREV_FRONTEND}"
  $COMPOSE up -d --force-recreate --no-build 2>&1

  # Brief wait for rollback health
  sleep 10
  ROLLBACK_STATUS=$(curl -sf "$HEALTH_URL" 2>/dev/null \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" \
    2>/dev/null || echo "")
  if [ "$ROLLBACK_STATUS" = "ok" ]; then
    log "Rollback healthy"
  else
    log "WARNING: Rollback health check also failed"
  fi
else
  log "No previous images recorded — cannot rollback"
fi

die "Deploy failed for ${SHA}"
