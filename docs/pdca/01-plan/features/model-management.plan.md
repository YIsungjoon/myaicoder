# Plan: model-management

**Feature**: model-management
**날짜**: 2026-03-14
**Phase**: Plan
**Level**: Enterprise
**Parent Context**: myAiCoder monorepo - 로컬 LLM 모델 관리 및 런타임 전환

---

## 1. 개요

사용자가 **여러 로컬 LLM 모델을 자유롭게 전환하며 사용**할 수 있도록 Model Management 기능을 구축한다.

현재 상태:
- `~/models/`에 3개의 GGUF 모델 파일 보관 중
  - `Qwen3.5-27B-Q4_K_M.gguf` (16GB) — 고품질 범용
  - `Qwen3.5-9B-Q4_K_M.gguf` (5.3GB) — 빠른 응답
  - `Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf` (18GB) — 코딩 특화
- Gateway에 `ModelRouter`가 존재하나 **config 기반 정적 라우팅**만 지원
- CLI에 `--model` 플래그 존재하나 **vLLM 서버 재시작 없이 모델 전환 불가**
- `/v1/models` 엔드포인트는 config에 등록된 모델만 반환

## 2. 환경별 운영 전략 (핵심 설계 결정)

### 2.1 DGX Spark 프로덕션 환경 (`prod.yaml`)

**하드웨어**: 128GB 통합 메모리 (Grace Blackwell)

- 3개 모델 **Always-on** (동시 로드)
- 모델별 전용 vLLM 프로세스 (포트 분리: 8001, 8002, 8003)
- Gateway가 `model` 파라미터로 즉시 라우팅 — **전환 대기 시간 0초**
- 메모리 분석: 3개 모델 합산 ~40GB → 80GB+ 여유 → 10명 동시 사용 가능

```
┌─────────────────────────────────────────────┐
│  DGX Spark (128GB)                          │
│                                             │
│  Gateway (:8080)                            │
│    ├─ model=qwen3.5-27b  → vLLM (:8001)    │  Always-on
│    ├─ model=qwen3.5-9b   → vLLM (:8002)    │  Always-on
│    └─ model=qwen3-coder  → vLLM (:8003)    │  Always-on
│                                             │
│  메모리: ~40GB 사용 / 80GB+ 여유            │
└─────────────────────────────────────────────┘
```

### 2.2 개발 데스크탑 환경 (`dev.yaml`)

**하드웨어**: 24GB VRAM (RTX 등)

- **기본: 9B 모델 1개만 로드** (5.3GB, VRAM 부담 최소)
- 27B(16GB) + 30B(18GB) = 34GB → 24GB VRAM에 동시 로드 **불가**
- 모델 전환 시 **stop → start** 순차 전환 (CLI `model switch`)
- 개발/테스트용으로 충분한 환경

```
┌─────────────────────────────────────────────┐
│  Dev Desktop (24GB VRAM)                    │
│                                             │
│  Gateway (:8080)                            │
│    └─ model=qwen3.5-9b   → vLLM (:8001)    │  Default
│                                             │
│  $ myaicoder model switch qwen3-coder-30b   │
│    ⏳ Stopping qwen3.5-9b...                │
│    ⏳ Loading qwen3-coder-30b...            │
│    ✓ Switched (12.3s)                       │
│                                             │
│  VRAM: 5.3~18GB 사용 / 모델 1개씩만        │
└─────────────────────────────────────────────┘
```

### 2.3 환경 감지 및 전략 선택

| 환경 | config | 모델 동시 로드 | 전환 방식 | switch 명령 |
|------|--------|---------------|----------|------------|
| DGX Spark | `prod.yaml` | 3개 전부 Always-on | 즉시 라우팅 | 불필요 (항상 가용) |
| Dev Desktop | `dev.yaml` | 1개 (기본 9B) | stop → start | `model switch` |

## 3. 핵심 요구사항

### 3.1 기능 요구사항

