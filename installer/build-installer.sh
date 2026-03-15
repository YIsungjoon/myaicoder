#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSTALLER_DIR="$REPO_ROOT/installer"
OUTPUT_DIR="$REPO_ROOT/dist/myaicoder-setup"

echo "=== Building myAiCoder Installer Package ==="
echo ""

# Clean previous build
rm -rf "$OUTPUT_DIR" "$REPO_ROOT/dist/myaicoder-setup.zip"
mkdir -p "$OUTPUT_DIR"

# ── 1. Frozen binary 빌드 ──
echo "[1/4] Building frozen binary..."
cd "$REPO_ROOT/services/myaicoder"
uv run pyinstaller "$INSTALLER_DIR/myaicoder.spec" \
    --distpath "$OUTPUT_DIR" \
    --workpath /tmp/pyinstaller-build \
    -y 2>&1 | tail -3
BINARY_SIZE=$(du -h "$OUTPUT_DIR/myaicoder" | cut -f1)
echo "      → myaicoder binary: $BINARY_SIZE"

# ── 2. Extension 빌드 ──
echo ""
echo "[2/4] Building VS Code Extension..."
cd "$REPO_ROOT/apps/vscode-extension"
npm run build 2>&1 | tail -1
npx @vscode/vsce package --no-dependencies -o "$OUTPUT_DIR/myaicoder-1.0.1.vsix" 2>&1 | tail -1
echo "      → myaicoder-1.0.1.vsix"

# ── 3. 설치 파일 복사 ──
echo ""
echo "[3/4] Copying installer files..."
cp "$INSTALLER_DIR/config.json" "$OUTPUT_DIR/"
cp "$INSTALLER_DIR/install.bat" "$OUTPUT_DIR/설치하기.bat"
cp "$INSTALLER_DIR/install.command" "$OUTPUT_DIR/설치하기.command"
chmod +x "$OUTPUT_DIR/설치하기.command"
cp "$INSTALLER_DIR/README.txt" "$OUTPUT_DIR/"
echo "      → config.json, 설치하기.bat, 설치하기.command, README.txt"

# ── 4. ZIP 패키지 생성 ──
echo ""
echo "[4/4] Creating zip package..."
cd "$REPO_ROOT/dist"
zip -r myaicoder-setup.zip myaicoder-setup/
ZIP_SIZE=$(du -h myaicoder-setup.zip | cut -f1)

echo ""
echo "=== Build Complete ==="
echo ""
echo "  Package: $REPO_ROOT/dist/myaicoder-setup.zip ($ZIP_SIZE)"
echo "  Contents:"
ls -lh "$OUTPUT_DIR/" | awk 'NR>1 {printf "    %-30s %s\n", $NF, $5}'
echo ""
echo "  배포 전 config.json의 server_url을 DGX 서버 IP로 수정하세요."
