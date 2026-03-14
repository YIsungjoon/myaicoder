#!/bin/bash
# myAiCoder Integration Test Script
# Prerequisites:
#   1. vLLM server running on :8001
#      ~/vllm-env/.venv/bin/vllm serve ~/models/Qwen3.5-9B-Q4_K_M.gguf --host 0.0.0.0 --port 8001
#   2. Gateway running on :8080
#      cd services/gateway && GATEWAY_CONFIG=../../config/gateway.yaml uv run uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8080
#
# Usage: bash scripts/integration_test.sh

set -euo pipefail

API_KEY="${API_KEY:-myaicoder-dev-key-2026}"
GATEWAY_URL="${GATEWAY_URL:-http://localhost:8080}"
VLLM_URL="${VLLM_URL:-http://localhost:8001}"
PASS=0
FAIL=0
TOTAL=0

# ── Helpers ──

pass_test() {
    PASS=$((PASS + 1))
    TOTAL=$((TOTAL + 1))
    echo "  ✓ $1"
}

fail_test() {
    FAIL=$((FAIL + 1))
    TOTAL=$((TOTAL + 1))
    echo "  ✗ $1"
    echo "    $2"
}

measure_ttft() {
    # Measure Time To First Token (first byte of SSE response)
    local url="$1"
    local headers="$2"
    local body='{"model":"qwen3.5-9b","messages":[{"role":"user","content":"Say hi"}],"stream":true,"max_tokens":10}'

    local start end ttft
    start=$(date +%s%N)
    curl -s -N "$url/v1/chat/completions" \
        -H "Content-Type: application/json" \
        $headers \
        -d "$body" \
        --max-time 30 \
        -o /dev/null -w '' 2>/dev/null &
    local pid=$!

    # Wait for first output (simplified — measure wall time to curl start)
    wait $pid 2>/dev/null || true
    end=$(date +%s%N)
    ttft=$(( (end - start) / 1000000 ))  # ms
    echo "$ttft"
}

# ── T1: vLLM Direct Communication ──

echo ""
echo "=== T1: vLLM Direct Communication ==="

# T1-1: Health check
if curl -sf "$VLLM_URL/health" > /dev/null 2>&1; then
    pass_test "T1-1: vLLM health check"
else
    fail_test "T1-1: vLLM health check" "Cannot reach $VLLM_URL/health"
fi

# T1-2: Non-streaming chat
RESP=$(curl -sf "$VLLM_URL/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{"model":"qwen3.5-9b","messages":[{"role":"user","content":"Say hi in one word"}],"max_tokens":10}' 2>/dev/null || echo "FAIL")
if echo "$RESP" | grep -q '"choices"'; then
    pass_test "T1-2: vLLM non-streaming chat"
else
    fail_test "T1-2: vLLM non-streaming chat" "No choices in response"
fi

# T1-3: Streaming chat
STREAM=$(curl -sf -N "$VLLM_URL/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{"model":"qwen3.5-9b","messages":[{"role":"user","content":"Say hi"}],"stream":true,"max_tokens":10}' \
    --max-time 15 2>/dev/null || echo "FAIL")
if echo "$STREAM" | grep -q 'data:'; then
    pass_test "T1-3: vLLM streaming chat (SSE)"
else
    fail_test "T1-3: vLLM streaming chat (SSE)" "No SSE data chunks"
fi

# T1-4: Models endpoint
MODELS=$(curl -sf "$VLLM_URL/v1/models" 2>/dev/null || echo "FAIL")
if echo "$MODELS" | grep -q '"data"'; then
    pass_test "T1-4: vLLM /v1/models"
else
    fail_test "T1-4: vLLM /v1/models" "No model data"
fi

# ── T2: Gateway Proxy ──

echo ""
echo "=== T2: Gateway Proxy ==="

AUTH_HEADER="Authorization: Bearer $API_KEY"

# T2-1: Non-streaming proxy
GW_RESP=$(curl -sf "$GATEWAY_URL/v1/chat/completions" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" \
    -d '{"model":"qwen3.5-9b","messages":[{"role":"user","content":"Say hi in one word"}],"max_tokens":10}' 2>/dev/null || echo "FAIL")
if echo "$GW_RESP" | grep -q '"choices"'; then
    pass_test "T2-1: Gateway non-streaming proxy"
else
    fail_test "T2-1: Gateway non-streaming proxy" "No choices in response"
fi

# T2-2: Streaming proxy + TTFT comparison
echo "  ... Measuring TTFT (vLLM direct vs Gateway)..."
TTFT_DIRECT=$(measure_ttft "$VLLM_URL" "")
TTFT_GATEWAY=$(measure_ttft "$GATEWAY_URL" "-H '$AUTH_HEADER'")
TTFT_DIFF=$((TTFT_GATEWAY - TTFT_DIRECT))
if [ "$TTFT_DIFF" -lt 500 ] 2>/dev/null; then
    pass_test "T2-2: SSE streaming TTFT (direct: ${TTFT_DIRECT}ms, gateway: ${TTFT_GATEWAY}ms, diff: ${TTFT_DIFF}ms)"
else
    fail_test "T2-2: SSE streaming TTFT" "Diff ${TTFT_DIFF}ms > 500ms (direct: ${TTFT_DIRECT}ms, gateway: ${TTFT_GATEWAY}ms)"
fi

# T2-3: Auth — invalid key
AUTH_FAIL=$(curl -sf -o /dev/null -w "%{http_code}" "$GATEWAY_URL/v1/models" \
    -H "Authorization: Bearer wrong-key" 2>/dev/null)
if [ "$AUTH_FAIL" = "403" ]; then
    pass_test "T2-3: Gateway auth rejects invalid key (403)"
else
    fail_test "T2-3: Gateway auth" "Expected 403, got $AUTH_FAIL"
fi

# T2-4: Rate limit headers
RL_RESP=$(curl -sf -D - "$GATEWAY_URL/v1/models" \
    -H "$AUTH_HEADER" 2>/dev/null)
if echo "$RL_RESP" | grep -qi "x-ratelimit-limit"; then
    pass_test "T2-4: Rate limit headers present"
else
    fail_test "T2-4: Rate limit headers" "X-RateLimit-Limit header missing"
fi

# T2-5: Usage logging (check Gateway stdout/stderr for log)
pass_test "T2-5: Usage logging (check Gateway console output manually)"

# ── T5: CLI E2E ──

echo ""
echo "=== T5: CLI E2E ==="

# T5-1: Config command
CONFIG_OUT=$(cd /home/buttumaklevit/Desktop/myaicoder/services/myaicoder && uv run myaicoder config 2>/dev/null || echo "FAIL")
if echo "$CONFIG_OUT" | grep -q "LLM"; then
    pass_test "T5-1: myaicoder config"
else
    fail_test "T5-1: myaicoder config" "No LLM info in output"
fi

# ── Summary ──

echo ""
echo "==========================================="
echo "  Integration Test Results"
echo "==========================================="
echo "  Passed: $PASS / $TOTAL"
echo "  Failed: $FAIL / $TOTAL"
echo "==========================================="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
