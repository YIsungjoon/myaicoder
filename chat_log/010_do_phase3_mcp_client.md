# 010. Do Phase 3: MCP Client 구현

**날짜**: 2026-03-13
**작업 유형**: PDCA Do (구현 + 통합 테스트)
**Feature**: ai-coder-cli
**Phase**: Phase 3 / 7

## 구현 내용

### Design 문서 Phase 3 체크리스트

- [x] `mcp/config.py` — .mcp.json 파싱 (Claude Code 호환, ${VAR} 치환)
- [x] `mcp/client.py` — MCP Client (공식 SDK 사용, stdio + HTTP 트랜스포트)
- [x] `mcp/client.py` — MCPToolProxy (MCP 도구를 Tool ABC로 래핑)
- [x] `cli.py` 확장 — MCP 서버 자동 연결 + `mcp list` 서브커맨드
- [x] `tools/registry.py`와 통합 — MCP 도구를 ToolRegistry에 등록
- [x] 테스트 작성 (46 passed, 3 skipped)
- [x] MCP filesystem 서버 통합 테스트 (14개 도구 발견, read_file 호출 성공)
- [x] E2E 테스트 (LLM + Built-in 6 + MCP 14 = 20개 도구)

### 생성/수정 파일 목록

```
services/myaicoder/
├── src/myaicoder/
│   ├── cli.py                     # MCP 서버 자동 연결 + mcp list 커맨드
│   └── mcp/
│       ├── __init__.py
│       ├── config.py              # .mcp.json 파싱 (Claude Code 호환)
│       └── client.py              # MCP Client + MCPToolProxy
├── tests/
│   └── test_mcp/
│       ├── __init__.py
│       ├── test_config.py         # Config 테스트 (4)
│       └── test_client.py         # Client 테스트 (2+1 skipped)
```

### MCP 아키텍처

```
.mcp.json (Claude Code 호환)
    │
    ▼
MCPConfig.load() ── ${VAR} 환경변수 치환
    │
    ▼
MCPClient.connect_all()
    │
    ├── stdio: subprocess → MCP SDK ClientSession
    │     initialize → list_tools → MCPToolProxy 생성
    │
    └── http: httpx → Streamable HTTP → ClientSession
          initialize → list_tools → MCPToolProxy 생성
    │
    ▼
ToolRegistry.register(MCPToolProxy)
    │
    ▼
AgentEngine → LLM이 Built-in + MCP 도구 모두 사용 가능
```

### 통합 테스트 결과

| 테스트 | 결과 |
|--------|------|
| MCP filesystem 서버 연결 | ✅ 14개 도구 발견 |
| read_file 도구 호출 | ✅ 파일 내용 반환 |
| E2E (LLM + 20개 도구) | ✅ 적절한 도구 선택 + 실행 |
| 단위 테스트 | 46 passed, 3 skipped |

### .mcp.json 호환 형식

```json
{
  "mcpServers": {
    "github": {
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_TOKEN": "${GITHUB_TOKEN}" }
    },
    "remote": {
      "transport": "http",
      "url": "https://mcp.example.com/sse"
    }
  }
}
```

## PDCA 상태
```
[Plan] ✅ → [Design] ✅ → [Do] 🔄 (Phase 3/7 완료) → [Check] ⏳ → [Act] ⏳
```

## 다음 단계
- Phase 4: MCP Server (자체 Built-in 도구를 MCP 서버로 노출)
- Phase 5: 컨텍스트 + 세션 (토큰 관리, 히스토리 압축)
- Phase 6: VS Code 확장
- Phase 7: 안정화 + 배포
