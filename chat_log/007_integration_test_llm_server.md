# 007. 통합 테스트: LLM 서버 연동 검증

**날짜**: 2026-03-13
**작업 유형**: PDCA Do (검증)
**Feature**: ai-coder-cli
**Phase**: Phase 1 / 7 (통합 테스트)

## 요약

로컬 LLM 서버(llama-server Docker)와 myAiCoder CLI 통합 테스트 완료.
Qwen3.5의 `reasoning_content` 문제 발견 및 해결.

## LLM 서버 환경

| 항목 | 값 |
|------|-----|
| 서버 | llama-server (Docker) |
| 포트 | 8080 |
| 모델 | Qwen3.5-27B-Q4_0.gguf |
| GPU | RTX 4090 24GB |
| API | OpenAI-compatible (`/v1/chat/completions`) |

### 서버 시도 이력
1. **vLLM** (`vllm serve`) → GGUF 포맷 미지원 (`qwen35 architecture not supported`)
2. **llama-cpp-python** → 모델 로드 실패 (버전 호환성)
3. **llama-server (Docker)** → 이미 실행 중이었음, 포트 8080에서 정상 동작 확인

## 발견 및 수정 사항

### 1. Qwen3.5 reasoning_content 문제

**문제**: Qwen3.5는 thinking 모드에서 `content` 필드가 비어있고, 사고 과정이 `reasoning_content` 필드에 반환됨.
OpenAI SDK는 이 비표준 필드를 무시하므로, 응답이 빈 문자열로 나옴.

**해결**:
- `vllm_provider.py`: OpenAI SDK 대신 raw httpx 요청으로 `reasoning_content` 캡처
- `content` 비어있으면 `reasoning_content`로 fallback

### 2. /no_think 태그로 thinking 비활성화

**문제**: fallback으로 reasoning_content 사용 시, 응답에 thinking 과정이 그대로 노출됨.

**해결**:
- `context.py`: 시스템 프롬프트 맨 앞에 `/no_think` 태그 추가
- Qwen3.5가 thinking 없이 직접 `content` 필드에 답변 반환
- `reasoning_content`는 별도 저장 (`_last_reasoning`) - 향후 UI에서 선택적 표시 가능

### 검증 결과

```
[Health Check] OK
[/no_think Chat]
  Content: Hello          ← 깔끔한 응답
  Reasoning: (별도 저장)   ← thinking 과정 분리
  Tokens: 34 in / 257 out
```

## 변경 파일

| 파일 | 변경 내용 |
|------|-----------|
| `src/myaicoder/core/context.py` | 시스템 프롬프트에 `/no_think` 추가 |
| `src/myaicoder/llm/vllm_provider.py` | `_last_reasoning` 속성 추가 |

## 테스트 결과
- 단위 테스트: 10 passed, 2 skipped
- 통합 테스트 (수동): Health Check OK, Basic Chat OK, Multi-turn OK

## 교훈

1. vLLM은 아직 Qwen3.5 GGUF를 지원하지 않음 (v0.17.1 기준)
2. llama-server (llama.cpp)가 GGUF 모델에 가장 안정적
3. Qwen3.5의 `/no_think` 태그는 시스템 프롬프트에서 동작함
4. OpenAI SDK만으로는 비표준 필드 캡처 불가 → raw HTTP 필요

## PDCA 상태
```
[Plan] ✅ → [Design] ✅ → [Do] 🔄 (Phase 1 완료 + 통합테스트 완료) → [Check] ⏳ → [Act] ⏳
```

## 다음 단계
- Phase 2: Tool Use 구현 (Read, Write, Edit, Glob, Grep, Bash)
