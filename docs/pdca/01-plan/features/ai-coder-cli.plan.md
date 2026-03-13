# Plan: AI Coder CLI (Claude Code 대안)

**Feature**: ai-coder-cli
**날짜**: 2026-03-13
**Phase**: Plan
**Level**: Enterprise

---

## 1. 개요

Claude Code와 유사한 AI 코딩 어시스턴트를 오픈소스 LLM(Qwen3.5-27B INT4)을 기반으로 구축한다.
로컬 LLM 추론을 통해 외부 API 의존 없이 독립적으로 동작하며,
Claude Code의 MCP 생태계와 호환되는 도구를 만든다.

## 2. 핵심 요구사항

### 2.1 기능 요구사항

| ID | 기능 | 설명 | 우선순위 |
|----|------|------|----------|
| FR-01 | **CLI 인터페이스** | 터미널에서 대화형 코딩 어시스턴트 실행 | P0 |
| FR-02 | **IDE 연동** | VS Code, JetBrains 등 IDE 확장 프로그램 | P0 |
| FR-03 | **MCP 클라이언트** | Claude Code의 MCP 서버들을 그대로 사용 | P0 |
| FR-04 | **MCP 서버** | 자체 도구(Read, Write, Edit, Bash 등)를 MCP로 노출 | P1 |
| FR-05 | **로컬 LLM 추론** | Qwen3.5-27B INT4 로컬 실행 | P0 |
| FR-06 | **Tool Use** | LLM의 function calling → 파일 읽기/쓰기/편집/검색/실행 | P0 |
| FR-07 | **컨텍스트 관리** | 프로젝트 구조 인식, CLAUDE.md 로딩 | P1 |
| FR-08 | **세션 관리** | 대화 히스토리 압축 및 지속 | P2 |

### 2.2 비기능 요구사항

| ID | 항목 | 기준 |
|----|------|------|
| NFR-01 | 응답 속도 | 첫 토큰 < 2초 (로컬 GPU) |
| NFR-02 | 메모리 | INT4 모델 로딩 시 VRAM 16GB 이내 |
| NFR-03 | 설치 | 단일 커맨드 설치 (npm/pip/cargo install) |
| NFR-04 | 호환성 | Linux, macOS, Windows(WSL) |
| NFR-05 | MCP 호환 | Claude Code의 .mcp.json 설정 파일 그대로 사용 가능 |

## 3. 시스템 아키텍처 (개요)

```
┌─────────────────────────────────────────────────────────┐
│                    사용자 인터페이스                        │
│  ┌─────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │   CLI   │  │ VS Code Ext  │  │ JetBrains Plugin   │  │
│  └────┬────┘  └──────┬───────┘  └─────────┬──────────┘  │
│       └──────────────┼────────────────────┘              │
│                      ▼                                    │
│  ┌──────────────────────────────────────────────────┐    │
│  │              Core Engine (코어 엔진)               │    │
│  │  ┌──────────┐ ┌──────────┐ ┌────────────────┐   │    │
│  │  │ 대화 관리 │ │ Tool 실행 │ │ 컨텍스트 관리   │   │    │
│  │  └──────────┘ └──────────┘ └────────────────┘   │    │
│  └───────────────────┬──────────────────────────────┘    │
│                      ▼                                    │
│  ┌────────────────────────────────────┐                  │
│  │         MCP Layer                  │                  │
│  │  ┌────────────┐ ┌──────────────┐  │                  │
│  │  │ MCP Client │ │  MCP Server  │  │                  │
│  │  │ (외부 도구) │ │ (자체 도구)   │  │                  │
│  │  └────────────┘ └──────────────┘  │                  │
│  └────────────────────────────────────┘                  │
│                      ▼                                    │
│  ┌────────────────────────────────────┐                  │
│  │      LLM Inference Backend        │                  │
│  │  Qwen3.5-27B INT4 (로컬 추론)      │                  │
│  │  llama.cpp / vLLM / llama-cpp-py  │                  │
│  └────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────┘
```

## 4. 구현 언어 분석 및 추천

### 4.1 언어별 상세 평가

#### 🥇 TypeScript (Node.js) — 추천도: ★★★★★

| 항목 | 평가 |
|------|------|
| **CLI 개발** | ✅ 최상 — ink(React for CLI), Commander.js, 풍부한 터미널 UI 라이브러리 |
| **IDE 연동** | ✅ 최상 — VS Code 확장은 TypeScript 네이티브, LSP 구현 풍부 |
| **MCP 호환** | ✅ 최상 — `@modelcontextprotocol/sdk` 공식 Tier 1 SDK |
| **LLM 연동** | ⚠️ 보통 — HTTP API로 추론 서버 호출 (직접 추론 불가) |
| **배포** | ✅ 좋음 — npm 패키지, pkg로 단일 바이너리 가능 |
| **생태계** | ✅ 최상 — Claude Code 자체가 TypeScript로 작성됨 |

