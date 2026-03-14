#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Load .env if exists
if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    source "$REPO_ROOT/.env"
    set +a
fi

MODELS_DIR="${MODELS_DIR:-$HOME/models}"
LLAMA_PORT="${LLAMA_PORT:-8001}"
GATEWAY_PORT="${GATEWAY_PORT:-8080}"
MODEL_FILE="${MODELS_DIR}/Qwen3.5-9B-Q4_K_M.gguf"

# Resolve llama-server path (3-tier fallback)
if [ -n "${LLAMA_SERVER_PATH:-}" ]; then
    LLAMA_CMD="$LLAMA_SERVER_PATH"
elif command -v llama-server &>/dev/null; then
    LLAMA_CMD="llama-server"
else
    echo "ERROR: llama-server not found."
    echo "  Set LLAMA_SERVER_PATH in .env or add llama-server to PATH"
    exit 1
fi

# Verify model exists
if [ ! -f "$MODEL_FILE" ]; then
    echo "ERROR: Model not found: $MODEL_FILE"
    echo "  Run scripts/setup-dev.sh first"
    exit 1
fi

echo "=== Starting myAiCoder Services ==="
echo ""

# ── 1. LLM Server ──
echo "[1/2] Starting LLM server on port $LLAMA_PORT..."
$LLAMA_CMD \
    --model "$MODEL_FILE" \
    --host 0.0.0.0 --port "$LLAMA_PORT" \
    --n-gpu-layers -1 --ctx-size 32768 &
LLM_PID=$!

echo "  Waiting for LLM server (PID: $LLM_PID)..."
for i in $(seq 1 30); do
    if curl -sf "http://localhost:$LLAMA_PORT/health" >/dev/null 2>&1; then
        echo "  LLM server ready!"
        break
    fi
    if ! kill -0 "$LLM_PID" 2>/dev/null; then
        echo "  ERROR: LLM server process died"
        exit 1
    fi
    sleep 1
done

# ── 2. Gateway ──
echo ""
echo "[2/2] Starting Gateway on port $GATEWAY_PORT..."
cd "$REPO_ROOT/services/gateway"
GATEWAY_CONFIG="${GATEWAY_CONFIG:-$REPO_ROOT/config/gateway.yaml}" \
    uv run uvicorn app.main:create_app --factory \
    --host 0.0.0.0 --port "$GATEWAY_PORT" &
GW_PID=$!

sleep 2
echo ""
echo "=== Services Running ==="
echo "  LLM Server: http://localhost:$LLAMA_PORT (PID: $LLM_PID)"
echo "  Gateway:    http://localhost:$GATEWAY_PORT (PID: $GW_PID)"
echo ""
echo "  Health check: curl http://localhost:$GATEWAY_PORT/health"
echo "  Metrics:      curl http://localhost:$GATEWAY_PORT/metrics"
echo ""
echo "Press Ctrl+C to stop all services"

# Graceful shutdown
cleanup() {
    echo ""
    echo "Stopping services..."
    kill "$GW_PID" 2>/dev/null || true
    kill "$LLM_PID" 2>/dev/null || true
    wait "$GW_PID" 2>/dev/null || true
    wait "$LLM_PID" 2>/dev/null || true
    echo "All services stopped."
}
trap cleanup INT TERM
wait
