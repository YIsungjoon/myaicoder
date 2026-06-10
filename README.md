# myAiCoder

> AI coding assistant powered by local LLM — your data stays on your machine

myAiCoder는 로컬 LLM(llama.cpp) + MCP 프로토콜 기반 AI 코딩 어시스턴트입니다.
VS Code에서 채팅하며 파일 읽기/쓰기, 코드 검색, 빌드, 웹 검색 등 9가지 도구를 사용할 수 있습니다.

## Getting Started

**[docs/getting-started.md](docs/getting-started.md)** — 서버 모드(3분) / 로컬 모드(10분) 셋업 가이드

### Quick Start (LM Studio 연동 - 1분)

LM Studio와 같이 로컬에서 OpenAI 호환 API 서버를 띄워 사용할 경우:

1. **LM Studio 실행**: 로컬 서버를 기동합니다. (기본 포트: `1234`)
2. **myaicoder CLI 설치**:
   ```bash
   pip install -e services/myaicoder/
   ```
3. **VS Code Extension 설치**: 배포된 `.vsix` 파일을 설치합니다.
4. **VS Code 설정**: `myaicoder.llmUrl` 설정에 LM Studio 주소인 **`http://127.0.0.1:1234`**를 입력합니다.
   > [!NOTE]
   > Extension 내부에서 자동으로 `/v1` 접미사를 붙여 통신하므로, 설정 주소 끝에 `/v1`은 제외하고 입력하시면 됩니다.

### Quick Start (서버 모드)

```bash
git clone <repo-url> myaicoder && cd myaicoder
pip install -e services/myaicoder/
code --install-extension myaicoder-0.1.0.vsix
# VS Code 설정: myaicoder.llmUrl → http://dgx-server:8080
```

## Architecture

```
VS Code Extension ──> myaicoder serve (로컬 도구 9개)
        │
        └──> Gateway (:8080) ──> LLM Server (:8001)
              │                    └ Qwen3.5 (GGUF)
              ├ Auth (API key)
              ├ Rate Limiting
              ├ Prometheus Metrics
              └ Structured Logging
```

## Project Structure

```
myaicoder/
├── apps/vscode-extension/    VS Code Extension (TypeScript)
├── services/myaicoder/       Core CLI + MCP Server (Python)
├── services/gateway/         API Gateway (FastAPI)
├── config/                   Central config (gitignored, use .example files)
├── scripts/                  Setup & startup scripts
├── docs/                     Documentation + PDCA records
└── docker-compose.yml        Prometheus + Grafana
```

## Key Features

- **9 Built-in Tools**: Read, Write, Edit, Glob, Grep, Bash, BuildRunner, WebFetch, ListDir
- **MCP Protocol**: VS Code Extension ↔ CLI 간 표준 통신
- **Gateway**: 인증, Rate Limiting, 모델 라우팅, Prometheus 메트릭
- **Context Management**: 자동 압축, 토큰 윈도우 관리
- **Session Persistence**: 대화 히스토리 저장/로드

## Development

```bash
# 테스트
cd services/myaicoder && uv run pytest tests -q    # 178 passed
cd services/gateway && uv run pytest tests -q      # 43 passed

# Extension
cd apps/vscode-extension && npm test               # 20 passed

# 코드 품질
cd services/myaicoder && uv run ruff check .
cd services/gateway && uv run ruff check .
```

## License

MIT
