# Session Handoff - 2026-03-15 (Session 5)

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

## 2. 이번 세션에서 한 일

### 2.1 windows-installer (Feature #18, 100%)
- GitHub Actions `windows-latest` runner에서 PyInstaller .exe 자동 빌드
- `installer-v*` 태그 push → CI → Release에 `myaicoder-windows-setup.zip` 자동 첨부
- 산출물: `build-windows-installer.yml` 신규, `myaicoder.spec` 수정
- **CI 디버깅 6회** (v0.1.0 ~ v0.1.6): PyInstaller 미설치, MSYS 경로 맹글링, SPECPATH dirname 버그, npm→pnpm 변경

### 2.2 workspace-integration (Feature #19, 100%) — V0.2
- 3가지 관문 구현:
  - **눈**: getOpenTabs(), getWorkspaceInfo(), buildPrompt 강화
  - **손발**: --working-dir 워크스페이스 연결, parseToolResults 도구 결과 표시
  - **코드 수정**: apply.ts (showDiff, applyToFile), [Apply] 버튼, Diff View
- 엣지 케이스 3건 반영: dirty state 방어, 정규식 관대화, 신규 파일 diff

### 2.3 Extension Windows 호환 수정
- `which` → `where` (Windows 호환)
- `path.normalize()` 경로 정규화
- `.venv/Scripts/` Windows venv 경로
- `stdio: ['pipe', 'pipe', 'pipe']` 에러 출력 숨김

### 2.4 대화 연속성 수정
- AgentEngine을 MCP 서버 수명 동안 영속화 (매 호출 생성 → 1회 생성)
- ConversationManager가 32K 컨텍스트 자동 관리 (기존 context-management 활용)
- `restoreMessages()`로 사이드바 전환 시 채팅 보존
- Extension 측 중복 히스토리 제거 (CLI가 관리)

### 2.5 기타 수정
- `enableAgentic` 기본값 true 변경
- `--llm-url`, `--model-name` CLI 옵션 추가 (원격 LLM 연결)
- `os.urandom(2)` → `os.urandom(4)` flaky test 수정
- Extension에서 llmUrl/modelName을 CLI spawn 시 전달

### 2.6 Windows E2E 테스트 결과
- 서버: LLM(8001) + Gateway(8080), IP 192.168.0.22
- Windows 노트북에서:
  - 설치하기.bat 실행 ✅
  - CLI 설치 확인 ✅
  - LLM 서버 연결 (직접 8001 포트) ✅
  - 채팅 응답 ✅
  - 대화 기억 (세션 내) ✅
  - 사이드바 전환 후 대화 유지 ✅

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

## 6. 서버 상태

| 서비스 | 포트 | 상태 |
|--------|------|------|
| LLM Server (llama.cpp) | 8001 | 실행 중 |
| Gateway | 8080 | 실행 중 |
| IP | 192.168.0.22 | 외부 접근 가능 |

## 7. 릴리즈 태그 이력

| 태그 | 결과 | 내용 |
|------|------|------|
| installer-v0.1.0 | ❌ flaky test | session ID urandom(2) |
| installer-v0.1.2 | ❌ PyInstaller 미설치 | uv pip install pyinstaller 추가 |
| installer-v0.1.3~4 | ❌ MSYS 경로 | WORKSPACE_ROOT env |
| installer-v0.1.5 | ❌ npm ci 실패 | pnpm 변경 |
| installer-v0.1.6 | ✅ CI 첫 성공 | |
| installer-v0.1.7 | ✅ Extension 수정 | which→where |
| installer-v0.1.9 | ✅ --llm-url 추가 | |
| installer-v0.2.0 | ✅ workspace-integration | V0.2 |
| installer-v0.2.2 | ✅ 대화 연속성 | AgentEngine 영속화 |

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

## 9. 다음 세션에서 먼저 볼 파일

- `docs/session-handoff-2026-03-15-session5.md` (이 파일)
- `docs/roadmap-2026-03.md`
- `docs/.pdca-status.json`
