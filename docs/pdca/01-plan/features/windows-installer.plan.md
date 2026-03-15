# Plan: windows-installer

## Feature 정보

| 항목 | 내용 |
|------|------|
| Feature | windows-installer |
| Track | A (UX 완성 및 제품화) |
| 우선순위 | **높음** — 주요 사용자가 Windows, 수동 빌드 불가 상태 해소 |
| 의존 | oneclick-installer (spec, install.bat 재사용), publish-extension.yml (CI 패턴) |
| 근거 | oneclick-installer P1-R8 이연 항목 이행 |

## 1. 목적

GitHub Actions `windows-latest` runner에서 **Windows .exe**를 자동 빌드하고, 배포 패키지(zip)를 GitHub Release에 첨부한다. 태그 하나로 빌드→패키징→배포 완전 자동화.

### 최종 UX

```
1. git tag installer-v0.1.0 && git push origin installer-v0.1.0
2. GitHub Actions 자동 실행 (windows-latest)
3. PyInstaller → myaicoder.exe 빌드
4. vsce package → .vsix 빌드
5. zip 패키지 생성 (exe + vsix + install.bat + config.json + README.txt)
6. GitHub Release에 myaicoder-windows-setup.zip 자동 첨부
7. 관리자가 Release에서 다운 → 카카오톡/인트라넷 배포
```

### 배경

- 현재 `build-installer.sh`는 Linux 바이너리만 생성 (PyInstaller 크로스 컴파일 불가)
- Windows 노트북에서 수동 빌드는 환경 재현·버스 팩터 문제
- Wine 크로스 컴파일은 안정성 문제로 비권장
- 기존 `publish-extension.yml` (ext-v* 태그 → Release) 패턴과 통일 가능

## 2. 현재 상태 분석

### 2.1 이미 있는 것

| 항목 | 위치 | 상태 |
|------|------|------|
| install.bat (Windows 설치 스크립트) | installer/install.bat | ✅ 완성 |
| install.command (macOS 설치 스크립트) | installer/install.command | ✅ 완성 |
| PyInstaller spec | installer/myaicoder.spec | ✅ 완성 (Linux 검증) |
| config.json (설치 설정) | installer/config.json | ✅ 완성 |
| README.txt (설치 안내) | installer/README.txt | ✅ 완성 |
| build-installer.sh (Linux 빌드) | installer/build-installer.sh | ✅ 완성 |
| publish-extension.yml (CI 패턴) | .github/workflows/publish-extension.yml | ✅ 참고용 |
| ci.yml (테스트 CI) | .github/workflows/ci.yml | ✅ 기존 |

### 2.2 없는 것

| 항목 | 필요 이유 | 복잡도 |
|------|----------|--------|
| build-windows-installer.yml | GitHub Actions Windows 빌드 워크플로우 | 중 |
| myaicoder.spec Windows 호환 확인 | `\` 경로, Windows 전용 모듈 | 낮 |
| uv.lock / requirements 호환 | CI runner에서 의존성 설치 | 낮 |

## 3. 아키텍처

### 3.1 워크플로우 구조

```
installer-v* 태그 push
  │
  └─ GitHub Actions (windows-latest)
      │
      ├─ Step 1: Checkout + Python 3.12 + uv 설치
      │
      ├─ Step 2: uv sync (myaicoder 의존성)
      │
      ├─ Step 3: PyInstaller → myaicoder.exe
      │           uv run pyinstaller installer/myaicoder.spec
      │           → dist/myaicoder.exe (~25MB)
      │
      ├─ Step 4: Node 20 + npm ci → vsce package
      │           → myaicoder-*.vsix
      │
      ├─ Step 5: 패키지 조립
      │           myaicoder-windows-setup/
      │           ├── myaicoder.exe
      │           ├── myaicoder-0.1.0.vsix
      │           ├── 설치하기.bat
      │           ├── config.json
      │           └── README.txt
      │
      ├─ Step 6: zip 생성
      │           → myaicoder-windows-setup.zip
      │
      ├─ Step 7: Upload artifact + GitHub Release 첨부
      │
      └─ 완료
