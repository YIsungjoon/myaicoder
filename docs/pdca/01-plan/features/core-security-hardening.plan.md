# Core Security Hardening Planning Document

> **Summary**: Core Service + VS Code Extension의 보안 취약점 13건을 체계적으로 수정
>
> **Project**: myAiCoder
> **Version**: 0.1.0
> **Author**: AI (code-review 기반)
> **Date**: 2026-03-17
> **Status**: Draft

---

## 1. Overview

### 1.1 Purpose

2026-03-17 코드 리뷰에서 발견된 Core Service 9건 + VS Code Extension 4건의 보안 취약점을 수정하여, MCP 서버 모드 외부 노출 및 마켓플레이스 배포가 가능한 수준의 보안을 확보한다.

### 1.2 Background

- Core Service 품질 점수: **68/100** (보안 취약점이 주요 감점 요인)
- VS Code Extension 품질 점수: **72/100** (XSS, API 키 노출)
- 현재 로컬 CLI 전용으로는 운영 가능하나, MCP 서버 모드 외부 노출 시 **치명적 공격 표면** 존재
- 마켓플레이스 배포 전 XSS 및 API 키 노출 필수 해결

### 1.3 Related Documents

- 코드 리뷰 아카이브: `docs/pdca/07-archive/features/2026-03/gateway-code-review/`
- Core Service 코드: `services/myaicoder/src/myaicoder/`
- VS Code Extension 코드: `apps/vscode-extension/`

---

## 2. Scope

### 2.1 In Scope

- [x] Core: 파일 도구 Path Traversal 차단 (read/write/edit)
- [x] Core: SSRF 차단 (web_fetch)
- [x] Core: Bash/BuildRunner 명령 실행 강화
- [x] Core: 기본 API 키 하드코딩 제거
- [x] Core: 핫 패스 동적 import 제거
- [x] VSCode: XSS — marked + DOMPurify로 마크다운 렌더링 교체
- [x] VSCode: API 키를 환경변수로 전달
- [x] VSCode: nonce 생성 crypto.randomUUID 전환
- [x] VSCode: config 런타임 타입 검증

### 2.2 Out of Scope

- Gateway 서비스 (이전 사이클에서 수정 완료)
- 성능 최적화 (별도 사이클로 진행)
- 새 기능 추가
- Clean Architecture 리팩토링

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | WorkspaceGuard: 모든 파일 도구가 설정된 워크스페이스 루트 내에서만 동작 | Critical | Pending |
| FR-02 | SSRF 차단: private/loopback IP 대역 요청 차단 | Critical | Pending |
| FR-03 | BashTool: eval, exec, $(), backtick 패턴 추가 차단 | High | Pending |
| FR-04 | BuildRunnerTool: BashTool과 동일한 안전 검사 적용 | High | Pending |
| FR-05 | VSCode XSS: marked 라이브러리 + DOMPurify로 마크다운 렌더링 | Critical | Pending |
| FR-06 | VSCode API 키: CLI 인자 → 환경변수 전달 | Critical | Pending |
| FR-07 | Config 기본값: `api_key = "not-needed"` → `api_key = ""` | Low | Pending |
| FR-08 | 동적 import 제거: `__import__("json")` → module-level import | Low | Pending |
| FR-09 | VSCode nonce: Math.random → crypto.randomUUID | Medium | Pending |
| FR-10 | VSCode config: `as T` → 런타임 타입 가드 | Medium | Pending |

### 3.2 Non-Functional Requirements

| Category | Criteria | Measurement Method |
|----------|----------|-------------------|
| Security | Path Traversal 차단: 워크스페이스 외부 접근 0건 | 테스트 케이스 (`../`, 절대경로, symlink) |
| Security | SSRF 차단: 내부 IP(127.0.0.1, 10.*, 172.16.*, 192.168.*) 접근 0건 | 테스트 케이스 |
| Security | XSS 차단: 악성 마크다운 입력 시 스크립트 실행 0건 | 수동 + 자동 테스트 |
| Compatibility | 기존 178개 Core 테스트 + 20개 Extension 테스트 전부 통과 | pytest / npm test |
| Performance | 파일 도구 경로 검증 오버헤드 < 1ms | 벤치마크 |

---

## 4. Success Criteria

### 4.1 Definition of Done

- [ ] 13개 보안 이슈 전부 수정
- [ ] 각 이슈에 대한 테스트 케이스 작성
- [ ] 기존 테스트 전부 통과 (Core 178 + Extension 20)
- [ ] Gap Analysis Match Rate >= 90%

### 4.2 Quality Criteria

- [ ] Core Service 품질 점수 68 → 80+ 달성
- [ ] VS Code Extension 품질 점수 72 → 80+ 달성
- [ ] ruff check 0 errors
- [ ] TypeScript strict mode 0 errors

---

