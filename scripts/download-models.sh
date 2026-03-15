#!/usr/bin/env bash
set -euo pipefail

MODELS_DIR="${MODELS_DIR:-$HOME/models}"
mkdir -p "$MODELS_DIR"

# Model definitions: name|filename|repo|size
MODELS=(
    "Qwen3.5-9B|Qwen3.5-9B-Q4_K_M.gguf|unsloth/Qwen3.5-9B-GGUF|~6GB"
    "Qwen3.5-27B|Qwen3.5-27B-Q4_K_M.gguf|unsloth/Qwen3.5-27B-GGUF|~17GB"
    "Qwen3-Coder-30B|Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf|unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF|~18GB"
)

echo "=== Model Download ==="
echo "Target directory: $MODELS_DIR"
echo ""

for entry in "${MODELS[@]}"; do
    IFS='|' read -r name filename repo size <<< "$entry"
    filepath="$MODELS_DIR/$filename"

    if [ -f "$filepath" ]; then
        echo "[SKIP] $name already exists ($filepath)"
        continue
    fi

    echo "[DOWNLOAD] $name ($size)"
    echo "  From: https://huggingface.co/$repo"

    if command -v huggingface-cli &>/dev/null; then
        huggingface-cli download "$repo" "$filename" \
            --local-dir "$MODELS_DIR" --local-dir-use-symlinks False
    else
        echo "  huggingface-cli not found, using curl..."
        curl -L -o "$filepath" \
            "https://huggingface.co/$repo/resolve/main/$filename"
    fi

    echo "  Done: $filepath"
    echo ""
done

# Ensure read permission for Docker volume mount (EC-D8-D)
chmod 644 "$MODELS_DIR"/*.gguf 2>/dev/null || true

echo ""
echo "=== Download Complete ==="
ls -lh "$MODELS_DIR"/*.gguf 2>/dev/null || echo "No .gguf files found"
