#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG="$SCRIPT_DIR/config.json"

echo "========================================"
echo "  myAiCoder 설치 프로그램"
echo "========================================"
echo ""

# ── 1. config.json 읽기 ──
if [ ! -f "$CONFIG" ]; then
    echo "[오류] config.json 파일을 찾을 수 없습니다."
    read -rp "아무 키나 눌러 종료..."
    exit 1
fi

SERVER_URL=$(python3 -c "import json; print(json.load(open('$CONFIG'))['server_url'])")
INSTALL_DIR_NAME=$(python3 -c "import json; print(json.load(open('$CONFIG'))['install_dir_name'])")
MODEL_NAME=$(python3 -c "import json; print(json.load(open('$CONFIG'))['model_name'])")
VSIX_FILE=$(python3 -c "import json; print(json.load(open('$CONFIG'))['extension_file'])")

INSTALL_DIR="$HOME/$INSTALL_DIR_NAME"

# ── 2. 바이너리 복사 ──
echo "[1/4] myAiCoder CLI 설치 중..."
mkdir -p "$INSTALL_DIR"
cp "$SCRIPT_DIR/myaicoder" "$INSTALL_DIR/myaicoder"
chmod +x "$INSTALL_DIR/myaicoder"
xattr -cr "$INSTALL_DIR/myaicoder" 2>/dev/null || true
echo "      → $INSTALL_DIR/myaicoder"

# ── 3. PATH 추가 ──
echo "[2/4] PATH 설정 중..."
SHELL_RC="$HOME/.zshrc"
if [ -f "$HOME/.bash_profile" ] && [ ! -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.bash_profile"
fi

if grep -q "$INSTALL_DIR_NAME" "$SHELL_RC" 2>/dev/null; then
    echo "      → 이미 PATH에 있음"
else
    echo "" >> "$SHELL_RC"
    echo "# myAiCoder" >> "$SHELL_RC"
    echo "export PATH=\"\$HOME/$INSTALL_DIR_NAME:\$PATH\"" >> "$SHELL_RC"
    echo "      → $SHELL_RC에 PATH 추가됨"
fi
export PATH="$INSTALL_DIR:$PATH"

# ── 4. VS Code Extension 설치 ──
echo "[3/4] VS Code Extension 설치 중..."
CODE_CMD=""
if command -v code &>/dev/null; then
    CODE_CMD="code"
elif [ -x "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" ]; then
    CODE_CMD="/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
fi

if [ -n "$CODE_CMD" ]; then
    "$CODE_CMD" --install-extension "$SCRIPT_DIR/$VSIX_FILE" --force 2>/dev/null
    echo "      → Extension 설치 완료"
else
    echo "      [경고] VS Code를 찾을 수 없습니다."
    echo "      VS Code 설치 후 수동으로 .vsix를 설치해주세요."
    echo "      (Extensions 탭 > ... > Install from VSIX)"
fi

# ── 5. VS Code settings.json 주입 ──
echo "[4/4] VS Code 설정 중..."
SETTINGS_DIR="$HOME/Library/Application Support/Code/User"
SETTINGS_FILE="$SETTINGS_DIR/settings.json"

mkdir -p "$SETTINGS_DIR"

python3 -c "
import json, os

settings_file = os.path.expanduser('$SETTINGS_FILE')
settings = {}
if os.path.exists(settings_file):
    with open(settings_file) as f:
        try:
            settings = json.load(f)
        except json.JSONDecodeError:
            settings = {}

settings['myaicoder.llmUrl'] = '$SERVER_URL'
settings['myaicoder.modelName'] = '$MODEL_NAME'
settings['myaicoder.executablePath'] = os.path.expanduser('$INSTALL_DIR/myaicoder')

with open(settings_file, 'w') as f:
    json.dump(settings, f, indent=4, ensure_ascii=False)
"
echo "      → 서버 URL: $SERVER_URL"

echo ""
echo "========================================"
echo "  설치가 완료되었습니다!"
echo "  VS Code를 켜고 왼쪽 바의 myAiCoder를"
echo "  클릭하면 바로 사용할 수 있습니다."
echo "========================================"
echo ""
read -rp "아무 키나 눌러 종료..."
