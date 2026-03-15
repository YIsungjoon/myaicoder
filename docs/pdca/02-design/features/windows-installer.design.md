# Design: windows-installer

## 1. 개요

| 항목 | 내용 |
|------|------|
| Feature | windows-installer |
| Plan | [windows-installer.plan.md](../../01-plan/features/windows-installer.plan.md) |
| 신규 파일 | 1개 (.github/workflows/build-windows-installer.yml) |
| 수정 파일 | 1개 (installer/myaicoder.spec) |
| 변경 없음 | ci.yml, publish-extension.yml, install.bat, config.json, README.txt |

## 2. 설계 항목

### D1. myaicoder.spec Windows 호환 수정

**파일**: `installer/myaicoder.spec`

**현재** (하드코딩 슬래시):
```python
a = Analysis(
    ['../services/myaicoder/src/myaicoder/cli.py'],
    pathex=['../services/myaicoder/src'],
    ...
)
```

**변경** (OS 독립적 경로):
```python
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(SPECPATH), '..'))
SERVICE_DIR = os.path.join(REPO_ROOT, 'services', 'myaicoder')
SRC_DIR = os.path.join(SERVICE_DIR, 'src')
ENTRY_POINT = os.path.join(SRC_DIR, 'myaicoder', 'cli.py')

a = Analysis(
    [ENTRY_POINT],
    pathex=[SRC_DIR],
    ...
)
```

**검증**: Linux에서 기존 빌드 동일 동작 + Windows CI에서 빌드 성공

---

### D2. build-windows-installer.yml 워크플로우

**파일**: `.github/workflows/build-windows-installer.yml`

#### D2-1. 트리거

```yaml
name: Build Windows Installer

on:
  push:
    tags:
      - 'installer-v*'
```

#### D2-2. Job 구조

```yaml
jobs:
  build:
    name: Build Windows Installer Package
    runs-on: windows-latest

    permissions:
      contents: write    # ← 엣지 케이스 D: Release 생성 권한

    defaults:
      run:
        shell: bash      # ← 엣지 케이스 A: 모든 step에서 bash 사용
```

#### D2-3. Step 1 — Checkout

```yaml
    steps:
      - name: Checkout
        uses: actions/checkout@v4
```

#### D2-4. Step 2 — Python + uv 설치

```yaml
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Set up uv
        uses: astral-sh/setup-uv@v5
```

#### D2-5. Step 3 — 의존성 설치 + PyInstaller 빌드

```yaml
      - name: Install dependencies
        working-directory: services/myaicoder
        run: uv sync --frozen --extra dev

      - name: Build frozen binary
        working-directory: services/myaicoder
        run: |
          uv run pyinstaller ../../installer/myaicoder.spec \
            --distpath ../../dist \
            --workpath /tmp/pyinstaller-build \
            -y
```

**산출물**: `dist/myaicoder.exe`

**주의사항**:
- `working-directory: services/myaicoder` — uv 프로젝트 루트에서 실행
- spec 경로는 `../../installer/myaicoder.spec` (상대 경로)
- `--distpath`로 출력 위치 지정
- `--workpath /tmp/pyinstaller-build` — Windows에서도 Git Bash의 /tmp 사용 가능

#### D2-6. Step 4 — Extension 빌드

```yaml
      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Build Extension
        working-directory: apps/vscode-extension
        run: |
          npm ci
          npm run build
          npx @vscode/vsce package --no-dependencies
```

**산출물**: `apps/vscode-extension/myaicoder-*.vsix`

**설계 근거**: Extension은 npm 사용 (pnpm 아닌 이유: publish-extension.yml과 동일, 독립성 유지)

#### D2-7. Step 5 — 패키지 조립

```yaml
      - name: Assemble package
        run: |
          mkdir -p dist/myaicoder-windows-setup
          cp dist/myaicoder.exe dist/myaicoder-windows-setup/
          cp apps/vscode-extension/myaicoder-*.vsix dist/myaicoder-windows-setup/
          cp installer/install.bat "dist/myaicoder-windows-setup/설치하기.bat"
          cp installer/config.json dist/myaicoder-windows-setup/
          cp installer/README.txt dist/myaicoder-windows-setup/
          echo "=== Package contents ==="
          ls -lh dist/myaicoder-windows-setup/
```

**산출물 구조**:
```
dist/myaicoder-windows-setup/
├── myaicoder.exe           ← frozen binary (~25MB)
├── myaicoder-0.1.0.vsix    ← VS Code Extension (~105KB)
├── 설치하기.bat             ← 더블클릭 설치 스크립트
├── config.json              ← 서버 URL, 모델 설정
└── README.txt               ← 설치 안내
```

**한글 파일명**: `shell: bash` (Git for Windows) 환경에서 UTF-8 처리 정상

#### D2-8. Step 6 — zip 생성

```yaml
      - name: Create zip package
        run: |
          cd dist
          7z a myaicoder-windows-setup.zip myaicoder-windows-setup/
```

**설계 근거**: Windows runner에 `7z` (7-Zip) 기본 설치됨. bash에서 zip 명령이 없을 수 있으므로 7z 사용.

#### D2-9. Step 7 — Artifact 업로드