**핵심 장점**: Claude Code의 구현 언어와 동일. MCP SDK가 가장 성숙함. IDE 확장 개발이 네이티브.
**핵심 단점**: LLM 직접 추론 불가 → 별도 추론 서버 필요.

---

#### 🥈 Rust — 추천도: ★★★★☆

| 항목 | 평가 |
|------|------|
| **CLI 개발** | ✅ 최상 — clap, ratatui, crossterm. 최고 수준의 터미널 성능 |
| **IDE 연동** | ⚠️ 보통 — VS Code: WASM 또는 별도 TS wrapper 필요 |
| **MCP 호환** | ✅ 좋음 — Tier 2 SDK (rust-mcp-sdk), JSON-RPC 직접 구현 가능 |
| **LLM 연동** | ✅ 좋음 — llama.cpp 바인딩(llama-cpp-rs), candle 프레임워크 |
| **배포** | ✅ 최상 — 단일 바이너리, 크로스 컴파일, 의존성 없음 |
| **생태계** | ⚠️ 보통 — AI/ML 생태계 성장 중이나 Python에 비해 부족 |

**핵심 장점**: 성능 최강. 단일 바이너리로 LLM 추론 + CLI + MCP를 한 프로세스에 통합 가능.
**핵심 단점**: 개발 속도 느림. VS Code 확장은 별도 TypeScript 레이어 필요.

---

#### 🥉 Python — 추천도: ★★★★☆

| 항목 | 평가 |
|------|------|
| **CLI 개발** | ⚠️ 보통 — rich, textual, click. 시작 속도 느림 (~500ms) |
| **IDE 연동** | ⚠️ 보통 — VS Code: 별도 TS 확장 필요, 백엔드로만 사용 |
| **MCP 호환** | ✅ 최상 — 공식 Tier 1 SDK, FastMCP 모듈 |
| **LLM 연동** | ✅ 최상 — vLLM, llama-cpp-python, transformers, GGUF 직접 로딩 |
| **배포** | ❌ 약함 — 가상환경 의존, PyInstaller 빌드 대형화 |
| **생태계** | ✅ 최상 — AI/ML 최강 생태계 |

**핵심 장점**: LLM 추론 생태계 최강. Qwen 모델 직접 로딩/추론 가장 용이.
**핵심 단점**: CLI 시작 속도 느림. 배포/설치 복잡. 단독 CLI 도구로는 부적합.

---

#### Go — 추천도: ★★★☆☆

| 항목 | 평가 |
|------|------|
| **CLI 개발** | ✅ 좋음 — cobra, bubbletea(TUI). 빠른 시작 속도 |
| **IDE 연동** | ⚠️ 보통 — VS Code: 별도 TS 확장 필요 |
| **MCP 호환** | ✅ 좋음 — 공식 Tier 1 SDK (mcp-go) |
| **LLM 연동** | ❌ 약함 — ollama Go 바인딩 있으나 직접 추론 라이브러리 부족 |
| **배포** | ✅ 최상 — 단일 바이너리, 크로스 컴파일 |
| **생태계** | ⚠️ 보통 — CLI 도구에 강하나 AI/ML 약함 |

**핵심 장점**: 빌드/배포 최고. 동시성 처리 우수.
**핵심 단점**: LLM 직접 추론 거의 불가 → 외부 서버 필수.

---

#### C++ — 추천도: ★★☆☆☆ (단독 사용 비추천)

| 항목 | 평가 |
|------|------|
| **CLI 개발** | ⚠️ 보통 — 라이브러리 부족, 개발 속도 느림 |
| **IDE 연동** | ❌ 약함 — 별도 래퍼 필수 |
| **MCP 호환** | ❌ 약함 — 공식 SDK 없음, 직접 JSON-RPC 구현 필요 |
| **LLM 연동** | ✅ 최상 — llama.cpp 네이티브, 최고 성능 추론 |
| **배포** | ⚠️ 보통 — 컴파일 의존성 복잡 |

**핵심 장점**: LLM 추론 성능 최고 (llama.cpp 네이티브).
**핵심 단점**: 단독으로 전체 시스템 구축 비현실적. 추론 엔진으로만 활용 권장.

---

### 4.2 종합 비교표

