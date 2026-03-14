# Plan: oneclick-installer

## Feature 정보

| 항목 | 내용 |
|------|------|
| Feature | oneclick-installer |
| Track | A (UX 완성 및 제품화) |
| 우선순위 | **높음** — 비개발자 온보딩의 마지막 퍼즐 |
| 의존 | developer-onboarding (config 포터블화), marketplace-deployment (.vsix) |

## 1. 목적

비개발자가 **더블클릭 한 번**으로 myAiCoder를 설치하고 VS Code에서 바로 사용할 수 있게 한다.
Python 설치, pip, 터미널 명령어 없이 완결.

### 최종 UX

```
1. 카카오톡/인트라넷에서 myaicoder-setup.zip 다운로드
2. 압축 풀기
3. "설치하기.bat" (또는 .command) 더블클릭
4. "설치 완료! VS Code를 켜주세요." 메시지
5. VS Code 열면 Activity Bar에 myAiCoder 아이콘 → 바로 채팅
```

### 배경

- developer-onboarding (Feature #16)은 개발자 대상 (pip, uv 필요)
- 비개발자 PC: Python 없음, 터미널 사용 불가, settings.json 편집 불가
- DGX 서버에 LLM + Gateway 이미 구동 중 (서버 모드 전제)

## 2. 현재 상태 분석

### 2.1 이미 있는 것

| 항목 | 위치 |
|------|------|
| myaicoder CLI (Python) | services/myaicoder/ (`myaicoder serve` 명령) |
| VS Code Extension (.vsix) | apps/vscode-extension/ (빌드 가능) |
| Extension → CLI 자동 연결 | MCP stdio transport (CLI를 subprocess로 spawn) |
| DGX 서버 배포 가이드 | docs/getting-started.md |

### 2.2 없는 것

| 항목 | 필요 이유 | 복잡도 |
|------|----------|--------|
| PyInstaller spec + 빌드 | CLI를 단일 바이너리로 freeze | 중 |
| install.bat (Windows) | 더블클릭 설치 스크립트 | 낮 |
| install.command (macOS) | 더블클릭 설치 스크립트 | 낮 |
| VS Code settings.json 자동 주입 | llmUrl 설정 자동화 | 중 |
| 배포 패키지 빌드 스크립트 | zip 자동 생성 | 낮 |
| CI/CD 빌드 자동화 | GitHub Actions에서 frozen binary 빌드 | 중 |

## 3. 아키텍처

### 3.1 배포 패키지 구조

```
myaicoder-setup/
├── myaicoder.exe              ← PyInstaller frozen binary (Windows)
│   (또는 myaicoder-macos)     ← macOS binary
├── myaicoder-0.1.0.vsix       ← VS Code Extension
├── 설치하기.bat                ← Windows 더블클릭 설치
├── 설치하기.command            ← macOS 더블클릭 설치
└── config.json                ← 설치 설정 (서버 URL, 바이너리 설치 경로)
```

### 3.2 config.json (설치 설정)

```json
{
  "server_url": "http://dgx-server:8080",
  "install_dir": "~/.myaicoder",
  "model_name": "qwen3.5-9b"
}
```

서버 관리자가 이 파일만 편집해서 배포하면 됨.

### 3.3 설치 스크립트 동작 플로우

```
설치하기.bat 더블클릭
  │
  ├─ 1. config.json 읽기 (서버 URL 추출)
  │
  ├─ 2. myaicoder.exe → %USERPROFILE%\.myaicoder\ 복사
  │     (또는 ~/.myaicoder/ on macOS)
  │
  ├─ 3. PATH에 추가 (Windows: setx, macOS: .zshrc)
  │
  ├─ 4. code --install-extension myaicoder-0.1.0.vsix
  │
  ├─ 5. VS Code settings.json 찾기 + llmUrl 주입
  │     Windows: %APPDATA%\Code\User\settings.json
  │     macOS:   ~/Library/Application Support/Code/User/settings.json
  │
  └─ 6. "설치 완료!" 메시지
```

### 3.4 settings.json 주입 로직

```
기존 settings.json이 있으면:
  → JSON 파싱 → "myaicoder.llmUrl" 키 추가/업데이트 → 저장
  → 다른 설정은 절대 건드리지 않음

settings.json이 없으면:
  → 새 파일 생성 { "myaicoder.llmUrl": "http://..." }
```

## 4. 요구사항

### 4.1 필수 요구사항 (P0)

| ID | 요구사항 | 검증 기준 |
|----|----------|----------|
| R1 | PyInstaller spec 파일 | `pyinstaller myaicoder.spec` 성공 |
| R2 | frozen binary 실행 | `./myaicoder serve --help` 정상 출력 |
| R3 | install.bat (Windows) | 더블클릭 시 설치 완료, VS Code 설정 자동 |
| R4 | install.command (macOS) | 더블클릭 시 설치 완료, VS Code 설정 자동 |
| R5 | settings.json 자동 주입 | myaicoder.llmUrl 키가 올바른 값으로 설정 |
| R6 | config.json 설치 설정 | 서버 URL, 설치 경로 커스터마이징 가능 |
| R7 | 배포 패키지 빌드 스크립트 | `scripts/build-installer.sh` → zip 생성 |

### 4.2 권장 요구사항 (P1)

| ID | 요구사항 | 검증 기준 |
|----|----------|----------|
| R8 | CI/CD 자동 빌드 | GitHub Actions에서 Windows/macOS binary 생성 |
| R9 | 설치 제거 스크립트 | uninstall.bat / uninstall.command |

### 4.3 이연 항목 (P2)

| ID | 요구사항 | 이유 |
|----|----------|------|
| R10 | Linux binary | 사내 사용자 대부분 Windows/macOS |
| R11 | 자동 업데이트 | 첫 배포 안정화 후 |
| R12 | GUI 설치 마법사 | 현재 bat/command로 충분 |

## 5. 구현 범위

### 5.1 PyInstaller

```
installer/
├── myaicoder.spec             ← PyInstaller spec (onefile 모드)
├── build-installer.sh         ← 통합 빌드 스크립트
├── config.json                ← 설치 설정 템플릿
├── install.bat                ← Windows 설치 스크립트
├── install.command            ← macOS 설치 스크립트
└── README-installer.txt       ← 설치 안내 (zip 내 포함)
```

### 5.2 PyInstaller 주의사항

| 항목 | 대응 |
|------|------|
| MCP SDK의 dynamic import | `--hidden-import` 옵션 |
| asyncio event loop | `--collect-all asyncio` |
| httpx + SSL 인증서 | `--collect-data certifi` |
| 바이너리 크기 (~80MB) | UPX 압축 선택적 |
| 크로스 컴파일 불가 | GitHub Actions에서 OS별 빌드 |

### 5.3 Extension → frozen binary 연결

현재 Extension은 `myaicoder serve`를 PATH에서 찾아 spawn.
frozen binary를 `~/.myaicoder/myaicoder` (또는 `.exe`)에 설치하면:
- install 스크립트가 PATH에 추가 → Extension이 자동 감지
- 또는 Extension 설정 `myaicoder.executablePath`에 직접 지정

## 6. 구현 순서

| 단계 | 작업 | 산출물 |
|------|------|--------|
| S1 | PyInstaller spec 작성 | installer/myaicoder.spec |
| S2 | 로컬 빌드 테스트 (Linux) | dist/myaicoder 바이너리 |
| S3 | frozen binary 기능 테스트 | `./myaicoder serve --help` 정상 |
| S4 | config.json 템플릿 작성 | installer/config.json |
| S5 | install.bat 작성 (Windows) | installer/install.bat |
| S6 | install.command 작성 (macOS) | installer/install.command |
| S7 | build-installer.sh 빌드 스크립트 | installer/build-installer.sh |
| S8 | 배포 패키지 생성 테스트 | myaicoder-setup.zip |
| S9 | 기존 테스트 통과 확인 | 241 passed |

## 7. 리스크

| 리스크 | 영향 | 대응 |
|--------|------|------|
| PyInstaller + MCP SDK 호환성 | frozen binary 실행 실패 | hidden-import 테스트, hook 파일 작성 |
| Windows 보안 경고 (SmartScreen) | 사용자 겁먹음 | 코드 서명(future) + 안내 메시지 |
| settings.json 파싱 실패 | 설정 주입 불가 | JSON 파싱 에러 시 수동 안내 출력 |
| 바이너리 크기 (~80MB) | 카카오톡 전송 제한 | zip 압축 후 인트라넷 호스팅 |
| macOS Gatekeeper 차단 | 실행 불가 | `xattr -cr` 명령 안내 또는 서명 |

## 8. 성공 기준

| 기준 | 측정 방법 |
|------|----------|
| Python 없는 PC에서 frozen binary 실행 | 별도 VM에서 테스트 |
| install.bat 더블클릭 → 설치 완료 | Windows에서 확인 |
| VS Code settings.json에 llmUrl 자동 설정 | settings.json 파일 확인 |
| 설치 후 VS Code에서 첫 대화 성공 | DGX 서버 연결 확인 |
| 기존 테스트 241개 통과 | 0 regression |
| 배포 zip 생성 | build-installer.sh 실행 성공 |