```yaml
      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: myaicoder-windows-setup
          path: dist/myaicoder-windows-setup.zip
```

**용도**: 빌드 디버깅, Release 실패 시 수동 다운로드

#### D2-10. Step 8 — GitHub Release 생성 및 첨부

```yaml
      - name: Create GitHub Release
        uses: softprops/action-gh-release@v1
        with:
          files: dist/myaicoder-windows-setup.zip
          generate_release_notes: true
```

**설계 근거**:
- `softprops/action-gh-release@v1` — 가장 안정적인 Release 액션
- `generate_release_notes: true` — 태그 간 커밋 자동 릴리즈 노트
- `permissions: contents: write` — D2-2에서 이미 설정
- `GITHUB_TOKEN`은 자동 주입 (별도 설정 불필요)

---

## 3. 전체 워크플로우 YAML (완성본)

```yaml
name: Build Windows Installer

on:
  push:
    tags:
      - 'installer-v*'

jobs:
  build:
    name: Build Windows Installer Package
    runs-on: windows-latest

    permissions:
      contents: write

    defaults:
      run:
        shell: bash

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Set up uv
        uses: astral-sh/setup-uv@v5

      - name: Install dependencies
        working-directory: services/myaicoder
        run: uv sync --frozen --extra dev

      - name: Build frozen binary
        working-directory: services/myaicoder
        run: |
          uv run pyinstaller ../../installer/myaicoder.spec \
            --distpath ../../dist \
            --workpath /tmp/pyinstaller-build \
            -y

      - name: Verify binary
        run: |
          ls -lh dist/myaicoder.exe
          echo "Binary size: $(du -h dist/myaicoder.exe | cut -f1)"

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Build Extension
        working-directory: apps/vscode-extension
        run: |
          npm ci
          npm run build
          npx @vscode/vsce package --no-dependencies

      - name: Assemble package
        run: |
          mkdir -p dist/myaicoder-windows-setup
          cp dist/myaicoder.exe dist/myaicoder-windows-setup/
          cp apps/vscode-extension/myaicoder-*.vsix dist/myaicoder-windows-setup/
          cp installer/install.bat "dist/myaicoder-windows-setup/설치하기.bat"
          cp installer/config.json dist/myaicoder-windows-setup/
          cp installer/README.txt dist/myaicoder-windows-setup/
          echo "=== Package contents ==="
          ls -lh dist/myaicoder-windows-setup/

      - name: Create zip package
        run: |
          cd dist
          7z a myaicoder-windows-setup.zip myaicoder-windows-setup/

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: myaicoder-windows-setup
          path: dist/myaicoder-windows-setup.zip

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v1
        with:
          files: dist/myaicoder-windows-setup.zip
          generate_release_notes: true
```

## 4. 엣지 케이스 반영 확인

| 엣지 케이스 | 반영 위치 | 설계 항목 |
|-------------|----------|----------|
| A. 기본 쉘 PowerShell | `defaults: run: shell: bash` | D2-2 |
| B. spec 경로 구분자 | `os.path.join()` + `SPECPATH` | D1 |
| C. Release 첨부 Action | `softprops/action-gh-release@v1` | D2-10 |
| D. GITHUB_TOKEN 권한 | `permissions: contents: write` | D2-2 |

## 5. 파일 변경 목록

| 파일 | 작업 | 설계 항목 |
|------|------|----------|
| `installer/myaicoder.spec` | 수정 (os.path.join 경로) | D1 |
| `.github/workflows/build-windows-installer.yml` | 신규 | D2 |

## 6. 검증 체크리스트

| ID | 검증 항목 | 방법 |
|----|----------|------|
| V1 | spec 수정 후 Linux 빌드 정상 | `cd services/myaicoder && uv run pyinstaller ../../installer/myaicoder.spec` |
| V2 | installer-v* 태그 → CI 트리거 | Actions 탭 확인 |
| V3 | PyInstaller .exe 빌드 성공 | CI 로그 "Verify binary" step |
| V4 | .vsix 빌드 포함 | CI 로그 "Build Extension" step |
| V5 | zip 내 5개 파일 | CI 로그 "Assemble package" step |
| V6 | GitHub Release 생성 + zip 첨부 | Release 페이지 확인 |
| V7 | 기존 CI 미영향 | push 시 ci.yml 3/3 PASS |
| V8 | 다운로드 zip → install.bat 실행 | Windows PC 수동 테스트 |

## 7. 기존 CI와의 비교

| 항목 | ci.yml | publish-extension.yml | build-windows-installer.yml |
|------|--------|----------------------|----------------------------|
| 트리거 | push/PR | ext-v* 태그 | installer-v* 태그 |
| Runner | ubuntu-latest | ubuntu-latest | **windows-latest** |
| Shell | 기본 (bash) | 기본 (bash) | **명시적 bash** |
| Python | 3.12 + uv | - | 3.12 + uv |
| Node | 20 + pnpm | 20 + npm | 20 + npm |
| 산출물 | 테스트 결과 | .vsix | .zip (exe + vsix + bat) |
| Release | - | softprops@v2 | **softprops@v1** |
| Permissions | - | contents: write | contents: write |