| ID | 기능 | 설명 | 우선순위 |
|----|------|------|----------|
| FR-01 | 환경별 config | `prod.yaml` / `dev.yaml` 환경 분리, 자동 감지 | P0 |
| FR-02 | 런처 스크립트 | 환경에 맞게 vLLM 프로세스 시작 (prod: 3개, dev: 1개) | P0 |
| FR-03 | 모델 목록 조회 | 사용 가능한 모델 + 현재 로드 상태 + 환경 표시 | P0 |
| FR-04 | 모델 전환 (dev) | dev 환경에서 stop → start 모델 전환 | P0 |
| FR-05 | 모델 상태 확인 | 로드된 모델, GPU/메모리 사용량, 서버 상태 | P0 |
| FR-06 | CLI 서브커맨드 | `myaicoder model {list,switch,status}` | P0 |
| FR-07 | Gateway 연동 | `/v1/models`에서 실제 가용 모델 실시간 반영 | P1 |
| FR-08 | 모델 프로필 | 모델별 추천 설정 (temperature, max_tokens 등) 프리셋 | P1 |
| FR-09 | VS Code 모델 선택 | Extension에서 모델 전환 UI | P2 |

### 3.2 비기능 요구사항

| ID | 항목 | 기준 |
|----|------|------|
| NFR-01 | prod 가용성 | 3개 모델 Always-on, 전환 대기 0초 |
| NFR-02 | dev 전환 시간 | 모델 전환 30초 이내 (vLLM 재시작 포함) |
| NFR-03 | 안전한 전환 | 진행 중인 요청 완료 후 전환 (graceful shutdown) |
| NFR-04 | 상태 피드백 | 전환 중 사용자에게 상태 표시 (loading, ready, error) |
| NFR-05 | 에러 복구 | dev 환경 전환 실패 시 이전 모델로 롤백 |
| NFR-06 | 테스트 가능성 | 프로세스 관리 로직에 단위 테스트 존재 |

## 4. 범위

### 4.1 In Scope

| # | 항목 | 우선순위 |
|---|------|----------|
| 1 | 환경별 config 시스템 (`prod.yaml`, `dev.yaml`) | P0 |
| 2 | 런처 스크립트 (환경별 vLLM 프로세스 시작) | P0 |
| 3 | `services/myaicoder`에 ModelManager 모듈 | P0 |
| 4 | VLLMProcessManager (프로세스 생명주기 관리) | P0 |
| 5 | GGUF 모델 파일 스캔 및 목록 관리 | P0 |
| 6 | CLI `model` 서브커맨드 (list, switch, status) | P0 |
| 7 | 모델 프로필/프리셋 설정 | P1 |
| 8 | Gateway `/v1/models` 실시간 반영 | P1 |
| 9 | pytest 테스트 스위트 | P0 |

### 4.2 Out of Scope

| 항목 | 사유 |
|------|------|
| 모델 다운로드 (HuggingFace 등) | 추후 별도 feature |
| 모델 파인튜닝 | 별도 feature |
| 웹 기반 관리 대시보드 | VS Code Extension으로 대체 |
| Ollama/llama.cpp 등 다른 런타임 | 현재 vLLM만 지원 |

## 5. 아키텍처 설계 방향

```
사용자 (CLI / VS Code / API)
     │
     ▼
┌──────────────────────────────┐
│  CLI: myaicoder model ...    │
│  - list / switch / status    │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│  ModelManager                │
│  - scan_models()             │
│  - switch_model(name)  [dev] │
│  - get_status()              │
│  - get_loaded_models()       │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│  VLLMProcessManager         │
│  - start(model, port, opts)  │
│  - stop(port, graceful)      │
│  - start_all()        [prod] │
│  - health_check(port)        │
│  - is_running(port)          │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│  vLLM Processes              │
│  prod: :8001, :8002, :8003   │
│  dev:  :8001 (1개만)         │
└──────────────────────────────┘
```

### 핵심 컴포넌트

