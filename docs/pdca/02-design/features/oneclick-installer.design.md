# Design: oneclick-installer

## 참조 문서
- Plan: `docs/pdca/01-plan/features/oneclick-installer.plan.md`
- PyInstaller 테스트: 빌드 성공 (25MB, 20초, hidden-import 자동 감지)

---

## 1. 설계 개요

비개발자가 더블클릭으로 myAiCoder를 설치하는 패키지.
**서버 모드 전제** — DGX에 LLM+Gateway가 이미 돌고 있고, 사용자 PC에는 VS Code만 필요.

### 변경 파일 목록

| # | 파일 | 작업 | 설계 항목 |
|---|------|------|----------|
| D1 | `installer/myaicoder.spec` | 신규 | PyInstaller spec (onefile) |
| D2 | `installer/config.json` | 신규 | 설치 설정 템플릿 |
| D3 | `installer/install.bat` | 신규 | Windows 설치 스크립트 |
| D4 | `installer/install.command` | 신규 | macOS 설치 스크립트 |
| D5 | `installer/build-installer.sh` | 신규 | 배포 패키지 빌드 스크립트 |
| D6 | `installer/README.txt` | 신규 | zip 내 설치 안내 |

### 배포 패키지 최종 구조

```
myaicoder-setup/
├── myaicoder (.exe)           25MB frozen binary
├── myaicoder-0.1.0.vsix       106KB Extension
├── config.json                서버 URL + 설치 경로
├── 설치하기.bat                Windows 더블클릭
├── 설치하기.command            macOS 더블클릭
└── README.txt                 설치 안내
```

---

## 2. D1: installer/myaicoder.spec

PyInstaller spec 파일. 테스트에서 검증된 옵션 기반.

```python
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ['../services/myaicoder/src/myaicoder/cli.py'],
    pathex=['../services/myaicoder/src'],
    binaries=[],
    datas=collect_data_files('certifi'),
    hiddenimports=[
        'myaicoder',
        'myaicoder.cli',
        'myaicoder.core',
        'myaicoder.core.engine',
        'myaicoder.core.config',
        'myaicoder.core.context',
        'myaicoder.core.conversation',
        'myaicoder.core.session',
        'myaicoder.llm',
        'myaicoder.llm.vllm_provider',
        'myaicoder.tools',
        'myaicoder.mcp',
        'myaicoder.models',
        'myaicoder.ui',
        'click',
        'rich',
        'openai',
        'httpx',
        'pydantic',
        'yaml',
        'aiofiles',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas,
    name='myaicoder',
    debug=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)
```

### 설계 결정

| 결정 | 이유 |
|------|------|
| `onefile` 모드 | 단일 파일 배포 (폴더 배포보다 단순) |
| `console=True` | `myaicoder serve`는 subprocess로 실행되므로 콘솔 필요 |
| `excludes` | tkinter, matplotlib 등 불필요한 대형 패키지 제외 |
| `collect_data_files('certifi')` | HTTPS 연결에 필요한 SSL 인증서 |
| `upx=True` | 바이너리 크기 추가 압축 (설치 시 UPX 있을 때만) |

### 검증 기준
- `pyinstaller installer/myaicoder.spec` 빌드 성공
- `dist/myaicoder --help` 정상 출력
- `dist/myaicoder serve --help` 정상 출력

---

## 3. D2: installer/config.json

서버 관리자가 배포 전에 편집하는 설정 파일.

```json
{
  "server_url": "http://dgx-server:8080",
  "install_dir_name": ".myaicoder",
  "model_name": "qwen3.5-9b",
  "extension_file": "myaicoder-0.1.0.vsix",
  "binary_name": "myaicoder"
}
```

| 필드 | 용도 | 기본값 |
|------|------|--------|
| `server_url` | Gateway URL → VS Code settings에 주입 | `http://dgx-server:8080` |
| `install_dir_name` | 바이너리 설치 폴더명 (홈 디렉토리 하위) | `.myaicoder` |
| `model_name` | VS Code settings에 주입할 모델명 | `qwen3.5-9b` |
| `extension_file` | .vsix 파일명 | `myaicoder-0.1.0.vsix` |
| `binary_name` | 바이너리 파일명 (OS별 자동 .exe 추가) | `myaicoder` |

