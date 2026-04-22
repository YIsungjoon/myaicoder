# Core Security Hardening — Archive

> **Status**: Archived
>
> **Project**: myAiCoder
> **Feature**: core-security-hardening
> **Archive Date**: 2026-04-22
> **Source Report**: [core-security-hardening.report.md](../../06-report/features/core-security-hardening.report.md)

---

## 1. Archive Summary

`core-security-hardening` feature has been archived after completing the full PDCA cycle.

- **시작일**: 2026-03-17 (코드 리뷰 기반 13건 보안 취약점 식별)
- **완료일**: 2026-04-22 (FR-05 XSS 수정으로 목표 달성)
- **최종 Match Rate**: 93%
- **완료 FR**: 9 / 10 (FR-10 Low priority 잔존 — 차기 사이클 권고)

| 지표 | 초기 | 최종 | 개선 |
|------|------|------|------|
| Match Rate | 80% | **93%** | +13%p |
| Core 품질 점수 | 68 | **82** | +14점 |
| Extension 품질 점수 | 72 | **85** | +13점 |
| 완료 FR | 8/10 | **9/10** | +1 |

---

## 2. 완료된 보안 항목

| FR | 설명 | 우선순위 | 상태 |
|----|------|---------|------|
| FR-01 | WorkspaceGuard — Path Traversal 차단 | Critical | PASS |
| FR-02 | SSRF 필터 — 8개 내부 네트워크 차단 | Critical | PASS |
| FR-03 | CommandValidator — BashTool 위험 명령 차단 | High | PASS |
| FR-04 | BuildRunnerTool validate_command 적용 | High | PASS |
| FR-05 | Webview XSS — marked + DOMPurify 교체 | Critical | PASS |
| FR-06 | API 키 환경변수 전달 | Critical | PASS |
| FR-07 | api_key 기본값 `"not-needed"` → `""` | Low | PASS |
| FR-08 | 동적 import 제거 | Low | PASS |
| FR-09 | crypto.randomUUID() nonce 전환 | Medium | PASS |
| FR-10 | Config 타입 가드 (`get<T>(key, default)`) | Low | 미구현 |

---

## 3. 주요 커밋

| 커밋 | 날짜 | 내용 |
|------|------|------|
| `abf531e` | 2026-03-17 | WorkspaceGuard, SSRF 차단, CommandValidator (8/10 FR) |
| `3ee56c2` | 2026-04-22 | FR-05 XSS 수정 (marked+DOMPurify) + LLM 서버 연결 개선 |
| `de4eb1e` | 2026-04-22 | 완료 보고서 작성 |

---

## 4. Archived Documents

- Plan: [core-security-hardening.plan.md](../../01-plan/features/core-security-hardening.plan.md)
- Design: [core-security-hardening.design.md](../../02-design/features/core-security-hardening.design.md)
- Analysis: [core-security-hardening.analysis.md](../../03-analysis/core-security-hardening.analysis.md)
- Report: [core-security-hardening.report.md](../../06-report/features/core-security-hardening.report.md)

---

## 5. 잔존 백로그

| 항목 | 우선순위 | 권고 시점 |
|------|---------|---------|
| FR-10: `config.ts` 타입 가드 (`get<T>(key, defaultValue)`) | Low | 차기 vscode-extension 개선 사이클 |
| FR-03: `rm -rf /path` 패턴 보강 | Medium | 보안 강화 사이클 |
| 침투 테스트 | High | 마켓플레이스 배포 전 |

---

## 6. 재사용 가능한 패턴

이 사이클에서 도입된 패턴은 다른 피처에서 재사용 가능합니다:

- **WorkspaceGuard** (`tools/base.py`): 파일 접근 제한이 필요한 모든 MCP 서버 도구
- **CommandValidator** (`tools/base.py`): 명령 실행 도구의 안전 검사 공통 모듈
- **`_ENV_OVERRIDES` 매핑 테이블** (`core/config.py`): 환경변수 오버라이드 확장 시 참조
- **esbuild webview 번들** (`esbuild.config.mjs`): browser-target 번들이 필요한 webview 추가 시 참조
