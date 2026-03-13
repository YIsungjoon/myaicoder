#!/bin/bash
# Start vLLM server with Qwen3.5-27B INT4
#
# Prerequisites:
#   pip install vllm
#
# Usage:
#   ./scripts/start_vllm.sh
#   ./scripts/start_vllm.sh --port 8080
#   ./scripts/start_vllm.sh --model Qwen/Qwen3-32B

MODEL="${MODEL:-Qwen/Qwen3.5-27B-INT4}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8080}"

echo "Starting vLLM server..."
echo "  Model: $MODEL"
echo "  Host:  $HOST"
echo "  Port:  $PORT"
echo ""

vllm serve "$MODEL" \
    --host "$HOST" \
    --port "$PORT" \
    --dtype auto \
    --max-model-len 32768 \
    "$@"
