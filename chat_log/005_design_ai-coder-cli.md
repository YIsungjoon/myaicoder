# 005. Design 작성: myAiCoder

**날짜**: 2026-03-13
**작업 유형**: PDCA Design
**Feature**: ai-coder-cli

## 수행 내용

Plan 문서의 결정 사항을 기반으로 상세 설계 문서 작성.

### 설계된 주요 구조

#### 시스템 4-Layer 아키텍처
1. **Interface Layer** — CLI (rich + click), VS Code Extension (TypeScript)
2. **Core Engine** — ConversationManager, ToolExecutor, ContextManager
3. **MCP Layer** — MCP Client (.mcp.json 호환), MCP Server (Built-in 도구 노출)
4. **LLM Provider Layer** — vLLM 서버 연동 (OpenAI SDK)

#### 핵심 인터페이스 (ABC)
- `LLMProvider` — LLM 추론 추상화 (향후 언어 전환 대비)
- `Tool` — 도구 추상화 (OpenAI/MCP 스키마 변환 내장)
- `ToolRegistry` — Built-in + MCP 도구 통합 관리

#### Python 패키지 구조
```
services/myaicoder/src/myaicoder/
├── cli.py          # CLI 진입점
├── core/           # 엔진, 대화, 컨텍스트
├── llm/            # LLM 제공자 (vLLM)
├── tools/          # 6개 Built-in 도구
├── mcp/            # MCP Client/Server + Transport
├── ui/             # 터미널 UI (rich)
└── utils/          # 토큰, 파일 유틸리티
```

#### 구현 7-Phase 순서
1. 기본 CLI + LLM 연동
2. Tool Use (파일 읽기/쓰기/실행)
3. MCP Client
4. MCP Server
5. 컨텍스트 + 세션
6. VS Code 확장
7. 안정화 + 배포

### 주요 설계 결정
- **Agentic Loop**: LLM → tool_call → 실행 → 결과 주입 → 반복
- **MCP 호환**: Claude Code의 .mcp.json 그대로 사용
- **권한 모델**: auto(읽기) / approval(쓰기/실행) / deny
- **CLAUDE.md 로딩**: 계층적 (프로젝트 → 서브디렉토리 → 글로벌)
- **IDE 통신**: stdio 또는 WebSocket + JSON-RPC

## 생성 문서
- `docs/pdca/02-design/features/ai-coder-cli.design.md`

## PDCA 상태
```
[Plan] ✅ → [Design] ✅ → [Do] ⏳ → [Check] ⏳ → [Act] ⏳
```

## 다음 단계
- `/pdca do ai-coder-cli` 로 구현 시작 (Phase 1: 기본 CLI + LLM 연동)
