# Session Handoff - 2026-03-15 (Session 4)

## 1. 현재 완료 상태

완료된 PDCA feature (17개):

| # | Feature | Match Rate | 상태 | 세션 |
|---|---------|-----------|------|------|
| 1 | ai-coder-cli | 95% | completed | 세션 1 (03-13) |
| 2 | mcp-server | 100% | completed | 세션 1 |
| 3 | myaicoder | 99% | completed | 세션 1 |
| 4 | vscode-extension | 99% | archived | 세션 1 |
| 5 | integration-and-ci | 97% | completed | 세션 1 |
| 6 | api-gateway | 100% | completed | 세션 2 (03-14) |
| 7 | model-management | 100% | completed | 세션 2 |
| 8 | rate-limiting | 99% | completed | 세션 2 |
| 9 | gateway-internal-api | 100% | completed | 세션 2 |
| 10 | integration-testing | 95% | completed | 세션 2 |
| 11 | context-management | 100% | completed | 세션 2 |
| 12 | conversation-persistence | 100% | completed | 세션 3 (03-14) |
| 13 | advanced-mcp-tools | 100% | completed | 세션 3 |
| 14 | marketplace-deployment | 91% | completed | 세션 4 (03-14~15) |
| 15 | observability | 100% | completed | 세션 4 |
| 16 | developer-onboarding | 100% | completed | 세션 4 |
| 17 | oneclick-installer | 100% | completed | 세션 4 |

평균 Match Rate: **98.5%**

## 2. 이번 세션에서 한 일

### 2.1 marketplace-deployment (Feature #14, 91%)
- VS Code Extension 사내 전용 배포 준비
- README.md, CHANGELOG.md, LICENSE, 128x128 아이콘
- CI/CD: ext-v* 태그 → GitHub Releases .vsix 첨부
- **배포 전략**: 퍼블릭 마켓플레이스 → 사내 전용 (인트라넷/카카오톡)

### 2.2 observability (Feature #15, 100%)
- Gateway Prometheus 메트릭 6종 계측
- **핵심**: SSE 스트리밍 latency/TTFT/tokens는 proxy.py finally 블록에서 측정
- 요청 상관 ID (clear_contextvars → bind_contextvars 순서)
- TTFT 버킷 20.0/30.0 추가 (콜드 스타트 대비)
- Grafana 대시보드 6패널 + JSON provisioning
- docker-compose에 Prometheus + Grafana 추가

### 2.3 developer-onboarding (Feature #16, 100%)
- docs/getting-started.md: 서버 모드(3분) + 로컬 모드(10분)
- config/*.example 중앙화, .env.example
- scripts/setup-dev.sh (멱등), scripts/start-all.sh (graceful shutdown)
- process.py 3-tier fallback (yaml → 환경변수 → PATH)
- CLI 기본 모델명 통일 (qwen3.5-9b)
- 프로젝트 루트 README.md

### 2.4 oneclick-installer (Feature #17, 100%)
- PyInstaller frozen binary (25MB, onefile)
- install.bat (Windows): 관리자 자동 상승, settings.json 주입
- install.command (macOS): code CLI 2-tier 폴백, xattr Gatekeeper
- build-installer.sh → myaicoder-setup.zip (24MB)
- README.txt (chmod+x 안내, SmartScreen 안내)

### 2.5 Windows 실제 접속 테스트 (진행 중)
- 서버: LLM(8001) + Gateway(8080) 구동, 192.168.0.22
- Windows 노트북에서 /health OK 확인
- CLI 설치 + Extension 설치 → 채팅 테스트 진행 예정

## 3. 주요 피드백 반영 (이번 세션)

| 피드백 | 반영 위치 |
|--------|----------|
| 사내 전용 배포 (마켓플레이스 미사용) | marketplace-deployment |
| README 이미지 절대 URL / Publisher ID / CHANGELOG 버전 매칭 | marketplace-deployment |
| SSE 스트리밍 계측 시점 (proxy finally) | observability |
| contextvars clear 필수 | observability |
| TTFT 콜드 스타트 버킷 | observability |
| setup-dev.sh 멱등성 (cp -n) | developer-onboarding |
| 모델 자동 다운로드 (huggingface-cli) | developer-onboarding |
| backend_command 3-tier fallback | developer-onboarding |
| DGX 서버 + 로컬 듀얼 모드 | developer-onboarding |
| Windows 관리자 자동 상승 | oneclick-installer |
| macOS chmod+x 소실 안내 | oneclick-installer |
| macOS code CLI 2-tier 폴백 | oneclick-installer |

## 4. 테스트 현황

| 서비스 | 결과 |
|--------|------|
| Python (myaicoder) | 178 passed, 4 skipped |
| Gateway | 43 passed |
| Extension | 20 passed |
| **총합** | **241 passed** |
| Ruff | All checks passed |

## 5. 서버 상태

| 서비스 | 포트 | 상태 |
|--------|------|------|
| LLM Server (llama.cpp) | 8001 | 실행 중 (PID: 178993) |
| Gateway | 8080 | 실행 중 (nohup, PID: 382001) |
| IP | 192.168.0.22 | 외부 접근 가능 |

## 6. 남아있는 작업

### 즉시
- Windows 노트북 실제 채팅 테스트 완료
- Windows용 .exe 빌드 (Windows 환경에서 PyInstaller)

### 로드맵 잔여
- B-2. Token Rate Limiting (필요 시)
- C-2. Performance Tuning (필요 시)

### 이연된 P2 항목
- LLM 기반 요약
- tiktoken 토큰 카운팅
- PythonAST 도구
- 웹 검색
- 자동 업데이트 (oneclick-installer P2)
- GUI 설치 마법사

## 7. CI 오류 수정 + 코드베이스 정리

### CI 오류
- **원인**: marketplace-deployment에서 `@vscode/vsce` 추가 후 `pnpm-lock.yaml` 미갱신
- **수정**: `pnpm install` → lockfile 업데이트 → CI 3/3 PASS

### 코드베이스 정리 (삭제 7건)
| 삭제 파일 | 이유 |
|----------|------|
| `services/gateway/gateway.yaml.example` | 중복 (config/에 중앙화) |
| `services/myaicoder/models.yaml.example` | 중복 (config/에 중앙화) |
| `apps/vscode-extension/package-lock.json` | npm 잔재 (pnpm이 정식) |
| `chat_log/020_ci_검증_및_model_management.md` | 중복 번호 (020 2개) |
| `myaicoder/` (루트 빈 폴더) | 초기 생성 후 방치 |
| `main.py` (루트) | "Hello" 플레이스홀더 |
| `COMPLETION_SUMMARY_oneclick-installer.md` | 자동 생성물 |

### .gitignore 추가
- `package-lock.json` — pnpm 프로젝트에서 npm lockfile 방지
- `COMPLETION_SUMMARY_*.md` — 빌드 산출물

### 기타
- `scripts/integration_test.sh` 주석 업데이트 (vLLM → llama.cpp)
- 빈 agent-memory 폴더 3개 삭제

## 8. 미커밋 변경사항 (다음 세션에서 커밋 필요)

- .gitignore 업데이트 (package-lock.json, COMPLETION_SUMMARY_*)
- 파일 7건 삭제 (중복 config, 잔재 파일)
- integration_test.sh 주석 수정

## 9. 다음 세션에서 먼저 볼 파일

- `docs/session-handoff-2026-03-15-session4.md` (이 파일)
- `docs/roadmap-2026-03.md`
- `docs/.pdca-status.json`