### 검증 기준
- 유효한 JSON
- 서버 관리자가 `server_url`만 바꾸면 배포 가능

---

## 4. D3: installer/install.bat (Windows)

```batch
@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: ── 디테일 A: 관리자 권한 확인 (setx PATH에 필요) ──
net session >nul 2>&1
if errorlevel 1 (
    echo [안내] 관리자 권한이 필요합니다. 권한을 요청합니다...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ========================================
echo   myAiCoder 설치 프로그램
echo ========================================
echo.

:: ── 1. config.json 읽기 ──
set "SCRIPT_DIR=%~dp0"
set "CONFIG=%SCRIPT_DIR%config.json"

if not exist "%CONFIG%" (
    echo [오류] config.json 파일을 찾을 수 없습니다.
    pause
    exit /b 1
)

:: PowerShell로 JSON 파싱
for /f "delims=" %%i in ('powershell -Command "(Get-Content '%CONFIG%' | ConvertFrom-Json).server_url"') do set "SERVER_URL=%%i"
for /f "delims=" %%i in ('powershell -Command "(Get-Content '%CONFIG%' | ConvertFrom-Json).install_dir_name"') do set "INSTALL_DIR_NAME=%%i"
for /f "delims=" %%i in ('powershell -Command "(Get-Content '%CONFIG%' | ConvertFrom-Json).model_name"') do set "MODEL_NAME=%%i"
for /f "delims=" %%i in ('powershell -Command "(Get-Content '%CONFIG%' | ConvertFrom-Json).extension_file"') do set "VSIX_FILE=%%i"

set "INSTALL_DIR=%USERPROFILE%\%INSTALL_DIR_NAME%"

:: ── 2. 바이너리 복사 ──
echo [1/4] myAiCoder CLI 설치 중...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
copy /Y "%SCRIPT_DIR%myaicoder.exe" "%INSTALL_DIR%\myaicoder.exe" >nul
echo       → %INSTALL_DIR%\myaicoder.exe

:: ── 3. PATH 추가 (현재 사용자) ──
echo [2/4] PATH 설정 중...
set "CURRENT_PATH="
for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "CURRENT_PATH=%%b"
echo !CURRENT_PATH! | findstr /i /c:"%INSTALL_DIR%" >nul 2>&1
if errorlevel 1 (
    setx PATH "%INSTALL_DIR%;!CURRENT_PATH!" >nul 2>&1
    echo       → PATH에 추가됨
) else (
    echo       → 이미 PATH에 있음
)

:: ── 4. VS Code Extension 설치 ──
echo [3/4] VS Code Extension 설치 중...
where code >nul 2>&1
if errorlevel 1 (
    echo       [경고] VS Code가 설치되어 있지 않거나 PATH에 없습니다.
    echo       VS Code 설치 후 수동으로 .vsix를 설치해주세요.
) else (
    code --install-extension "%SCRIPT_DIR%%VSIX_FILE%" --force 2>nul
    echo       → Extension 설치 완료
)

:: ── 5. VS Code settings.json 주입 ──
echo [4/4] VS Code 설정 중...
set "SETTINGS_DIR=%APPDATA%\Code\User"
set "SETTINGS_FILE=%SETTINGS_DIR%\settings.json"

if not exist "%SETTINGS_DIR%" mkdir "%SETTINGS_DIR%"

if exist "%SETTINGS_FILE%" (
    :: 기존 settings.json에 myaicoder 설정 추가/업데이트
    powershell -Command ^
        "$s = Get-Content '%SETTINGS_FILE%' -Raw | ConvertFrom-Json; ^
         $s | Add-Member -NotePropertyName 'myaicoder.llmUrl' -NotePropertyValue '%SERVER_URL%' -Force; ^
         $s | Add-Member -NotePropertyName 'myaicoder.modelName' -NotePropertyValue '%MODEL_NAME%' -Force; ^
         $s | Add-Member -NotePropertyName 'myaicoder.executablePath' -NotePropertyValue '%INSTALL_DIR%\myaicoder.exe' -Force; ^
         $s | ConvertTo-Json -Depth 10 | Set-Content '%SETTINGS_FILE%' -Encoding UTF8"
) else (
    :: 새 settings.json 생성
    powershell -Command ^
        "@{ 'myaicoder.llmUrl'='%SERVER_URL%'; 'myaicoder.modelName'='%MODEL_NAME%'; 'myaicoder.executablePath'='%INSTALL_DIR%\myaicoder.exe' } | ConvertTo-Json | Set-Content '%SETTINGS_FILE%' -Encoding UTF8"
)
echo       → 서버 URL: %SERVER_URL%

echo.
echo ========================================
echo   설치가 완료되었습니다!
echo   VS Code를 켜고 왼쪽 바의 myAiCoder를
echo   클릭하면 바로 사용할 수 있습니다.
echo ========================================
echo.
pause
```

