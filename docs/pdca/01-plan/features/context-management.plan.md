# Plan: context-management

**Feature**: context-management
**날짜**: 2026-03-14
**Phase**: Plan
**Level**: Enterprise
**Parent Context**: myAiCoder — 대화 컨텍스트 관리, 압축, 토큰 예산 제어

---

## 1. 개요

대화가 길어지면 **컨텍스트 윈도우를 초과하여 LLM이 응답하지 못하는 문제**를 해결한다.

### 현재 상태

| 항목 | 현재 구현 | 문제 |
|------|----------|------|
| `ConversationManager` | 단순 append-only 리스트 | 메시지 무한 증가, 토큰 제한 없음 |
| `ContextConfig` | `max_tokens=32768`, `compression_threshold=0.8` 정의됨 | **코드에서 사용 안 함** (dead config) |
| 토큰 추정 | `chars // 4` (고정 비율) | 시스템 프롬프트/도구 스키마 미반영 |
| 도구 결과 | 개별 4000 토큰 절단 | 누적 히스토리 크기 고려 안 함 |
| 대화 지속성 | 메모리 전용 | CLI 재시작 시 대화 소실 |
| `/clear` 명령 | 전체 히스토리 삭제 | 전부 또는 전무 — 중간 없음 |

### 핵심 문제 시나리오

```
사용자: (대규모 코드베이스 분석 요청)
  → Read tool: 10개 파일 × 500줄 = ~20,000 토큰
  → 도구 결과 누적
  → 추가 질문 3~4회
  → 총 히스토리 > 32,768 토큰
  → LLM: "context length exceeded" 에러 또는 이전 대화 망각
```

## 2. 핵심 요구사항

### 2.1 기능 요구사항

| ID | 기능 | 설명 | 우선순위 |
|----|------|------|----------|
| FR-01 | 토큰 예산 제어 | max_tokens 초과 시 자동으로 오래된 메시지 제거 | P0 |
| FR-02 | 대화 압축 | compression_threshold 도달 시 오래된 대화를 요약으로 압축 | P0 |
| FR-03 | 시스템 프롬프트 보호 | 시스템 프롬프트 + 최근 메시지는 절대 제거 안 함 | P0 |
| FR-04 | 토큰 카운팅 개선 | tiktoken 또는 모델별 토크나이저로 정확한 토큰 수 계산 | P1 |
| FR-05 | 압축 상태 표시 | 압축 발생 시 사용자에게 알림 | P0 |
| FR-06 | CLI `/compact` 명령 | 수동 압축 트리거 | P1 |
| FR-07 | 대화 저장/로드 | 대화를 파일로 저장하고 다음 세션에서 복원 | P2 |

### 2.2 비기능 요구사항

| ID | 항목 | 기준 |
|----|------|------|
| NFR-01 | 압축 지연 | 사용자 체감 1초 이내 (LLM 호출 없는 방식) |
| NFR-02 | 정보 보존 | 압축 후에도 핵심 결정/결과가 유지됨 |
| NFR-03 | 하위 호환 | 기존 ConversationManager API 깨지지 않음 |
| NFR-04 | 테스트 가능 | 토큰 계산, 압축 로직에 단위 테스트 존재 |

## 3. 범위

### 3.1 In Scope

| # | 항목 | 우선순위 |
|---|------|----------|
| 1 | `ConversationManager`에 토큰 예산 제어 적용 (max_tokens 활성화) | P0 |
| 2 | Sliding Window + 요약 기반 압축 전략 | P0 |
| 3 | 시스템 프롬프트 + 도구 스키마 토큰 예약 | P0 |
| 4 | `ContextConfig` 실제 연결 (dead config 활성화) | P0 |
| 5 | 압축 발생 시 UI 알림 | P0 |
| 6 | CLI `/compact` 명령 | P1 |
| 7 | pytest 테스트 | P0 |

### 3.2 Out of Scope

| 항목 | 사유 |
|------|------|
| 대화 저장/로드 (P2) | 별도 feature |
| LLM 기반 요약 (LLM 호출로 압축) | 느림 + 토큰 소비, 추후 확장 |
| 다중 대화 세션 관리 | 별도 feature |
| RAG (검색 증강 생성) | 별도 feature |

## 4. 압축 전략

### 4.1 Sliding Window + Summary Prefix