1. **EnvironmentConfig**: 환경 감지 + config 로드
   - `prod.yaml` / `dev.yaml` 선택
   - 환경 변수 또는 CLI 플래그로 오버라이드

2. **ModelManager**: 모델 관리 오케스트레이션
   - 모델 디렉토리 스캔 (`~/models/*.gguf`)
   - prod: 모든 모델 상태 조회
   - dev: 전환 워크플로 (health check → graceful stop → start → health check)

3. **VLLMProcessManager**: vLLM 프로세스 생명주기
   - prod: `start_all()` — 3개 프로세스 동시 시작
   - dev: `start()` / `stop()` — 단일 프로세스 관리
   - health check polling (`/health`)
   - dev 전환 실패 시 롤백

4. **Launcher**: 런처 스크립트
   - 환경별 vLLM 시작 자동화
   - `myaicoder launch [--env prod|dev]`

## 6. 환경별 Config 구조 (안)

```yaml
# prod.yaml — DGX Spark (128GB)
environment: prod
models_dir: "~/models"

instances:
  - name: "qwen3.5-27b"
    file: "Qwen3.5-27B-Q4_K_M.gguf"
    port: 8001
    description: "Qwen 3.5 27B — 고품질 범용 모델"
    always_on: true
    vllm_args:
      gpu_memory_utilization: 0.3
      max_model_len: 32768
    defaults:
      temperature: 0.0
      max_tokens: 8192

  - name: "qwen3.5-9b"
    file: "Qwen3.5-9B-Q4_K_M.gguf"
    port: 8002
    description: "Qwen 3.5 9B — 빠른 응답 모델"
    always_on: true
    vllm_args:
      gpu_memory_utilization: 0.1
      max_model_len: 32768
    defaults:
      temperature: 0.0
      max_tokens: 8192

  - name: "qwen3-coder-30b"
    file: "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf"
    port: 8003
    description: "Qwen 3 Coder 30B — 코딩 특화 모델"
    always_on: true
    vllm_args:
      gpu_memory_utilization: 0.35
      max_model_len: 16384
    defaults:
      temperature: 0.0
      max_tokens: 8192

---
# dev.yaml — Dev Desktop (24GB VRAM)
environment: dev
models_dir: "~/models"

default_model: "qwen3.5-9b"
port: 8001

instances:
  - name: "qwen3.5-27b"
    file: "Qwen3.5-27B-Q4_K_M.gguf"
    description: "Qwen 3.5 27B — 고품질 범용 모델"
    vllm_args:
      gpu_memory_utilization: 0.9
      max_model_len: 32768
    defaults:
      temperature: 0.0
      max_tokens: 8192

  - name: "qwen3.5-9b"
    file: "Qwen3.5-9B-Q4_K_M.gguf"
    description: "Qwen 3.5 9B — 빠른 응답 모델"
    vllm_args:
      gpu_memory_utilization: 0.5
      max_model_len: 32768
    defaults:
      temperature: 0.0
      max_tokens: 8192

  - name: "qwen3-coder-30b"
    file: "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf"
    description: "Qwen 3 Coder 30B — 코딩 특화 모델"
    vllm_args:
      gpu_memory_utilization: 0.95
      max_model_len: 16384
    defaults:
      temperature: 0.0
      max_tokens: 8192
```

## 7. CLI 인터페이스 (안)