### 핵심 설계

| 항목 | 구현 |
|------|------|
| 관리자 권한 자동 상승 | `net session` 체크 → `Start-Process -Verb RunAs`로 자동 재시작 |
| JSON 파싱 | PowerShell `ConvertFrom-Json` (Windows 10+ 기본 내장) |
| PATH 추가 | `setx` (레지스트리 수정, 관리자 권한으로 안전 실행) |
| settings.json 주입 | `Add-Member -Force` (기존 키 업데이트, 다른 설정 보존) |
| 한글 지원 | `chcp 65001` (UTF-8 코드 페이지) |
| 멱등성 | PATH 중복 체크, Extension `--force` 플래그 |

### 검증 기준
- 더블클릭 시 4단계 순차 실행
- settings.json에 `myaicoder.llmUrl`, `myaicoder.executablePath` 설정됨
- 기존 settings.json의 다른 설정 보존

---

## 5. D4: installer/install.command (macOS)

```bash
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
    read -p "아무 키나 눌러 종료..."
    exit 1
fi

# python3 또는 osascript로 JSON 파싱 (macOS는 python3 기본 내장)
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
# macOS Gatekeeper 해제
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
# 디테일 C: code CLI 2차 폴백 (macOS 기본 설치 경로)
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

settings_file = '$SETTINGS_FILE'
settings = {}
if os.path.exists(settings_file):
    with open(settings_file) as f:
        try:
            settings = json.load(f)
        except json.JSONDecodeError:
            settings = {}

settings['myaicoder.llmUrl'] = '$SERVER_URL'
settings['myaicoder.modelName'] = '$MODEL_NAME'
settings['myaicoder.executablePath'] = '$INSTALL_DIR/myaicoder'

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
read -p "아무 키나 눌러 종료..."
```

### macOS 고려사항

| 항목 | 대응 |
|------|------|
| Gatekeeper | `xattr -cr` 으로 quarantine 해제 |
| python3 | macOS 기본 내장 (JSON 파싱에 사용) |
| .command 확장자 | Finder에서 더블클릭 시 Terminal.app에서 실행 |
| PATH | `.zshrc` (기본) 또는 `.bash_profile` |
| `code` CLI 폴백 | PATH 없으면 `/Applications/.../bin/code` 직접 시도 (성공률 99%) |
| chmod+x 소실 | ZIP 해제 시 실행 권한 날아감 → README에 `chmod +x` 안내 |

### 검증 기준
- `.command` 더블클릭 → Terminal에서 4단계 실행
- settings.json에 설정 주입 완료
- `xattr` 오류 시에도 계속 진행

---

## 6. D5: installer/build-installer.sh

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSTALLER_DIR="$REPO_ROOT/installer"
OUTPUT_DIR="$REPO_ROOT/dist/installer"

echo "=== Building myAiCoder Installer Package ==="

# ── 1. Frozen binary 빌드 ──
echo "[1/4] Building frozen binary..."
cd "$REPO_ROOT/services/myaicoder"
uv pip install pyinstaller -q
uv run pyinstaller "$INSTALLER_DIR/myaicoder.spec" --distpath "$OUTPUT_DIR" --workpath /tmp/pyinstaller-build -y
echo "      → $(ls -lh "$OUTPUT_DIR/myaicoder" | awk '{print $5}')"

