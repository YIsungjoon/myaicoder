# Act: myaicoder (Iteration 1)

**Feature**: myaicoder
**날짜**: 2026-03-13
**Phase**: Act
**Iteration**: 1
**Input**: [myaicoder.analysis.md](../../03-analysis/myaicoder.analysis.md)

---

## 1. 목적

Check 단계에서 확인된 소규모 정합성 갭을 즉시 수정하여, `myaicoder`를 report 단계로 넘길 수 있는 수준으로 끌어올린다.

## 2. 반영한 조치

### 2.1 포트 안내 정렬

- [cli.py](/home/laon/Desktop/myAiCoder/services/myaicoder/src/myaicoder/cli.py)
  - `--vllm-url` help 문구를 `http://localhost:8080/v1` 기준으로 수정
  - 연결 실패 안내 문구의 예시 포트를 `8080`으로 수정
- [start_vllm.sh](/home/laon/Desktop/myAiCoder/services/myaicoder/scripts/start_vllm.sh)
  - 기본 포트를 `8080`으로 수정

### 2.2 MCPClient 공개 API 보완

- [client.py](/home/laon/Desktop/myAiCoder/services/myaicoder/src/myaicoder/mcp/client.py)
  - 서버별 tool metadata cache 추가
  - `get_tool_proxies()`가 실제 proxy 목록을 반환하도록 구현
  - `discover_tools()`와 `close()`도 cache lifecycle에 맞춰 정리

### 2.3 테스트 보강

- [test_client.py](/home/laon/Desktop/myAiCoder/services/myaicoder/tests/test_mcp/test_client.py)
  - `get_tool_proxies()`의 cached proxy 반환 테스트 추가

### 2.4 warning 원인 수정

- [bash.py](/home/laon/Desktop/myAiCoder/services/myaicoder/src/myaicoder/tools/bash.py)
  - timeout 경로에서 subprocess를 `kill()`만 하던 동작을 정리
  - kill 후 `await proc.communicate()`로 프로세스와 pipe를 수거하도록 수정
  - pytest 종료 시 발생하던 event loop / subprocess warning 해소

## 3. 검증 결과

실행 명령:

```bash
cd services/myaicoder
uv run pytest tests -q
```

결과:

- `67 passed`
- `3 skipped`
- warning `0`

## 4. 남은 항목

- 실제 MCP 연동 통합 테스트는 여전히 skip 상태

## 5. 다음 단계

- 테스트 재실행
- 필요 시 analysis 문서의 잔여 갭 재평가
- report 문서 작성 여부 결정
