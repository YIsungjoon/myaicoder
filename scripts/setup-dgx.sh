#!/usr/bin/env bash
set -euo pipefail

echo "=== myAiCoder DGX Setup ==="

# P0: 사전 체크
echo "[1/5] Checking system requirements..."

# P0-1: Architecture
ARCH=$(uname -m)
if [ "$ARCH" != "aarch64" ]; then
    echo "WARNING: Expected aarch64, got $ARCH"
fi

# P0-2: NVIDIA Driver
if ! command -v nvidia-smi &>/dev/null; then
    echo "ERROR: nvidia-smi not found. Install NVIDIA drivers."
    exit 1
fi
echo "  GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)"
echo "  CUDA: $(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)"

# P0-3: NVIDIA Container Toolkit
if ! command -v nvidia-ctk &>/dev/null; then
    echo "ERROR: nvidia-container-toolkit not installed."
    echo "  Install: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
    exit 1
fi
echo "  Container Toolkit: $(nvidia-ctk --version 2>/dev/null || echo 'installed')"

# P0-4: Docker
if ! command -v docker &>/dev/null; then
    echo "ERROR: Docker not installed."
    exit 1
fi
echo "  Docker: $(docker --version)"

# P0-5: Docker GPU test
echo ""
echo "[2/5] Testing Docker GPU access..."
if ! docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu24.04 nvidia-smi &>/dev/null; then
    echo "ERROR: Docker cannot access GPU."
    echo "  Check: nvidia-container-toolkit configuration"
    exit 1
fi
echo "  Docker GPU: OK"

# Setup .env.prod
echo ""
echo "[3/5] Creating .env.prod..."
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ ! -f "$REPO_ROOT/.env.prod" ]; then
    cp "$REPO_ROOT/.env.prod.example" "$REPO_ROOT/.env.prod"
    # Generate secrets
    INTERNAL_TOKEN=$(openssl rand -base64 32)
    sed -i "s|<generate-with-openssl-rand-base64-32>|${INTERNAL_TOKEN}|" "$REPO_ROOT/.env.prod"
    DB_PASS=$(openssl rand -base64 16)
    sed -i "s|<generate-secure-password>|${DB_PASS}|g" "$REPO_ROOT/.env.prod"
    echo "  Created .env.prod (review and update API key hash!)"
else
    echo "  .env.prod already exists, skipping"
fi

# Create models directory
echo ""
echo "[4/5] Checking models directory..."
MODELS_DIR="${MODELS_DIR:-$HOME/models}"
mkdir -p "$MODELS_DIR"
echo "  Models dir: $MODELS_DIR"

# Build images
echo ""
echo "[5/5] Building Docker images..."
cd "$REPO_ROOT"
docker compose -f docker-compose.prod.yml build

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Download models:  ./scripts/download-models.sh"
echo "  2. Review config:    nano .env.prod"
echo "  3. Start services:   docker compose -f docker-compose.prod.yml up -d"
