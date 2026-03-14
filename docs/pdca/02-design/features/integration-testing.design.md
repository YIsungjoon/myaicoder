# Design: integration-testing

**Feature**: integration-testing
**날짜**: 2026-03-14
**Phase**: Design
**Level**: Enterprise
**Plan Reference**: `docs/pdca/01-plan/features/integration-testing.plan.md`

---

## 1. 설계 개요

mock 기반 테스트로 덮어둔 실환경 리스크를 해소한다. 세 가지 산출물을 만든다:

1. **`config/` 실환경 설정 파일** — Gateway + Models 설정
2. **환경변수 기반 skip 전환** — 기존 `skipif(True)` → `skipif(not env)`
3. **수동 검증 스크립트** — `scripts/integration_test.sh` (TTFT 측정 포함)

### 환경

| 항목 | 값 |
|------|-----|
| vLLM | 0.17.1 (`~/vllm-env/.venv/bin/vllm`) |
| GPU | NVIDIA RTX PRO 4000 Blackwell, 24GB |
| 기본 모델 | Qwen3.5-9B (5.3GB) |
| 모델 경로 | `~/models/` |

## 2. 산출물

### 2.1 `config/gateway.yaml` — 실환경 설정

```yaml
server:
  host: "0.0.0.0"
  port: 8080

auth:
  internal_token: "<generated>"
  users:
    - api_key_hash: "<generated>"
      user_id: "dev_user"
      name: "개발자"
      org: "MyAiCoder"
      role: "admin"

models:
  default: "qwen3.5-9b"
  routes:
    - name: "qwen3.5-9b"
      upstream: "http://localhost:8001/v1"
      description: "Qwen 3.5 9B"

rate_limit:
  enabled: true
  roles:
    admin:
      requests_per_minute: 120
      requests_per_hour: 3600

logging:
  level: "INFO"
  format: "json"
```

### 2.2 `config/models.yaml` — dev 환경 모델 설정

```yaml
environment: dev
models_dir: "~/models"
default_model: "qwen3.5-9b"
port: 8001
gateway_url: "http://localhost:8080"
internal_token: "<same as gateway>"

instances:
  - name: "qwen3.5-9b"
    file: "Qwen3.5-9B-Q4_K_M.gguf"
    description: "Qwen 3.5 9B — fast response"
    vllm_args:
      gpu_memory_utilization: 0.5
      max_model_len: 32768
  - name: "qwen3.5-27b"
    file: "Qwen3.5-27B-Q4_K_M.gguf"
    description: "Qwen 3.5 27B — high quality"
    vllm_args:
      gpu_memory_utilization: 0.9
      max_model_len: 32768
  - name: "qwen3-coder-30b"
    file: "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf"
    description: "Qwen 3 Coder 30B — coding"
    vllm_args:
      gpu_memory_utilization: 0.95
      max_model_len: 16384
```

### 2.3 기존 skip 테스트 전환

`skipif(True)` → 환경변수 기반:

```python
@pytest.mark.skipif(
    not os.environ.get("VLLM_INTEGRATION"),
    reason="Set VLLM_INTEGRATION=1 with running vLLM server",
)
```

### 2.4 `scripts/integration_test.sh` — 수동 검증 스크립트

TTFT 측정, Gateway 프록시 검증, rate limit 확인을 포함한 셸 스크립트.

핵심 검증 포인트:
- T2-2: TTFT (vLLM 직접 vs Gateway 경유 차이 100ms 이내)
- T3-4: model switch 직후 sleep 없이 즉시 요청 → race condition 검증
- T4-0: MCP stdout 오염 검증

## 3. 구현 순서

| 순서 | 작업 | 파일 |
|------|------|------|
| 1 | config/gateway.yaml 생성 (API key hash 생성) | config/ |
| 2 | config/models.yaml 생성 | config/ |
| 3 | 기존 skip 테스트 환경변수 전환 | tests/ |
| 4 | scripts/integration_test.sh 작성 | scripts/ |
| 5 | .gitignore에 config/*.yaml 추가 (secrets 보호) | .gitignore |