## 5. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| WorkspaceGuard가 정상 파일 접근을 차단 (false positive) | High | Medium | `--workspace-root` CLI 옵션으로 명시적 설정 + 기본값은 현재 디렉토리 |
| SSRF 차단이 정상 외부 URL을 차단 | Medium | Low | Private IP 대역만 차단, DNS rebinding은 resolved IP 체크 |
| marked/DOMPurify 추가로 Extension 번들 크기 증가 | Low | High | 이미 package.json에 marked 존재 (unused). DOMPurify는 ~7KB minified |
| BashTool 패턴 추가가 정상 명령 차단 | Medium | Medium | 차단 시 사용자에게 명확한 에러 메시지 + `--allow-bash` 플래그로 오버라이드 |

---

## 6. 기술적 사각지대 (Blind Spots)

| 사각지대 | 위험 시나리오 | 완화 전략 |
|----------|-------------|----------|
| **Symlink 우회** | `/workspace/link` → `/etc/passwd` symlink으로 WorkspaceGuard 우회 | `Path.resolve()` 후 검증 (심볼릭 링크 해석 후 실제 경로 체크) |
| **Unicode 정규화** | `..%2F` 등 URL 인코딩으로 path traversal | 경로 정규화(normalize) 후 검증 |
| **Race condition (TOCTOU)** | 검증 시점과 접근 시점 사이에 심볼릭 링크 생성 | 로컬 CLI 환경에서는 자체 사용자이므로 실용적 위험 낮음. MCP 서버 모드에서는 `O_NOFOLLOW` 사용 검토 |
| **DNS rebinding** | web_fetch에서 첫 resolve는 외부 IP, 실제 연결 시 내부 IP로 rebinding | Resolved IP 주소 기반 차단 (httpx의 `transport` 커스터마이징) |
| **LLM 프롬프트 인젝션** | 악성 파일 내용이 LLM 컨텍스트에 주입되어 도구 호출 유도 | 도구 실행 전 사용자 승인 (현재 `--allow-bash` 패턴 유지) |

---

## 7. Architecture Considerations

### 7.1 Project Level

| Level | Selected |
|-------|:--------:|
| **Enterprise** | ✅ |

### 7.2 구현 전략

| 항목 | 결정 | 근거 |
|------|------|------|
| WorkspaceGuard 위치 | `tools/base.py`의 `Tool` ABC에 공통 메서드 추가 | 모든 파일 도구가 상속, 한 곳에서 관리 |
| SSRF 필터 위치 | `tools/web_fetch.py` 내부 private 함수 | 단일 도구에만 적용 |
| Bash 안전 검사 | `tools/base.py`에 공통 `CommandValidator` 추출 | BashTool + BuildRunnerTool 공유 |
| VSCode 마크다운 | `webview/main.js` 기존 regex → marked + DOMPurify | hand-rolled regex 완전 교체 |

### 7.3 수정 대상 파일

```
services/myaicoder/src/myaicoder/
├── tools/
│   ├── base.py          ← WorkspaceGuard + CommandValidator 추가
│   ├── read.py          ← validate_path() 호출 추가
│   ├── write.py         ← validate_path() 호출 추가
│   ├── edit.py          ← validate_path() 호출 추가
│   ├── glob_tool.py     ← validate_path() 호출 추가
│   ├── grep_tool.py     ← validate_path() 호출 추가
│   ├── list_dir.py      ← validate_path() 호출 추가
│   ├── bash.py          ← CommandValidator 적용
│   ├── build_runner.py  ← CommandValidator 적용
│   └── web_fetch.py     ← SSRF 필터 추가
├── core/config.py       ← api_key 기본값 수정
└── llm/base.py          ← 동적 import 제거

apps/vscode-extension/
├── webview/main.js      ← marked + DOMPurify
├── src/mcp/client.ts    ← API 키 환경변수 전달
├── src/mcp/process.ts   ← spawn 옵션 수정
├── src/chat/panel.ts    ← crypto.randomUUID nonce
└── src/config.ts        ← 런타임 타입 가드
```

---

## 8. 구현 순서

| 순서 | 작업 | 예상 난이도 | 의존성 |
|:----:|------|:----------:|--------|
| 1 | `tools/base.py` — WorkspaceGuard + CommandValidator | 중 | 없음 |
| 2 | `tools/read.py, write.py, edit.py, glob, grep, list_dir` — validate_path 적용 | 하 | Step 1 |
| 3 | `tools/bash.py, build_runner.py` — CommandValidator 적용 | 하 | Step 1 |
| 4 | `tools/web_fetch.py` — SSRF 필터 | 하 | 없음 |
| 5 | `core/config.py, llm/base.py` — 소소한 수정 | 하 | 없음 |
| 6 | `webview/main.js` — marked + DOMPurify | 중 | npm install |
| 7 | `src/mcp/client.ts, process.ts` — API 키 환경변수 | 하 | 없음 |
| 8 | `src/chat/panel.ts, config.ts` — nonce + 타입 가드 | 하 | 없음 |

---

## 9. Next Steps

1. [ ] Design 문서 작성 (`/pdca design core-security-hardening`)
2. [ ] 구현 시작
3. [ ] Gap Analysis

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-03-17 | Initial draft (코드 리뷰 기반) | AI |
