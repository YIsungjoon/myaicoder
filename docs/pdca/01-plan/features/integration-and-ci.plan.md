# Plan: integration-and-ci

**Feature**: integration-and-ci
**날짜**: 2026-03-13
**Phase**: Plan
**Level**: Enterprise
**Parent Context**: myAiCoder monorepo quality baseline

---

## 1. 개요

기능 PDCA 사이클이 대부분 완료된 현재 시점에서, 저장소 전반의 품질 보증 체계를 구축한다. 목표는 개별 feature 품질을 넘어서, 저장소 차원의 통합 테스트 실행 경로와 CI 자동화 기준을 확립하는 것이다.

## 2. 핵심 요구사항

### 2.1 기능 요구사항

| ID | 기능 | 설명 | 우선순위 |
|----|------|------|----------|
| FR-01 | Python 테스트 자동 실행 | `services/myaicoder` 테스트를 CI에서 실행 | P0 |
| FR-02 | VS Code extension 테스트 자동 실행 | `apps/vscode-extension` 테스트를 CI에서 실행 | P0 |
| FR-03 | Monorepo 기준 실행 경로 정리 | 루트 기준에서 재현 가능한 테스트 명령 정리 | P0 |
| FR-04 | GitHub Actions CI | push / PR 기준 CI 워크플로 추가 | P0 |
| FR-05 | 실패 시 빠른 피드백 | lint/test 실패가 명확히 드러나는 단계 구성 | P1 |
| FR-06 | 통합 테스트 확장 기반 | 향후 MCP 실연동 테스트를 붙일 수 있는 구조 확보 | P1 |

### 2.2 비기능 요구사항

| ID | 항목 | 기준 |
|----|------|------|
| NFR-01 | 재현성 | 로컬과 CI 명령이 최대한 동일해야 함 |
| NFR-02 | 단순성 | 초기 CI는 과도한 매트릭스 없이 유지보수 가능해야 함 |
| NFR-03 | 분리성 | Python / Node 테스트를 독립 job 또는 단계로 구분 |
| NFR-04 | 확장성 | 이후 보안 검사, 배포, 실통합 테스트를 추가 가능해야 함 |

## 3. 범위

### 3.1 In Scope

| # | 항목 | 우선순위 |
|---|------|----------|
| 1 | 저장소 기준 테스트 진입점 정리 | P0 |
| 2 | `myaicoder` pytest 실행 자동화 | P0 |
| 3 | `vscode-extension` vitest 실행 자동화 | P0 |
| 4 | GitHub Actions 워크플로 작성 | P0 |
| 5 | 관련 문서화 | P0 |

### 3.2 Out of Scope

| 항목 | 사유 |
|------|------|
| 실제 MCP 서버/LLM 서버를 띄우는 장시간 실통합 테스트 | 후속 단계에서 별도 관리 |
| 보안 스캔(SAST/secret/license) 전체 도입 | 후속 품질 단계 |
| 배포 파이프라인 | 별도 feature |
| 커버리지 업로드 / 외부 SaaS 연동 | 초기 CI 범위 밖 |

## 4. 성공 기준

- 저장소에 CI 워크플로 파일이 추가된다
- 로컬 기준 실행 가능한 테스트 명령이 문서화된다
- `myaicoder`와 `vscode-extension` 테스트가 CI에서 재현 가능하다
- 이후 실통합 테스트를 붙일 수 있는 구조가 남는다

## 5. 현재 확인된 출발점

- `myaicoder`: `uv run pytest tests -q` 경로가 안정적
- `vscode-extension`: `pnpm --filter myaicoder test` 경로가 안정적
- 저장소에는 아직 `.github/workflows/`가 없다

따라서 이번 feature는 “새 기능 개발”이 아니라 “이미 만든 기능을 자동 검증 가능한 제품 상태로 고정”하는 작업이다.