| 기준 | TypeScript | Rust | Python | Go | C++ |
|------|:---:|:---:|:---:|:---:|:---:|
| CLI 개발 | ★★★★★ | ★★★★★ | ★★★☆☆ | ★★★★☆ | ★★☆☆☆ |
| IDE 연동 | ★★★★★ | ★★★☆☆ | ★★★☆☆ | ★★★☆☆ | ★☆☆☆☆ |
| MCP 호환 | ★★★★★ | ★★★★☆ | ★★★★★ | ★★★★☆ | ★☆☆☆☆ |
| LLM 추론 | ★★☆☆☆ | ★★★★☆ | ★★★★★ | ★★☆☆☆ | ★★★★★ |
| 배포 용이 | ★★★★☆ | ★★★★★ | ★★☆☆☆ | ★★★★★ | ★★★☆☆ |
| 개발 속도 | ★★★★★ | ★★★☆☆ | ★★★★★ | ★★★★☆ | ★★☆☆☆ |
| **종합** | **★★★★★** | **★★★★☆** | **★★★★☆** | **★★★☆☆** | **★★☆☆☆** |

### 4.3 추천 조합 (3가지 옵션)

---

#### 옵션 A: TypeScript + Python (실용적 최적안) ⭐ 추천

```
┌─────────────────────────────────┐
│  TypeScript (메인)               │
│  • CLI (ink / Commander.js)     │
│  • VS Code 확장                  │
│  • MCP Client/Server            │
│  • Core Engine                  │
├─────────────────────────────────┤
│  Python (추론 서버)              │
│  • vLLM 또는 llama-cpp-python   │
│  • Qwen3.5-27B INT4 로딩        │
│  • OpenAI-compatible API 노출   │
└─────────────────────────────────┘
```

- **장점**: Claude Code와 동일한 아키텍처. MCP 생태계 100% 호환. 개발 속도 최상.
- **단점**: 2개 런타임 관리. Python 추론 서버 별도 프로세스.
- **적합 대상**: 빠른 MVP, Claude Code 사용자 기반 확장.

---

#### 옵션 B: Rust + TypeScript (고성능 하이브리드)

```
┌─────────────────────────────────┐
│  Rust (코어 엔진)                │
│  • CLI (ratatui + crossterm)    │
│  • Core Engine                  │
│  • MCP Client/Server            │
│  • llama.cpp 바인딩 (추론 통합)  │
├─────────────────────────────────┤
│  TypeScript (IDE 확장 전용)      │
│  • VS Code Extension            │
│  • JetBrains Plugin wrapper     │
└─────────────────────────────────┘
```

- **장점**: 단일 바이너리에 추론 포함. 최고 성능. 의존성 최소화.
- **단점**: 개발 속도 느림. Rust MCP SDK가 Tier 2.
- **적합 대상**: 성능 중시, 장기 프로젝트, 배포 간편성.

---

#### 옵션 C: Python 중심 (AI-First)

```
┌─────────────────────────────────┐
│  Python (메인)                   │
│  • CLI (textual / rich)         │
│  • Core Engine                  │
│  • MCP Client/Server (FastMCP)  │
│  • LLM 추론 (vLLM 직접 통합)    │
├─────────────────────────────────┤
│  TypeScript (IDE 확장 전용)      │
│  • VS Code Extension            │
└─────────────────────────────────┘
```

- **장점**: 단일 언어로 대부분 구현. AI/ML 라이브러리 풍부. 프로토타이핑 최상.
- **단점**: CLI 시작 속도 느림. 배포 복잡(venv 의존).
- **적합 대상**: AI 연구 중심, 모델 교체/실험 빈번.

---

## 5. 기술적 핵심 고려사항

### 5.1 MCP 호환성 전략

Claude Code의 MCP 생태계를 그대로 활용하려면:

| 항목 | 구현 내용 |
|------|----------|
| `.mcp.json` 파싱 | Claude Code와 동일한 설정 파일 형식 지원 |
| stdio 트랜스포트 | 로컬 MCP 서버 subprocess 실행 |
| Streamable HTTP | 원격 MCP 서버 연결 |
| JSON-RPC 2.0 | MCP 프로토콜 메시지 포맷 준수 |
| Tool Discovery | `tools/list` → LLM function calling 스키마 변환 |
| Capability Negotiation | 서버 연결 시 capabilities 교환 |

### 5.2 Qwen3.5-27B INT4 추론 옵션

| 방식 | 도구 | VRAM | 속도 | 비고 |
|------|------|------|------|------|
| vLLM | vLLM 서버 | ~16GB | 빠름 | OpenAI API 호환, 추천 |
| llama-cpp-python | llama.cpp 바인딩 | ~14GB | 보통 | GGUF 포맷 필요 |
| llama.cpp (직접) | llama-server | ~14GB | 빠름 | C++ 빌드 필요 |
| Ollama | ollama serve | ~16GB | 보통 | 가장 간편, 커스텀 제한 |

