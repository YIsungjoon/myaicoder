# Session Handoff - 2026-03-15 (Session 5) — Final

## 1. 현재 완료 상태

완료된 PDCA feature (19개):

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
| 18 | windows-installer | 100% | completed | 세션 5 (03-15) |
| 19 | workspace-integration | 100% | completed | 세션 5 (03-15) |

평균 Match Rate: **98.7%**
Extension Version: **1.0.3** (최종 릴리즈: installer-v1.0.3)

## 2. 이번 세션에서 한 일

### Phase 1: PDCA 피처 (2개)

#### 2.1 windows-installer (Feature #18, 100%)
- GitHub Actions `windows-latest` runner에서 PyInstaller .exe 자동 빌드
- `installer-v*` 태그 push → CI → Release에 `myaicoder-windows-setup.zip` 자동 첨부
- 산출물: `build-windows-installer.yml` 신규, `myaicoder.spec` 수정
- **CI 디버깅 6회** (v0.1.0 ~ v0.1.6)

#### 2.2 workspace-integration (Feature #19, 100%) — V0.2
- 3가지 관문: 눈(Context) + 손발(Tools) + 코드 수정(Apply & Diff)
- 산출물: `apply.ts` 신규, 7개 파일 수정
- 엣지 케이스 3건: dirty state, 정규식, 신규 파일 diff

### Phase 2: Windows E2E 테스트 + 버그 수정

#### 2.3 Extension Windows 호환 수정
- `which` → `where` (process.platform 분기)
- `path.normalize()` 경로 정규화
- `.venv/Scripts/` Windows venv 경로
- `stdio: ['pipe', 'pipe', 'pipe']` 에러 출력 숨김

#### 2.4 대화 연속성 수정
- AgentEngine을 MCP 서버 수명 동안 영속화 (매 호출 생성 → 1회 생성)
- ConversationManager가 32K 컨텍스트 자동 관리
- `restoreMessages()`로 사이드바 전환 시 채팅 보존

#### 2.5 CLI 옵션 추가
- `--llm-url`, `--model-name` CLI 옵션 (원격 LLM 연결)
- Extension에서 llmUrl/modelName을 CLI spawn 시 전달
- `enableAgentic` 기본값 true 변경

### Phase 3: UX 개선 + v1.0.1

#### 2.6 시스템 프롬프트 개선 (`context.py`)
- **확인 후 행동**: 도구 사용 전 사용자 승인 필수
- **간결 응답**: 인사에는 인사만, 불필요한 분석 안 함
- **한국어 기본**: 응답 한국어, 코드 영어
- **도구 우선순위**: write_file > Bash, read_file > cat
- **Windows 명령어 가이드**: mkdir, dir, type, copy, del 안내
- **MYAICODER.md**: 프로젝트별 행동 양식 커스터마이징 (CLAUDE.md → MYAICODER.md 변경)

#### 2.7 3단 뷰 (Copilot 스타일)
- 채팅 패널을 오른쪽 보조 사이드바로 자동 이동
- `activitybar` 등록 + `workbench.action.moveViewToSecondarySideBar` 프로그래밍 이동
- `globalState`로 1회만 이동 (재시작 시 위치 유지)

#### 2.8 버전 1.0.1 통일
- `package.json` version → 1.0.1
- `installer/config.json` extension_file → myaicoder-1.0.1.vsix
- `installer/build-installer.sh` vsix 파일명 통일
- `src/mcp/client.ts` MCP 클라이언트 버전 통일
- `docs/getting-started.md` vsix 파일명 통일
- `CHANGELOG.md` 1.0.1 릴리즈 노트 추가

### Phase 4: Windows E2E 최종 테스트

| 항목 | 결과 |
|------|:----:|
| 설치하기.bat 실행 | ✅ |
| CLI 설치 확인 | ✅ |
| LLM 서버 연결 (직접 8001 포트) | ✅ |
| 채팅 응답 | ✅ |
| 대화 기억 (세션 내) | ✅ |
| 사이드바 전환 후 대화 유지 | ✅ |
| 한국어 응답 | ✅ |
| 확인 후 행동 (인사 테스트) | ✅ |

## 3. 주요 피드백 반영 (이번 세션)

| 피드백 | 반영 위치 |
|--------|----------|
| Windows runner 기본 쉘 PowerShell | build-windows-installer.yml (shell: bash) |
| PyInstaller SPECPATH는 디렉토리 | myaicoder.spec (dirname 제거) |
| MSYS 경로 맹글링 | WORKSPACE_ROOT env + YAML 치환 |
| GITHUB_TOKEN 권한 | permissions: contents: write |
| pnpm 프로젝트 npm ci 불가 | pnpm으로 통일 |
| Dirty state 방어 | handleApplyCode isDirty 체크 |
| 정규식 관대화 | [a-zA-Z0-9_+\-]* + trim() |
| 신규 파일 Diff | existsSync → 빈 파일 diff |
| 대화 연속성 | AgentEngine 영속화 |
| Qwen3.5 컨텍스트 활용 | 32K 자동 관리 + 압축 |
| 확인 후 행동 | 시스템 프롬프트 행동 규칙 |
| 한국어 기본 | 시스템 프롬프트 |
| CLAUDE.md → MYAICODER.md | 범용 이름 변경 |
| 3단 뷰 (오른쪽 배치) | auxiliarybar → activitybar + 프로그래밍 이동 |

## 4. 발견된 엣지 케이스 (13건)

