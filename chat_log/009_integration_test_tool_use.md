# 009. 통합 테스트: Tool Use (Agentic Loop)

**날짜**: 2026-03-13
**작업 유형**: PDCA Do (검증)
**Feature**: ai-coder-cli
**Phase**: Phase 2 / 7 (통합 테스트)

## 요약

로컬 LLM (Qwen3.5-27B, llama-server)과 6개 Built-in Tool의 Agentic Loop 통합 테스트 완료.
LLM이 적절한 도구를 선택하고, 실행 결과를 기반으로 최종 응답을 생성하는 전체 흐름 검증.

## 테스트 결과

### Test 1: Tool Schema 전달 + Tool Call 파싱
- 6개 도구 스키마를 LLM에 전송
- LLM이 `Read` 도구를 정확히 선택
- `tool_calls` 파싱 정상 (id, name, arguments)

### Test 2: Read → 응답 (Agentic Loop)
- 입력: "Read /tmp/test_tooluse.txt and tell me the secret code."
- LLM → Read tool_call → 실행 → 결과 피드백 → "secret code는 42"
- 전체 루프 정상 동작

### Test 3: Bash 명령어 실행
- 입력: "Run ls and confirm file exists."
- LLM → Bash tool_call → 실행 → "파일 존재 확인"

### Test 4: Write + Read (다중 도구 호출)
- 입력: "Write to file, then read it back."
- LLM → Write → Read → "Successfully wrote and confirmed"
- 실제 파일 내용 검증 완료

## 핵심 확인 사항

| 항목 | 상태 |
|------|------|
| Tool Schema → LLM 전달 | ✅ |
| LLM → tool_calls 반환 | ✅ |
| tool_calls 파싱 (id, name, arguments) | ✅ |
| Tool 실행 (Read, Write, Bash) | ✅ |
| 실행 결과 → LLM 피드백 | ✅ |
| Agentic Loop 반복 (다중 도구) | ✅ |
| 최종 텍스트 응답 생성 | ✅ |

## PDCA 상태
```
[Plan] ✅ → [Design] ✅ → [Do] 🔄 (Phase 2 통합테스트 완료) → [Check] ⏳ → [Act] ⏳
```

## 다음 단계
- Phase 3: MCP Client 구현
