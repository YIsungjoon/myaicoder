# 006. Do Phase 1: 기본 CLI + vLLM 연동

**날짜**: 2026-03-13
**작업 유형**: PDCA Do (구현)
**Feature**: ai-coder-cli
**Phase**: Phase 1 / 7

## 구현 내용

### Design 문서 Phase 1 체크리스트

- [x] `pyproject.toml` — 패키지 설정, 의존성, CLI 진입점
- [x] `llm/base.py` — LLMProvider ABC (Message, ToolCall, LLMResponse)
- [x] `llm/vllm_provider.py` — vLLM 구현체 (OpenAI SDK 사용)
- [x] `cli.py` — click 기반 CLI (대화형 + 원샷 + 서브커맨드)
- [x] `ui/chat.py` — rich 기반 터미널 UI
- [x] `core/conversation.py` — 대화 히스토리 관리
- [x] `core/context.py` — 프로젝트 컨텍스트 (CLAUDE.md 로딩)
- [x] `core/config.py` — 설정 파일 로딩
- [x] `core/engine.py` — 에이전트 루프 (Phase 1: 도구 없이)
- [x] 테스트 작성 (10 passed, 2 skipped)

### 생성된 파일 목록

```
services/myaicoder/
├── pyproject.toml
├── src/myaicoder/
│   ├── __init__.py, __main__.py
│   ├── cli.py                    # click CLI
│   ├── core/
│   │   ├── config.py             # 설정 관리
│   │   ├── context.py            # 컨텍스트 관리
│   │   ├── conversation.py       # 대화 관리
│   │   └── engine.py             # 에이전트 엔진
│   ├── llm/
│   │   ├── base.py               # LLMProvider ABC
│   │   └── vllm_provider.py      # vLLM 구현체
│   └── ui/
│       └── chat.py               # 터미널 UI
├── tests/
│   ├── conftest.py               # MockLLMProvider
│   ├── test_core/
│   │   ├── test_engine.py        # 엔진 테스트 (4)
│   │   └── test_conversation.py  # 대화 테스트 (3)
│   └── test_llm/
│       └── test_vllm_provider.py # 직렬화 + 통합 테스트 (3+2)
└── scripts/
    └── start_vllm.sh             # vLLM 서버 시작
```

### CLI 사용법
```bash
# 가상환경 활성화
source .venv/bin/activate

# 대화형 모드
myaicoder

# 원샷 모드
myaicoder -p "Hello, what can you do?"

# 설정 확인
myaicoder config

# vLLM URL 지정
myaicoder --vllm-url http://gpu-server:8000/v1
```

### 테스트 결과
- 10 passed, 2 skipped (vLLM 통합 테스트)
- 실행 시간: 0.20초

### 발견 및 수정 사항
- `prompt`를 positional argument → `--prompt` 옵션으로 변경 (서브커맨드 충돌 해결)

## PDCA 상태
```
[Plan] ✅ → [Design] ✅ → [Do] 🔄 (Phase 1/7 완료) → [Check] ⏳ → [Act] ⏳
```

## 다음 단계
- Phase 2: Tool Use 구현 (Read, Write, Edit, Glob, Grep, Bash)
- 또는 vLLM 서버 연결 후 통합 테스트 실행