```bash
# ── prod 환경 ──

$ myaicoder model list
  ENV: prod (DGX Spark, 128GB)
  NAME              SIZE     PORT   STATUS     DESCRIPTION
  qwen3.5-27b       16GB     8001   loaded ●   Qwen 3.5 27B — 고품질 범용
  qwen3.5-9b        5.3GB    8002   loaded ●   Qwen 3.5 9B — 빠른 응답
  qwen3-coder-30b   18GB     8003   loaded ●   Qwen 3 Coder 30B — 코딩 특화

$ myaicoder model status
  Environment: prod (DGX Spark)
  Models loaded: 3/3 (All Always-on)
  Memory: ~40GB / 128GB (31%)

# ── dev 환경 ──

$ myaicoder model list
  ENV: dev (Desktop, 24GB VRAM)
  NAME              SIZE     STATUS      DESCRIPTION
  qwen3.5-27b       16GB     available   Qwen 3.5 27B — 고품질 범용
  qwen3.5-9b        5.3GB    loaded ●    Qwen 3.5 9B — 빠른 응답
  qwen3-coder-30b   18GB     available   Qwen 3 Coder 30B — 코딩 특화

$ myaicoder model switch qwen3-coder-30b
  ⏳ Stopping qwen3.5-9b (:8001)...
  ⏳ Loading qwen3-coder-30b (:8001)...
  ✓ Model switched to qwen3-coder-30b (12.3s)

# ── 런처 ──

$ myaicoder launch --env prod    # 3개 vLLM 동시 시작
$ myaicoder launch --env dev     # 기본 모델(9B) 1개 시작
$ myaicoder launch               # 환경 자동 감지
```

## 8. 성공 기준

- [ ] `prod.yaml` / `dev.yaml` 환경별 config가 동작한다
- [ ] `myaicoder launch`로 환경에 맞는 vLLM 프로세스가 시작된다
  - prod: 3개 동시 시작
  - dev: 기본 모델 1개 시작
- [ ] `myaicoder model list`로 모델 목록 + 로드 상태를 확인할 수 있다
- [ ] `myaicoder model switch` (dev)로 모델을 전환할 수 있다
- [ ] `myaicoder model status`로 현재 환경과 모델 상태를 확인할 수 있다
- [ ] dev 환경에서 전환 실패 시 이전 모델로 롤백된다
- [ ] prod 환경에서 `switch` 실행 시 "이미 모든 모델이 로드됨" 안내가 표시된다
- [ ] 테스트가 `uv run pytest tests -q`로 통과한다

## 9. 의존 관계

```
model-management (이번 feature)
  ├── depends on: services/myaicoder (CLI, config 인프라)
  ├── depends on: vLLM 런타임 (외부)
  ├── extends: services/gateway (ModelRouter — 라우팅 연동)
  ├── consumed by: CLI 사용자
  └── consumed by: vscode-extension (향후 FR-09)
```

## 10. 기술 결정 사항

| 항목 | 결정 | 근거 |
|------|------|------|
| 환경 전략 | prod(Always-on) / dev(switch) 이중 전략 | 하드웨어 제약 차이 |
| 프로세스 관리 | subprocess (asyncio) | systemd보다 단순, 개발 환경에 적합 |
| 환경 감지 | config 파일 + CLI 플래그 + 자동 감지 | 유연한 환경 전환 |
| 모델 설정 | YAML (prod.yaml, dev.yaml) | 기존 gateway.yaml과 일관성 |
| dev 전환 | stop → start (sequential) | 단일 GPU에서 동시 로드 불가 |
| prod 라우팅 | Gateway ModelRouter 활용 | 기존 인프라 재사용 |
| Health check | HTTP polling (/health) | vLLM 기본 제공 엔드포인트 |
| 롤백 | 이전 모델 정보 메모리 보관 (dev만) | 실패 시 이전 모델로 재시작 |

## 11. 리스크

| 리스크 | 영향 | 대응 |
|--------|------|------|
| dev에서 vLLM 시작 30초 초과 | UX 저하 | 프로그레스 표시, 타임아웃 설정 |
| dev에서 GPU 메모리 부족 | 로드 실패 | 롤백 + 모델별 VRAM 요구량 표시 |
| prod에서 3개 동시 시작 시 메모리 피크 | 순간 부하 | 순차 시작 (1 → 2 → 3) |
| 진행 중인 요청 끊김 (dev switch) | 데이터 손실 | graceful shutdown (drain 대기) |
| vLLM 버전별 인수 차이 | 호환성 | vllm_args를 config로 분리 |
