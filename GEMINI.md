# GEMINI.md - myAiCoder Project Mandates

## 1. Project Identity & Philosophy
**myAiCoder**은 엔터프라이즈급 로컬 LLM 기반 AI 코딩 어시스턴트입니다.
- **기본 언어**: 모든 상호작용 및 문서화는 **한국어**를 기본으로 합니다.
- **핵심 목표**: Claude Code와 유사한 강력한 AI 코딩 경험을 제공하되, 모든 데이터를 로컬 환경에서 보호합니다.
- **Key Technologies**: Python (Core/Gateway), TypeScript (VS Code Ext), MCP (Protocol), llama.cpp/vLLM (Backend).
- **Primary Interface**: VS Code Extension (with Diff view, Chat panel, and StatusBar integration).

## 2. Architectural Mandates

### 2.1 Gateway Service (`services/gateway`)
- **Refactoring Requirement**: Root-level files must be organized into subpackages to reduce coupling.
- **Target Structure**:
  - `auth/`: Authentication stores and logic.
  - `middleware/`: Concurrency, rate limiting, and FastAPI dependencies.
  - `proxy/`: Forwarding logic and model routing.
  - `infra/`: DB, logging, and Prometheus metrics.
  - `config/`: Settings and data models.

### 2.2 Core Tools (`services/myaicoder/src/myaicoder/tools`)
- **Logical Grouping**: Tools must be categorized into functional sub-directories.
  - `filesystem/`: read, write, edit, list_dir.
  - `search/`: bash, glob, grep.
  - `external/`: build_runner, web_fetch.
- **New Tool Addition**: Always implement `deepagents`-style planning tools (e.g., `write_todos`) to improve agent reasoning.

### 2.3 Agent Logic
- **Execution Loop**: Standard agentic loop with tool calls and human-in-the-loop approvals.
- **Intelligence Upgrades**:
  - **Planning first**: Encourage the agent to use a "Planning" tool before executing complex edits.
  - **Sub-agents**: Implement task delegation for high-context or multi-file refactoring (Inspired by `deepagents`).

## 3. Development Workflow (PDCA & Gap Analysis)
- **Mandatory Lifecycle**: Research -> Strategy (Plan) -> Execution (Do) -> Validation (Check/Act).
- **Gap Analysis**: For every major feature, perform a Gap Analysis between the Design document and the implementation (Match Rate target: >95%).
- **Documentation**: Maintain `chat_log` and `docs/pdca` as the source of truth for project history.

## 4. Coding Standards & Tooling
- **Python**: Use `uv` for package management, `ruff` for linting, and `pytest` for testing.
- **TypeScript**: Use `pnpm` for workspaces, `esbuild` for bundling, and `vitest` for testing.
- **Backend**: Default LLM port is `8080`. Always verify `llama.cpp` compatibility for new features.

## 5. High-Priority Roadmap
1. **[Refactoring]** Gateway and Tools restructuring (as per `docs/structure-analysis.md`).
2. **[Intelligence]** Integration of `deepagents` features: `write_todos` and Sub-agent delegation.
3. **[Observability]** Prometheus + Grafana dashboard integration.
4. **[Optimization]** Token-based Rate Limiting for multi-user environments.
