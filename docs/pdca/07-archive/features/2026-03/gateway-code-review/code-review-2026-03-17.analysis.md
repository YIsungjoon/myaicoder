# 코드 리뷰 종합 분석 (2026-03-17)

## 분석 대상
| 서비스 | 경로 | 품질 점수 |
|--------|------|-----------|
| Core Service | `services/myaicoder/` | **68/100** |
| Gateway Service | `services/gateway/` | **78/100** |
| VS Code Extension | `apps/vscode-extension/` | **72/100** |

**전체 평균: 73/100**

---

## CRITICAL 이슈 종합 (즉시 수정 필요)

### 1. Core Service — 보안 (9건)

| # | 파일 | 이슈 | 위험도 |
|---|------|------|--------|
| C-01 | `tools/bash.py:10-17` | 블록리스트 우회 가능 (command injection) | 🔴 |
| C-02 | `tools/bash.py:101` | `create_subprocess_shell()` 샌드박스 없음 | 🔴 |
| C-03 | `tools/write.py:37-56` | Path traversal — 임의 파일 쓰기 | 🔴 |
| C-04 | `tools/read.py:42-78` | Path traversal — 임의 파일 읽기 | 🔴 |
| C-05 | `tools/edit.py:46-101` | Path traversal — 임의 파일 수정 | 🔴 |
| C-06 | `tools/build_runner.py:62-136` | 안전 검사 전무 | 🔴 |
| C-07 | `tools/web_fetch.py:44-101` | SSRF — 내부 네트워크 접근 가능 | 🔴 |
| C-08 | `core/config.py:16` | 하드코딩된 기본 API 키 | 🟡 |
| C-09 | `llm/base.py:43` | 핫 패스에서 동적 `__import__` | 🟡 |

### 2. Gateway Service — 기능 버그 + 보안 (5건)

| # | 파일 | 이슈 | 위험도 |
|---|------|------|--------|
| C-01 | `proxy.py:71-72` | `except Exception: pass` — 에러 무시 | 🔴 |
| C-02 | `proxy.py:152` | `if "resp" in dir()` — 불안정한 변수 존재 체크 | 🔴 |
| C-03 | `db.py:119-125` | fire-and-forget task 에러 추적 불가 | 🔴 |
| C-04 | `db.py:65` | DB URL 로깅 시 크리덴셜 노출 가능 | 🟡 |
| C-05 | `routes/v1.py:85-90` | ConnectError 시 동시성 슬롯 이중 해제 | 🔴 |

### 3. VS Code Extension — XSS + 보안 (4건)

| # | 파일 | 이슈 | 위험도 |
|---|------|------|--------|
| C-01 | `webview/main.js:66` | XSS — innerHTML로 마크다운 렌더링 | 🔴 |
| C-02 | `webview/main.js:25-32` | 코드 블록 렌더링 인젝션 벡터 | 🔴 |
| C-03 | `src/mcp/client.ts:55` | API 키가 CLI 인자로 노출 (`ps aux`) | 🔴 |
| C-04 | `src/config.ts:9-12` | 런타임 타입 검증 없는 `as T` 캐스팅 | 🟡 |

---

## WARNING 이슈 요약

### Core (17건 주요)
- 동기 파일 I/O가 async 메서드에서 이벤트 루프 블로킹
- HTTP 클라이언트 요청마다 새로 생성 (연결 재사용 없음)
- `SKIP_DIRS` 4곳 중복 정의
- BashTool/BuildRunnerTool 코드 85% 중복
- 한국어 토큰 추정 부정확 (`len//4` → 실제 1 token/char)

### Gateway (13건 주요)
- `catch_all` 핸들러 동시성 슬롯 미해제 → 영구 누수 (W10) **기능 버그**
- upstream HTTP 읽기 타임아웃 없음 → 리소스 고갈 위험 (W13)
- Prometheus 라벨 고카디널리티 → OOM 위험 (W7)
- 내부 토큰 비교에 `hmac.compare_digest` 미사용 (W4)
- Rate limit 분/시 카운터 비원자적 증가 (W12)

### VS Code Extension (12건 주요)
- 무한 재연결 루프 (백오프/최대 재시도 없음)
- `execSync` 블로킹 호출
- 임시 파일 미정리
- 메시지 히스토리 무제한 증가
- 취소가 UI만 처리 (서버측 실행 계속)
- `chat/panel.ts` 테스트 0% (가장 복잡한 모듈)

---

## 수정 우선순위 (Top 15)

| 순위 | 서비스 | 이슈 | 영향 | 난이도 |
|------|--------|------|------|--------|
| 1 | Core | WorkspaceGuard 구현 (C-03/04/05) | 파일시스템 전체 노출 차단 | 중 |
| 2 | Gateway | catch_all 동시성 슬롯 누수 (W10) | 프로덕션 서비스 중단 | 하 |
| 3 | Gateway | ConnectError 이중 해제 (C-05) | 동시성 카운트 오류 | 하 |
| 4 | VSCode | XSS 수정 — marked + DOMPurify (C-01/02) | 사용자 브라우저 공격 가능 | 중 |
| 5 | Core | SSRF 차단 — 내부 IP 블록 (C-07) | 내부 네트워크 스캔 차단 | 하 |
| 6 | Gateway | silent exception 로깅 추가 (C-01/03) | 장애 탐지 불가 해소 | 하 |
| 7 | VSCode | API 키 환경변수로 전달 (C-03) | 키 노출 차단 | 하 |
| 8 | Gateway | upstream 읽기 타임아웃 설정 (W13) | 리소스 고갈 방지 | 하 |
| 9 | Gateway | Prometheus 라벨 정규화 (W7) | OOM 방지 | 하 |
| 10 | Core | BashTool 샌드박스 강화 (C-01/02) | 명령 인젝션 완화 | 상 |
| 11 | Core | HTTP 클라이언트 재사용 (W-04) | 성능 개선 | 하 |
| 12 | VSCode | 재연결 백오프 + 최대 재시도 (W-11) | 안정성 향상 | 하 |
| 13 | Core | SKIP_DIRS 상수 통합 (W-02) | 유지보수성 | 하 |
| 14 | Gateway | hmac.compare_digest 적용 (W4) | 타이밍 공격 차단 | 하 |
| 15 | VSCode | execSync → async exec (W-10) | UI 프리즈 방지 | 하 |

---

## 긍정적 사항

### Core
- `LLMProvider` ABC를 통한 DIP 준수
- `ToolResult` 일관된 에러 패턴
- 대화 압축이 tool call chain splitting 방지
- 세션 원자적 쓰기 + 자가 복구 인덱스

### Gateway
- Concurrency control `max(0, ...)` 가드
- 구조화된 로깅 일관 적용
- Health check가 upstream 실제 확인

### VS Code Extension
- CSP nonce 기반 (VS Code 모범 사례)
- 판별 유니언 타입 (`WebviewMessage`/`ExtensionMessage`)
- TypeScript strict mode 활성화
- 파일 적용 전 dirty-state 확인

---

## 결론

**전체 품질: 73/100** — 핵심 기능은 잘 동작하나, 보안과 안정성에 개선이 필요합니다.

- **Core**: 로컬 CLI 전용이면 수용 가능하나, MCP 서버 모드 외부 노출 시 Critical
- **Gateway**: 동시성 슬롯 누수(W10)가 가장 급한 기능 버그
- **VS Code**: XSS와 API 키 노출이 마켓플레이스 배포 전 필수 수정 사항