```

### 3.2 기존 CI와의 관계

```
ci.yml              → push/PR 시 테스트 (ubuntu-latest)
publish-extension.yml → ext-v* 태그 → .vsix Release (ubuntu-latest)
build-windows-installer.yml → installer-v* 태그 → .exe + zip Release (windows-latest)  ← 신규
```

### 3.3 태그 컨벤션

| 태그 패턴 | 워크플로우 | 산출물 |
|-----------|-----------|--------|
| `ext-v*` | publish-extension.yml | .vsix |
| `installer-v*` | build-windows-installer.yml | myaicoder-windows-setup.zip |

## 4. 요구사항

### 4.1 필수 요구사항 (P0)

| ID | 요구사항 | 검증 기준 |
|----|----------|----------|
| R1 | GitHub Actions 워크플로우 | `installer-v*` 태그 push 시 자동 트리거 |
| R2 | windows-latest runner에서 빌드 | PyInstaller 빌드 성공, exit code 0 |
| R3 | myaicoder.exe 생성 | artifact에 .exe 포함 |
| R4 | .vsix 포함 | Extension도 패키지에 포함 |
| R5 | zip 패키지 조립 | exe + vsix + bat + config.json + README.txt |
| R6 | GitHub Release 첨부 | Release에 .zip 다운로드 가능 |
| R7 | 기존 CI 미영향 | ci.yml, publish-extension.yml 변경 없음 |

### 4.2 권장 요구사항 (P1)

| ID | 요구사항 | 검증 기준 |
|----|----------|----------|
| R8 | 빌드 캐시 (uv, pip) | 재빌드 시간 단축 |
| R9 | 빌드 결과 Slack/카카오 알림 | webhook (향후) |

### 4.3 이연 항목 (P2)

| ID | 요구사항 | 이유 |
|----|----------|------|
| R10 | macOS binary 동시 빌드 (matrix) | 현재 Windows 타겟 집중 |
| R11 | 코드 사이닝 (SmartScreen 해소) | 인증서 비용 발생 |
| R12 | 자동 업데이트 체크 | 첫 배포 안정화 후 |

## 5. 구현 범위

### 5.1 신규 파일

```
.github/workflows/build-windows-installer.yml   ← 핵심 산출물
```

### 5.2 수정 가능 파일

```
installer/myaicoder.spec    ← Windows 경로 호환 확인 (필요 시)
```

### 5.3 변경 없는 파일

```
installer/install.bat       ← 그대로 사용
installer/config.json       ← 그대로 사용
installer/README.txt        ← 그대로 사용
.github/workflows/ci.yml    ← 변경 없음
.github/workflows/publish-extension.yml  ← 변경 없음
```

## 6. 구현 순서

| 단계 | 작업 | 산출물 |
|------|------|--------|
| S1 | myaicoder.spec Windows 호환 확인 | pathex, separator 검증 |
| S2 | build-windows-installer.yml 작성 | 워크플로우 파일 |
| S3 | 로컬 검증 (act 또는 수동 push) | CI 통과 |
| S4 | 태그 push → Release 확인 | zip 다운로드 가능 |
| S5 | 다운로드한 zip으로 Windows 설치 테스트 | 설치 성공 |

## 7. 리스크 및 엣지 케이스

| 리스크 | 영향 | 대응 |
|--------|------|------|
| Windows runner에서 uv 설치 실패 | 빌드 불가 | astral-sh/setup-uv@v5 공식 지원 확인 |
| PyInstaller spec의 pathex 경로 | 빌드 실패 | 상대 경로 + os.path 사용 |
| Windows에서 한글 파일명 (설치하기.bat) | 인코딩 문제 | cp65001 + UTF-8 |
| vsce package가 npm 필요 | pnpm과 혼재 | Extension은 npm ci 사용 (독립성) |
| .exe 크기 > 100MB | Release 첨부 제한 | UPX 압축, excludes 최적화 (현재 25MB) |
| Private repo Actions 분 제한 | 월 2,000분 초과 | 빌드 캐시로 완화, 필요 시 public |

### 7.1 Windows CI 엣지 케이스 (필수 반영)

| 엣지 케이스 | 문제 | 해결 |
|-------------|------|------|
| **A. 기본 쉘이 PowerShell** | `run:` 블록이 pwsh로 실행되어 cp/ls/rm 동작 차이, 한글 파일명 인코딩 깨짐 | 모든 핵심 Step에 `shell: bash` 명시 (Git for Windows Bash) |
| **B. spec 경로 구분자** | `../services/...` 슬래시 하드코딩 → PyInstaller Windows에서 간헐적 경로 실패 | `os.path.join()` 또는 `Path` 객체로 OS 독립적 경로 변환 |
| **C. Release 첨부 Action** | zip을 GitHub Release에 첨부 | `softprops/action-gh-release@v1` 사용 (태그 연동 + 자동 릴리즈 노트) |
| **D. GITHUB_TOKEN 권한** | 기본 토큰이 Read-only → Release 생성 시 403 Forbidden | job에 `permissions: contents: write` 명시 필수 |

## 8. 성공 기준

| 기준 | 측정 방법 |
|------|----------|
| `installer-v*` 태그 → CI 자동 시작 | Actions 탭 확인 |
| 빌드 성공 (exit 0) | CI 로그 |
| Release에 zip 첨부 | GitHub Release 페이지 |
| zip 내 5개 파일 포함 | zip 내용 확인 (exe, vsix, bat, config.json, README.txt) |
| 다운로드 zip → install.bat 실행 → 설치 성공 | Windows PC 테스트 |
| 기존 CI (ci.yml) 영향 없음 | push 시 기존 테스트 통과 |
