# Act: windows-installer — CI 디버깅 기록

**작성일**: 2026-03-15
**상태**: CI 빌드 성공 (v0.1.6) → Extension Windows 호환 수정 (v0.1.7) → E2E 테스트 진행 중

---

## 1. 요약

GitHub Actions `windows-latest` runner에서 PyInstaller .exe 빌드 시 발생한 3건의 연속 오류와 해결 과정을 기록한다.

---

## 2. 오류 타임라인

### 시도 1: installer-v0.1.0 — CI 기존 테스트 실패 (무관)

**증상**: `test_generate_session_id_uniqueness` flaky test 실패 (98/100)
**원인**: `os.urandom(2)` → 4자리 hex (65536 가능), 동일 밀리초에 100개 생성 시 birthday problem ~7% 충돌
**수정**: `os.urandom(4)` → 8자리 hex (~4.3억 가능)
**교훈**: windows-installer와 무관한 기존 코드 품질 문제

---

### 시도 2: installer-v0.1.2 — PyInstaller not found

```
error: Failed to spawn: `pyinstaller`
  Caused by: program not found
```

**원인**: PyInstaller가 `pyproject.toml`의 dev 의존성에 없음
**수정**: workflow에 `uv pip install pyinstaller` 추가 (dev에 넣지 않음 → CI 테스트에 불필요한 설치 방지)
**교훈**: 빌드 전용 도구는 workflow에서 별도 설치

---

### 시도 3: installer-v0.1.3 ~ v0.1.4 — Windows 경로 증발

```
Python environment: D:\a\myaicoder\myaicoder\services\myaicoder\.venv
ERROR: script 'D:\a\myaicoder\services\myaicoder\src\myaicoder\cli.py' not found
```

**증상**: `myaicoder\myaicoder\` 중 하나가 사라짐
**원인 1 (MSYS 맹글링)**: Git Bash(MSYS)가 `$GITHUB_WORKSPACE` 셸 변수의 중복 경로 컴포넌트 `myaicoder/myaicoder`를 `myaicoder`로 축소
**원인 2 (SPECPATH 오해)**: `SPECPATH`는 이미 디렉토리 경로인데 `os.path.dirname(SPECPATH)`로 한 단계 더 올라감

**시도한 수정**:
1. `$GITHUB_WORKSPACE` → `${{ github.workspace }}` 변경 → 실패 (MSYS가 여전히 개입)
2. `REPO_ROOT` 환경변수 전달 → 실패 (spec 내부의 dirname 버그 미수정)

**최종 수정**:
```python
# Before (버그)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(SPECPATH), '..'))

# After (수정)
WORKSPACE_ROOT = os.environ.get('WORKSPACE_ROOT')
if WORKSPACE_ROOT:
    REPO_ROOT = WORKSPACE_ROOT
else:
    REPO_ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))  # dirname 제거
```

```yaml
# Workflow: YAML 레벨 치환으로 MSYS 우회
env:
  WORKSPACE_ROOT: ${{ github.workspace }}
```

**교훈**:
- SPECPATH는 PyInstaller가 제공하는 디렉토리 경로 → dirname 불필요
- Windows Git Bash에서 경로는 반드시 YAML `${{ }}` 또는 env로 전달
- 셸 변수 `$GITHUB_WORKSPACE` 직접 사용 금지 (MSYS 맹글링)

---

### 시도 4: installer-v0.1.5 — npm ci 실패

```
npm error The `npm ci` command can only install with an existing package-lock.json
```

**원인**: 세션 4에서 `package-lock.json` 삭제 + `.gitignore` 추가 (pnpm이 정식)
**수정**: npm → pnpm으로 변경
```yaml
# Before
npm ci && npm run build && npx @vscode/vsce package

# After
pnpm install --frozen-lockfile && pnpm run build && pnpm exec vsce package
```
**교훈**: 프로젝트 패키지 매니저 변경 시 모든 CI 워크플로우 일괄 확인 필요

---

### 시도 5: installer-v0.1.6 — 성공

```
✓ Run Build Windows Installer completed with 'success'
```

---

### 시도 6: installer-v0.1.7 — Extension Windows 호환 수정

**증상 1**: `'which' is not recognized` 에러 → Extension이 `which myaicoder`로 CLI를 찾으려 함
**증상 2**: `executablePath` 설정이 있어도 `fs.existsSync`에서 Windows 경로를 못 찾음
**증상 3**: `install.bat`의 settings.json 주입이 `%APPDATA%\Code\User\` 경로에 실패 (디렉토리 미존재)

**수정** (`apps/vscode-extension/src/config.ts`):
```typescript
// Before
execSync('which myaicoder', ...);
// After
const cmd = process.platform === 'win32' ? 'where myaicoder' : 'which myaicoder';
execSync(cmd, { stdio: ['pipe', 'pipe', 'pipe'] });

