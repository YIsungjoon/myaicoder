#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODELS_DIR="${MODELS_DIR:-$HOME/models}"
HF_MODEL_REPO="Qwen/Qwen3.5-9B-GGUF"
HF_MODEL_FILE="Qwen3.5-9B-Q4_K_M.gguf"

echo "=== myAiCoder Dev Setup ==="
echo ""

# ── 1. Config 복사 (멱등: 기존 파일 보호) ──
echo "[1/5] Config files..."
if [ ! -f "$REPO_ROOT/config/gateway.yaml" ]; then
    cp "$REPO_ROOT/config/gateway.yaml.example" "$REPO_ROOT/config/gateway.yaml"
    echo "  Created config/gateway.yaml — EDIT THIS: set API key hash and internal token!"
else
    echo "  config/gateway.yaml already exists, skipped"
fi

if [ ! -f "$REPO_ROOT/config/models.yaml" ]; then
    cp "$REPO_ROOT/config/models.yaml.example" "$REPO_ROOT/config/models.yaml"
    echo "  Created config/models.yaml"
else
    echo "  config/models.yaml already exists, skipped"
fi

if [ ! -f "$REPO_ROOT/.env" ]; then
    cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
    echo "  Created .env"
else
    echo "  .env already exists, skipped"
fi

# ── 2. Python 의존성 ──
echo ""
echo "[2/5] Python dependencies..."
if command -v uv &>/dev/null; then
    (cd "$REPO_ROOT/services/myaicoder" && uv sync --extra dev 2>&1 | tail -1)
    (cd "$REPO_ROOT/services/gateway" && uv sync --extra dev 2>&1 | tail -1)
    echo "  Dependencies synced"
else
    echo "  ERROR: uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# ── 3. CLI 설치 ──
echo ""
echo "[3/5] Installing myaicoder CLI..."
(cd "$REPO_ROOT/services/myaicoder" && uv pip install -e . -q)
echo "  CLI installed"

# ── 4. 모델 다운로드 (없는 경우에만) ──
echo ""
echo "[4/5] Checking model files..."
mkdir -p "$MODELS_DIR"
MODEL_FILE="$MODELS_DIR/$HF_MODEL_FILE"
if [ -f "$MODEL_FILE" ]; then
    echo "  Model already exists: $MODEL_FILE ($(du -h "$MODEL_FILE" | cut -f1))"
else
    echo "  Model not found: $MODEL_FILE"
    if command -v huggingface-cli &>/dev/null; then
        echo "  Downloading $HF_MODEL_FILE from $HF_MODEL_REPO (~6GB)..."
        huggingface-cli download "$HF_MODEL_REPO" "$HF_MODEL_FILE" \
            --local-dir "$MODELS_DIR" --local-dir-use-symlinks False
    else
        echo "  huggingface-cli not found."
        echo "  Option 1: pip install huggingface-hub && re-run this script"
        echo "  Option 2: Download manually from https://huggingface.co/$HF_MODEL_REPO"
        echo "  Place the .gguf file in: $MODELS_DIR/"
    fi
fi

# ── 5. 검증 ──
echo ""
echo "[5/5] Verifying setup..."
echo ""

OK=0
WARN=0

check() {
    local label="$1" cmd="$2"
    if eval "$cmd" &>/dev/null; then
        echo "  [OK]   $label"
        OK=$((OK + 1))
    else
        echo "  [WARN] $label"
        WARN=$((WARN + 1))
    fi
}

check "myaicoder CLI"    "command -v myaicoder"
check "Gateway config"   "[ -f '$REPO_ROOT/config/gateway.yaml' ]"
check "Models config"    "[ -f '$REPO_ROOT/config/models.yaml' ]"
check "Model file"       "[ -f '$MODEL_FILE' ]"
check "llama-server"     "command -v llama-server || [ -n '${LLAMA_SERVER_PATH:-}' ]"

echo ""
echo "=== Setup complete ($OK OK, $WARN warnings) ==="
echo ""

if [ "$WARN" -gt 0 ]; then
    echo "Fix warnings above, then:"
fi

echo "Next steps:"
echo "  1. Edit config/gateway.yaml (set API key hash)"
echo "  2. Run: scripts/start-all.sh"
echo "  3. Install VS Code extension (.vsix)"
echo ""
echo "Or for server mode (DGX):"
echo "  1. Install CLI: pip install -e services/myaicoder/"
echo "  2. Install .vsix in VS Code"
echo "  3. Set VS Code setting: myaicoder.llmUrl → http://dgx-server:8080"