# ── 2. Extension 빌드 ──
echo "[2/4] Building VS Code Extension..."
cd "$REPO_ROOT/apps/vscode-extension"
npm run build
npx @vscode/vsce package --no-dependencies -o "$OUTPUT_DIR/myaicoder-0.1.0.vsix"

# ── 3. 설치 파일 복사 ──
echo "[3/4] Copying installer files..."
cp "$INSTALLER_DIR/config.json" "$OUTPUT_DIR/"
cp "$INSTALLER_DIR/install.bat" "$OUTPUT_DIR/설치하기.bat"
cp "$INSTALLER_DIR/install.command" "$OUTPUT_DIR/설치하기.command"
chmod +x "$OUTPUT_DIR/설치하기.command"
cp "$INSTALLER_DIR/README.txt" "$OUTPUT_DIR/"

# ── 4. ZIP 패키지 생성 ──
echo "[4/4] Creating zip package..."
cd "$OUTPUT_DIR/.."
zip -r myaicoder-setup.zip installer/
echo "      → $(ls -lh myaicoder-setup.zip | awk '{print $5}')"

echo ""
echo "=== Build Complete ==="
echo "Output: $REPO_ROOT/dist/myaicoder-setup.zip"
echo ""
echo "배포 전 config.json의 server_url을 확인하세요."
```

### 검증 기준
- 스크립트 실행 → `dist/myaicoder-setup.zip` 생성
- zip 내 6개 파일 포함

---

## 7. D6: installer/README.txt

```
======================================
myAiCoder 설치 안내
======================================

1. 이 폴더의 "설치하기" 파일을 더블클릭하세요.
   - Windows: 설치하기.bat
   - macOS:   설치하기.command

2. 설치가 완료되면 VS Code를 켜주세요.

3. VS Code 왼쪽 바에서 myAiCoder 아이콘을 클릭하면
   바로 AI 코딩 어시스턴트를 사용할 수 있습니다.

--------------------------------------
문제가 발생하면?
--------------------------------------
- Windows: "Windows가 PC를 보호했습니다" 메시지가 나오면
  "추가 정보" → "실행" 클릭

- macOS: "설치하기.command"를 더블클릭해도 텍스트 편집기가
  열리는 경우, 터미널에서 아래 명령어를 실행하세요:
  chmod +x 설치하기.command && open 설치하기.command

- macOS: "확인되지 않은 개발자" 메시지가 나오면
  시스템 설정 > 개인정보 및 보안 > "확인 없이 열기" 클릭

- VS Code가 설치되어 있지 않다면
  https://code.visualstudio.com 에서 먼저 설치하세요
```

---

## 8. 구현 순서

```
S1. installer/ 디렉토리 생성
S2. myaicoder.spec 작성                    [D1]
S3. config.json 템플릿 작성                 [D2]
S4. install.bat 작성 (Windows)              [D3]
S5. install.command 작성 (macOS)            [D4]
S6. build-installer.sh 작성                 [D5]
S7. README.txt 작성                         [D6]
S8. 로컬 빌드 테스트 (Linux binary + zip)    [D5 검증]
S9. frozen binary 기능 테스트               [D1 검증]
S10. 기존 테스트 통과 확인                    [241 passed]
```

## 9. 검증 매트릭스

| 설계 항목 | 검증 방법 | 성공 기준 |
|----------|----------|----------|
| D1 spec | `pyinstaller installer/myaicoder.spec` | 빌드 성공 |
| D1 binary | `dist/myaicoder --help` | 정상 출력 |
| D1 serve | `dist/myaicoder serve --help` | MCP 옵션 표시 |
| D2 config | JSON 유효성 | `python3 -c "import json; json.load(open(...))"` |
| D3 bat | PowerShell JSON 파싱 테스트 | `server_url` 추출 성공 |
| D4 command | bash 구문 검증 | `bash -n install.command` |
| D5 build | `bash build-installer.sh` | zip 생성 (6개 파일) |
| D6 README | 파일 존재 | 한글 안내 포함 |
| 전체 | Gateway + myaicoder 테스트 | 241 passed |