// Before
if (configured && fs.existsSync(configured)) {
// After
const normalized = path.normalize(configured);
if (fs.existsSync(normalized)) {

// Before (venv 경로)
path.join(workspaceFolder, '.venv', 'bin', 'myaicoder');
// After (크로스 플랫폼)
isWin ? path.join('.venv', 'Scripts', 'myaicoder.exe')
      : path.join('.venv', 'bin', 'myaicoder');
```

**교훈**:
- Windows에서 `which` → `where` 사용
- Windows 경로는 `path.normalize()`로 정규화
- `.venv/bin/` → Windows는 `.venv/Scripts/`
- `execSync` 에러 출력 숨김: `stdio: ['pipe', 'pipe', 'pipe']`

---

## 3. 최종 변경 파일

| 파일 | 변경 내용 |
|------|----------|
| `installer/myaicoder.spec` | WORKSPACE_ROOT 환경변수 우선, SPECPATH fallback (dirname 제거) |
| `.github/workflows/build-windows-installer.yml` | WORKSPACE_ROOT env, pnpm 빌드, uv pip install pyinstaller |
| `services/myaicoder/src/myaicoder/core/session.py` | os.urandom(2) → os.urandom(4) flaky test 수정 |
| `apps/vscode-extension/src/config.ts` | which→where, path.normalize, .venv/Scripts, stdio 숨김 |
| `apps/vscode-extension/test/unit/config.test.ts` | PATH lookup 테스트에 mockExistsSync 추가 |

## 4. 발견된 엣지 케이스 (10건)

### CI 빌드 관련 (A~G)

| # | 엣지 케이스 | 해결 |
|---|-------------|------|
| A | Windows 기본 쉘 PowerShell | `shell: bash` 명시 |
| B | spec 경로 구분자 | `os.path.join()` 사용 |
| C | Release Action 선택 | `softprops/action-gh-release@v1` |
| D | GITHUB_TOKEN 권한 | `permissions: contents: write` |
| E | MSYS 경로 맹글링 | YAML `${{ }}` 치환 또는 env 전달 |
| F | SPECPATH는 디렉토리 | `dirname()` 제거, `join(SPECPATH, '..')` |
| G | pnpm 프로젝트 npm ci 불가 | pnpm으로 통일 |

### Extension Windows 호환 (H~J)

| # | 엣지 케이스 | 해결 |
|---|-------------|------|
| H | Windows에 `which` 없음 | `process.platform === 'win32' ? 'where' : 'which'` |
| I | Windows 경로 정규화 | `path.normalize()` 적용 |
| J | Windows .venv 경로 | `.venv/Scripts/myaicoder.exe` (bin → Scripts) |

## 5. 향후 주의사항

- Windows CI 워크플로우에서 경로는 **절대 셸 변수로 직접 사용하지 말 것**
- PyInstaller spec에서 `SPECPATH`를 사용할 때 **dirname을 적용하지 말 것**
- 패키지 매니저 변경 시 **모든 워크플로우 일괄 검토**
- 빌드 전용 도구(PyInstaller)는 **dev dependencies가 아닌 workflow에서 설치**
- Extension 코드에서 OS 명령어는 **반드시 `process.platform` 분기**
- install.bat의 settings.json 주입은 **VS Code 미설치 시 디렉토리 없을 수 있음** → 수동 설정 안내 필요

## 6. 테스트 현황

| 서비스 | 결과 |
|--------|------|
| Python (myaicoder) | 178 passed, 4 skipped |
| Gateway | 43 passed |
| Extension | 20 passed |
| **총합** | **241 passed** |

## 7. 진행 상태

```
CI 빌드: ✅ (installer-v0.1.6 성공)
Extension 수정: ✅ (installer-v0.1.7 빌드)
Windows E2E: ⏳ (재설치 후 채팅 테스트 필요)
```
