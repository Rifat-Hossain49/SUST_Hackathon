#!/usr/bin/env bash
set -euo pipefail

IMAGE="${1:-${IMAGE:-}}"
CONTAINER_NAME="${2:-${CONTAINER_NAME:-qsi}}"
HOST_PORT="${3:-${HOST_PORT:-8011}}"
CONTAINER_PORT="${CONTAINER_PORT:-8000}"
APP_DIR="${APP_DIR:-$HOME/queuestorm-investigator}"
RUNTIME_ENV="${RUNTIME_ENV:-$APP_DIR/runtime.env}"

if [ -z "$IMAGE" ]; then
  echo "IMAGE is required" >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed on this VM." >&2
  exit 2
fi

mkdir -p "$APP_DIR"
if [ ! -f "$RUNTIME_ENV" ]; then
  cat > "$RUNTIME_ENV" <<EOF
PORT=$CONTAINER_PORT
USE_LLM=false
MODEL_NAME=gemini-3.5-flash
LLM_TIMEOUT_SECONDS=4.0
LLM_MAX_TOKENS=600
EOF
fi
chmod 600 "$RUNTIME_ENV" || true

echo "Pulling $IMAGE"
docker pull "$IMAGE"

echo "Replacing container $CONTAINER_NAME"
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  --env-file "$RUNTIME_ENV" \
  -p "$HOST_PORT:$CONTAINER_PORT" \
  "$IMAGE"

echo "Waiting for health check on http://127.0.0.1:$HOST_PORT/health"
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:$HOST_PORT/health" >/dev/null; then
    echo "Deployment healthy."
    docker ps --filter "name=$CONTAINER_NAME"
    exit 0
  fi
  sleep 2
done

echo "Deployment failed health check. Last logs:" >&2
docker logs --tail 80 "$CONTAINER_NAME" >&2 || true
exit 1