```
┌─────────────────────────────────────────────────────┐
│ System Prompt (보호됨, 제거 불가)                     │
├─────────────────────────────────────────────────────┤
│ [Summary] 이전 대화 요약                              │ ← 압축된 과거
│   "사용자가 gateway 코드를 분석하고 rate limiting을    │
│    추가하기로 결정함. config.py에 RateLimitConfig..."   │
├─────────────────────────────────────────────────────┤
│ Recent Message 1 (user)                              │ ← 최근 윈도우
│ Recent Message 2 (assistant + tool_calls)             │   (보존됨)
│ Recent Message 3 (tool result)                        │
│ Recent Message 4 (assistant)                          │
│ Recent Message 5 (user) ← 현재 질문                   │
└─────────────────────────────────────────────────────┘
```

### 4.2 압축 트리거

```
compression_threshold = 0.8 (80%)
max_tokens = 32768

사용 토큰 > 32768 × 0.8 = 26,214 토큰
  → 압축 트리거
  → 오래된 메시지를 요약으로 교체
  → 최근 N개 메시지는 보존
```

### 4.3 요약 생성 방식 (LLM 없이)

P0에서는 **LLM 호출 없이** 규칙 기반 요약을 사용한다:

1. **도구 결과 축소**: 전체 파일 내용 → "Read: /path/to/file.py (500 lines)"
2. **어시스턴트 응답 축소**: 긴 설명 → 첫 2줄 + "..."
3. **user/assistant 쌍 병합**: 여러 턴 → "[이전 대화 N턴: 주제 키워드]"

이 방식의 장점:
- 지연 시간 0 (LLM 호출 없음)
- 추가 토큰 소비 없음
- 결정론적 (테스트 가능)

## 5. 토큰 예산 배분

```
Total Budget: max_tokens (e.g., 32,768)

┌────────────────────────────────────────┐
│ Reserved: System Prompt     ~2,000     │
│ Reserved: Tool Schemas      ~1,000     │
│ Reserved: Response Buffer   ~4,000     │ ← LLM 응답 공간
├────────────────────────────────────────┤
│ Available for History:     ~25,768     │
│   ├─ Summary Prefix:      ~2,000 max  │
│   └─ Recent Messages:     ~23,768     │
└────────────────────────────────────────┘
```

## 6. CLI 통합

```bash
# 기존
/clear       # 전체 히스토리 삭제 (유지)

# 신규
/compact     # 수동 압축 트리거 (P1)
/tokens      # 현재 토큰 사용량 표시 (P1)
```

## 7. 성공 기준

- [ ] `max_tokens` 초과 시 자동으로 오래된 메시지가 제거/압축된다
- [ ] `compression_threshold` 도달 시 압축이 트리거된다
- [ ] 시스템 프롬프트와 최근 메시지는 압축되지 않는다
- [ ] 압축 발생 시 사용자에게 알림이 표시된다
- [ ] 기존 `ConversationManager` API가 깨지지 않는다
- [ ] 테스트가 `uv run pytest tests -q`로 통과한다
- [ ] 긴 대화(50턴+) 시뮬레이션에서 토큰 예산을 초과하지 않는다

## 8. 의존 관계

```
context-management (이번 feature)
  ├── modifies: core/conversation.py (ConversationManager 확장)
  ├── modifies: core/engine.py (토큰 예산 연결)
  ├── modifies: cli.py (/compact, 압축 알림)
  ├── activates: core/config.py (ContextConfig — dead config 활성화)
  └── consumed by: CLI 사용자, AgentEngine
```

## 9. 기술 결정 사항

| 항목 | 결정 | 근거 |
|------|------|------|
| 압축 방식 | 규칙 기반 (LLM 없이) | 지연 0ms, 토큰 소비 없음, 결정론적 |
| 토큰 추정 | chars // 4 유지 (P0) | tiktoken은 P1, 현재 충분히 실용적 |
| 보존 윈도우 | 최근 N턴 (설정 가능) | 최신 대화 맥락 유지 |
| 요약 저장 | Message(role="system", content="[Summary]...") | 기존 API 호환 |
| 압축 시점 | get_messages() 호출 시 lazy 검사 | 불필요한 압축 방지 |

## 10. 리스크

| 리스크 | 영향 | 대응 |
|--------|------|------|
| 규칙 기반 요약의 정보 손실 | 맥락 누락 | 핵심 정보(파일 경로, 결정사항) 보존 규칙 |
| 도구 호출 체인 파괴 | tool_call_id 참조 끊김 | 도구 호출 쌍은 함께 제거/보존 |
| 토큰 추정 오차 | 실제 초과 | 응답 버퍼 4000 토큰 여유 |
| 압축 후 대화 품질 저하 | UX 저하 | 압축 알림 + /compact 수동 제어 |