### CI 빌드 관련 (A~G)
| # | 엣지 케이스 | 해결 |
|---|-------------|------|
| A | Windows 기본 쉘 PowerShell | shell: bash 명시 |
| B | spec 경로 구분자 | os.path.join() |
| C | Release Action 선택 | softprops/action-gh-release@v1 |
| D | GITHUB_TOKEN 권한 | permissions: contents: write |
| E | MSYS 경로 맹글링 | YAML ${{ }} 치환 |
| F | SPECPATH는 디렉토리 | dirname 제거 |
| G | pnpm 프로젝트 npm ci 불가 | pnpm 통일 |

### Extension Windows 호환 (H~J)
| # | 엣지 케이스 | 해결 |
|---|-------------|------|
| H | Windows에 which 없음 | process.platform 분기 |
| I | Windows 경로 정규화 | path.normalize() |
| J | Windows .venv 경로 | .venv/Scripts/ |

### Workspace (EC-A~C)
| # | 엣지 케이스 | 해결 |
|---|-------------|------|
| EC-A | Dirty State 방어 | isDirty → 저장 경고 |
| EC-B | 정규식 관대화 | 선택적 언어 + trim |
| EC-C | 신규 파일 Diff | existsSync → 빈 파일 |

## 5. 테스트 현황

| 서비스 | 결과 |
|--------|------|
| Python (myaicoder) | 178 passed, 4 skipped |
| Gateway | 43 passed |
| Extension | 20 passed |
| **총합** | **241 passed** |
| Ruff | All checks passed |

## 6. 릴리즈 태그 이력

| 태그 | 결과 | 내용 |
|------|------|------|
| installer-v0.1.0 | ❌ | flaky test (urandom) |
| installer-v0.1.2 | ❌ | PyInstaller 미설치 |
| installer-v0.1.3~4 | ❌ | MSYS 경로 맹글링 |
| installer-v0.1.5 | ❌ | npm ci 실패 |
| installer-v0.1.6 | ✅ | CI 첫 성공 |
| installer-v0.1.7 | ✅ | Extension which→where |
| installer-v0.1.9 | ✅ | --llm-url 추가 |
| installer-v0.2.0 | ✅ | workspace-integration V0.2 |
| installer-v0.2.2 | ✅ | 대화 연속성 |
| installer-v1.0.1 | ✅ | v1.0.1 (3단 뷰, 프롬프트 개선) |
| installer-v1.0.3 | ✅ | v1.0.3 최종 (MYAICODER.md, 확인 후 행동) |

## 7. 아키텍처 현황

```
[Windows 사용자 PC]                       [서버 PC (192.168.0.22)]
┌─────────────────────────────┐          ┌──────────────────────┐
│ VS Code                     │          │                      │
│ ┌─────┐ ┌──────┐ ┌───────┐ │          │ LLM Server (:8001)   │
│ │Explr│ │Editor│ │myAi   │ │          │  └ Qwen3.5-9B        │
│ │     │ │      │ │Coder  │ │          │    (32K context)     │
│ │     │ │      │ │Chat   │──HTTP─────>│                      │
│ │     │ │      │ │[Apply]│ │          │ Gateway (:8080)      │
│ └─────┘ └──────┘ └───────┘ │          │  └ Auth, Rate Limit  │
│                             │          │  └ Observability     │
│ myaicoder.exe (MCP stdio)   │          │                      │
│  └ AgentEngine (영속)       │          └──────────────────────┘
│    └ ConversationManager    │
│      └ 32K 자동 압축        │
└─────────────────────────────┘
```

## 8. 남아있는 작업

### 로드맵 잔여
- B-2. Token Rate Limiting (필요 시)
- C-2. Performance Tuning (필요 시)

### 이연된 P2 항목
- LLM 기반 요약 (context-management)
- tiktoken 토큰 카운팅
- PythonAST 도구
- 웹 검색
- 자동 업데이트 (oneclick-installer P2)
- GUI 설치 마법사
- apply.test.ts 신규 테스트 (workspace-integration P2)
- Gateway API key 연동 (현재 LLM 직접 연결로 우회)

### 개선 가능 항목
- Gateway 인증을 Extension에서 지원 (--api-key 옵션)
- install.bat의 settings.json 주입 디버깅 (현재 수동 설정 필요)
- 멀티파일 동시 수정 지원
- @file 멘션 기능
- Chat Participant API 검토 (VS Code native chat 통합)

## 9. 서버 실행 방법

```bash
# .env에 llama-server 경로 설정 (1회)
cd ~/Desktop/myaicoder
echo 'LLAMA_SERVER_PATH=/home/buttumaklevit/llm-server-env/llama.cpp/build/bin/llama-server' > .env

# 서비스 전체 시작
scripts/start-all.sh

# Health check
curl http://localhost:8080/health
```

## 10. 다음 세션 주요 작업: DGX Spark 이전

DGX Spark (ARM aarch64, GB10 Blackwell, 128GB 통합 메모리)로 서버 이전 예정.

**핵심**: ARM 아키텍처이므로 llama.cpp 재빌드 필수 (x86 바이너리 복사 불가)

```
SSH 접속 → 저장소 클론 → llama.cpp ARM 빌드 → 모델 배치
→ setup-dev.sh → start-all.sh → config.json IP 변경 → 재배포
```

**모델 업그레이드 검토**: 128GB 통합 메모리로 Qwen3.5-72B Q4 (~45GB)까지 가능

## 11. 다음 세션에서 먼저 볼 파일

- `docs/session-handoff-2026-03-15-session5.md` (이 파일)
- `docs/roadmap-2026-03.md`
- `docs/.pdca-status.json`