### 5.3 Tool Use (Function Calling) 구현

Qwen3.5는 function calling을 지원하므로:
1. MCP tools → OpenAI function calling 스키마로 변환
2. LLM 응답에서 tool_call 파싱
3. 해당 MCP 도구 실행
4. 결과를 다시 LLM에 주입
5. 반복 (agentic loop)

## 6. 리스크 및 완화 전략

| 리스크 | 영향 | 완화 전략 |
|--------|------|----------|
| Qwen3.5-27B의 tool calling 정확도 | 높음 | 프롬프트 엔지니어링, few-shot, 폴백 파싱 |
| INT4 양자화로 인한 품질 저하 | 중간 | GPTQ/AWQ 비교 실험, 핵심 도구는 구조화 출력 강제 |
| MCP SDK 버전 호환성 | 중간 | MCP spec 버전 고정, 하위 호환 테스트 |
| GPU 메모리 부족 | 높음 | 모델 분할 로딩, CPU 오프로딩 옵션 |
| IDE 확장 멀티플랫폼 지원 | 중간 | VS Code 우선, JetBrains 2차 |

## 7. 마일스톤 (초안)

| Phase | 목표 | 기간 |
|-------|------|------|
| M1 | CLI 기본 동작 + Qwen3.5 추론 연동 | - |
| M2 | Tool Use (파일 읽기/쓰기/실행) | - |
| M3 | MCP Client 구현 (외부 MCP 서버 연결) | - |
| M4 | MCP Server 구현 (자체 도구 노출) | - |
| M5 | VS Code 확장 | - |
| M6 | 컨텍스트 관리 + 세션 | - |
| M7 | 안정화 + 배포 | - |

## 8. 결정 사항

- [x] **구현 언어 조합 선택**: **옵션 C (Python 중심)** 채택 (2026-03-13)
  - 초기 단계: Python(CLI, MCP, Core, LLM 추론) + TypeScript(IDE 확장)
  - 사유: 프로젝트 초기이므로 프로토타이핑 속도 및 LLM 실험 유연성 우선
- [x] **LLM 추론 방식 선택**: **vLLM** 채택 (2026-03-13)
  - OpenAI-compatible API 제공 → 클라이언트 코드 교체 없이 모델 교체 가능
  - Qwen3.5-27B INT4 지원, Paged Attention으로 메모리 효율적
- [x] **우선 지원 IDE**: **VS Code 기반 IDE** (2026-03-13)
  - VS Code, Windsurf 등 VS Code 기반 IDE 전체 호환
  - VS Code Extension API로 개발 → 모든 VS Code 포크에서 동작
- [x] **프로젝트 이름**: **myAiCoder** 확정 (2026-03-13)

## 9. 언어 전환 로드맵

```
[현재] 옵션 C: Python 중심
  │
  │  MVP 완성 + 성능 벤치마크
  │
  ├──→ 옵션 A: TypeScript + Python  (MCP 호환성/개발속도 우선 시)
  │     - CLI/MCP/Core를 TypeScript로 재작성
  │     - Python은 추론 서버로만 유지
  │
  └──→ 옵션 B: Rust + TypeScript    (성능/배포 간편성 우선 시)
        - Core+CLI+MCP+추론을 Rust 단일 바이너리로 통합
        - TypeScript는 IDE 확장만 유지
```

### 전환 판단 기준
| 기준 | 옵션 A로 전환 | 옵션 B로 전환 |
|------|-------------|-------------|
| CLI 시작 속도 | Python > 1초로 불편 | Python > 1초로 불편 |
| 배포 피드백 | 설치 과정 복잡하다는 불만 | 단일 바이너리 필요 |
| MCP 호환성 | TS SDK가 더 안정적 | - |
| 추론 성능 | - | Rust 바인딩이 충분히 성숙 |
| 사용자 규모 | 커뮤니티 확장 필요 | 대규모 배포 필요 |

### 전환 용이성을 위한 설계 원칙
1. **Core Engine을 독립 모듈로 분리** — 추후 다른 언어로 포팅 가능
2. **MCP 통신 레이어 별도 모듈화** — 프로토콜 처리와 비즈니스 로직 분리
3. **인터페이스(ABC) 기반 설계** — 구현체 교체 용이
4. **설정/프로토콜은 JSON 기반** — 언어 무관하게 호환

---

*작성일: 2026-03-13 | Phase: Plan | Status: All Decisions Made*
*결정 완료일: 2026-03-13*
*언어: Python + TypeScript(IDE) | 추론: vLLM | IDE: VS Code 기반 | 이름: myAiCoder*
