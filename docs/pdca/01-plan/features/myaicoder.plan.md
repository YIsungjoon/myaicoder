# Plan: myaicoder

**Feature**: myaicoder
**날짜**: 2026-03-13
**Phase**: Plan
**Level**: Enterprise
**Parent Context**: myAiCoder monorepo core service

---

## 1. 개요

`myaicoder`는 로컬 LLM 기반 AI 코딩 어시스턴트의 핵심 서비스다. CLI 인터페이스, agentic 실행 엔진, 내장 도구 레이어, MCP 서버/클라이언트 연결을 제공하며, 이후 상위 제품들(`ai-coder-cli`, `vscode-extension`)이 이 기능을 소비한다.

이 feature의 목적은 현재 구현된 코어 기능을 공식 PDCA 기준으로 정리하고, 문서와 실제 구현을 일치시키며, Check 단계로 넘길 수 있는 기준선을 만드는 것이다.

## 2. 핵심 요구사항

### 2.1 기능 요구사항

| ID | 기능 | 설명 | 우선순위 |
|----|------|------|----------|
| FR-01 | CLI 채팅 실행 | 대화형 및 one-shot 프롬프트 실행 | P0 |
| FR-02 | 로컬 LLM 연동 | vLLM 호환 OpenAI API 엔드포인트 연결 | P0 |
| FR-03 | Agentic 실행 엔진 | LLM 응답의 tool call을 반복 실행하는 루프 | P0 |
| FR-04 | 내장 도구 제공 | Read, Write, Edit, Glob, Grep, Bash 도구 제공 | P0 |
| FR-05 | 도구 승인 정책 | 위험 도구에 대한 승인/거부 흐름 | P0 |
| FR-06 | MCP 서버 모드 | 내장 도구를 MCP로 노출 | P0 |
| FR-07 | MCP 클라이언트 모드 | 외부 MCP 서버 도구를 프록시로 연결 | P1 |
| FR-08 | 설정 파일 로딩 | 프로젝트/사용자 범위 JSON 설정 로딩 | P1 |
| FR-09 | 스트리밍 출력 | 최종 응답의 스트리밍 출력 | P1 |
| FR-10 | agentic_task 노출 | MCP 서버에서 복합 작업용 고수준 도구 제공 | P2 |

### 2.2 비기능 요구사항

| ID | 항목 | 기준 |
|----|------|------|
| NFR-01 | 오프라인 우선 | 외부 SaaS API 없이 로컬 LLM 중심 동작 |
| NFR-02 | 확장성 | 새로운 Tool, MCP 서버를 쉽게 추가 가능 |
| NFR-03 | 안전성 | Write/Edit/Bash는 승인 정책 또는 제한 적용 |
| NFR-04 | 호환성 | Python 3.11+, MCP 1.x, vLLM OpenAI 호환 API |
| NFR-05 | 테스트 가능성 | 핵심 코어/도구/MCP 레이어에 자동 테스트 존재 |

## 3. 범위

### 3.1 In Scope

| # | 항목 | 우선순위 |
|---|------|----------|
| 1 | CLI 엔트리포인트 및 slash command | P0 |
| 2 | `AgentEngine` 기반 agentic loop | P0 |
| 3 | Conversation / Context 관리 | P0 |
| 4 | Built-in tools registry 및 실행 | P0 |
| 5 | MCP Server (`myaicoder serve`) | P0 |
| 6 | MCP Client로 외부 서버 연결 | P1 |
| 7 | AppConfig / MCPConfig 로딩 | P1 |
| 8 | Rich 기반 터미널 UI | P1 |
| 9 | 단위/통합 성격의 pytest 스위트 | P0 |

### 3.2 Out of Scope

| 항목 | 사유 |
|------|------|
| GUI 프론트엔드 자체 구현 | `vscode-extension` 등 상위 feature에서 담당 |
| 원격 상용 LLM provider 다중 지원 | 현재는 vLLM 중심 |
| Marketplace/배포 자동화 | 별도 feature |
| 멀티유저 서버 운영 기능 | 현재 범위는 단일 사용자 로컬 워크플로우 |

## 4. 성공 기준

- `myaicoder`의 구현 범위를 설명하는 Plan/Design 문서가 `docs/pdca` 체계에 존재한다
- 현재 코드 구조와 핵심 모듈 책임이 문서화된다
- 테스트 실행 기준이 정리된다
- Gap Analysis를 수행할 수 있을 만큼 요구사항과 설계 기준이 명확해진다

## 5. 확인된 현재 상태

- 구현은 이미 상당 부분 존재한다
- 테스트는 `services/myaicoder` 기준으로 통과한다
- 하지만 공식 PDCA 문서가 비어 있어 현재 상태를 평가하거나 종료 처리하기 어렵다

따라서 이번 단계의 핵심 목표는 신규 대규모 구현보다, 현재 코어 서비스를 공식 기준에 맞춰 문서화하고 평가 가능 상태로 만드는 것이다.
